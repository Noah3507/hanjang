"""Copy snapshot/cache is attached to the private upload record and its TTL."""
from contextlib import contextmanager
from hashlib import sha256
import json
from threading import RLock
import time
from app.schemas.copy import CopyResponse, CopyError, Attempt
from app.services.copy_prompt import provider_payload, PROMPT_VERSION, input_bound
from app.services.copy_validation import validate_copy, CopyFailure
from app.services.uploads import UploadError

def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

class CopyStore:
    def __init__(self, uploads, analysis, provider):
        self.uploads, self.analysis, self.provider = uploads, analysis, provider
        self.lock = RLock()
        self.active = False

    @contextmanager
    def locked(self):
        # Same analysis -> upload lock order as S4; saving facts needs only upload lock.
        with self.lock, self.analysis.lock, self.uploads.lock:
            yield

    def snapshot(self, owner, job):
        record = self.uploads.get(owner, job)
        if record.draft is None:
            raise UploadError(409, 'INPUT_NOT_SAVED', '상품 정보를 먼저 저장해 주세요.')
        photo, asset = self.analysis.selected(owner, job)
        draft = record.draft.model_copy(deep=True)
        context = self.analysis.context(owner, job)
        try:
            payload = provider_payload(draft, context)
        except CopyFailure:
            raise UploadError(422, 'COPY_PRIVATE_INPUT', '전송 제외된 주소나 Instagram이 다른 입력에 포함돼 있습니다. 상품 특징을 확인해 주세요.') from None
        hash_input = digest(draft.model_dump(mode='json'))
        key = digest({'asset': asset.asset_id, 'input': hash_input, 'payload': payload,
                      'provider': self.provider.name, 'model': self.provider.model, 'prompt': PROMPT_VERSION})
        return record, photo, asset, draft, payload, hash_input, key

    def blank(self, job, record, asset, draft, payload, hash_input):
        return CopyResponse(job_id=job, status='pending', status_url=f'/api/v1/jobs/{job}/copy-generation',
            source_asset_id=asset.asset_id, input_hash=hash_input, is_current=True,
            facts=draft.facts.model_copy(deep=True), mood=draft.mood, product_features=draft.product_features,
            use_address_for_copy=draft.use_address_for_copy, provider=self.provider.name, model=self.provider.model,
            analysis_used=bool(payload['visual_hints']), expires_at=record.upload.expires_at)

    def get(self, owner, job):
        with self.locked():
            record, photo, asset, draft, payload, hash_input, key = self.snapshot(owner, job)
            result = record.copies.get(key) or record.copies.get(record.last_copy)
            if result is None:
                return self.blank(job, record, asset, draft, payload, hash_input)
            response = result.model_copy(deep=True)
            response.is_current = key in record.copies and record.copies[key] is result
            return response

    def start(self, owner, job, body):
        with self.locked():
            record, photo, asset, draft, payload, hash_input, key = self.snapshot(owner, job)
            if body.expected_asset_id != asset.asset_id or body.expected_input != draft:
                raise UploadError(409, 'COPY_SOURCE_CHANGED', '저장된 상품 정보나 선택 사진이 변경됐습니다. 다시 조회해 주세요.')
            if photo.status == 'processing':
                raise UploadError(409, 'PHOTO_PROCESSING_BUSY', '사진 처리 완료 후 카피를 생성해 주세요.')
            cached = record.copies.get(key)
            if cached and cached.status in ('processing', 'completed'):
                record.last_copy = key
                return self.get(owner, job), None
            if self.active:
                raise UploadError(503, 'COPY_BUSY', '다른 카피 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요.')
            if input_bound(payload) > 6000:
                raise UploadError(422, 'COPY_INPUT_LIMIT', '입력과 분석 단서가 요청 한도를 초과했습니다. 상품 특징을 줄여 주세요.')
            response = self.blank(job, record, asset, draft, payload, hash_input)
            response.status = 'processing'
            response.warnings = ['MOCK_COPY_NOT_LLM'] if self.provider.name == 'mock' else ['COPY_REVIEW_REQUIRED']
            if not payload['visual_hints']:
                response.warnings.append('COPY_WITHOUT_CLIP')
            record.copies[key], record.last_copy = response, key
            self.active = True
            return response.model_copy(deep=True), (key, draft, payload)

    def finish(self, owner, job, task):
        key, draft, payload = task
        attempts = []
        try:
            for attempt in (1, 2):
                started = time.perf_counter()
                metric = Attempt(attempt=attempt, provider=self.provider.name, latency_seconds=0)
                try:
                    # Check TTL before a potentially billable retry.
                    self.uploads.get(owner, job)
                    reply = self.provider.generate(payload)
                    metric.input_tokens, metric.output_tokens = reply.input_tokens, reply.output_tokens
                    if reply.input_tokens is not None and reply.output_tokens is not None:
                        metric.estimated_cost_usd = (reply.input_tokens*.75+reply.output_tokens*4.5)/1_000_000
                    variants = validate_copy(reply.text, draft).variants
                    error = None
                except CopyFailure as failure:
                    error = failure
                    metric.error_code = failure.code
                    usage = getattr(self.provider, 'last_usage', None)
                    if usage:
                        metric.input_tokens, metric.output_tokens = usage
                        metric.estimated_cost_usd = (usage[0]*.75+usage[1]*4.5)/1_000_000
                    metric.reserved_unknown_cost_usd = getattr(self.provider, 'last_reserved_unknown', 0)
                finally:
                    metric.latency_seconds = round(time.perf_counter()-started, 4)
                    attempts.append(metric)
                if error is None or not error.retryable or attempt == 2:
                    break
                time.sleep(.1)
            with self.locked():
                record = self.uploads.get(owner, job)  # no publication after expiry
                response = record.copies[key]
                response.attempts = attempts
                if error:
                    response.status = 'failed'
                    response.error = CopyError(code=error.code, message='카피를 생성하지 못했습니다. 입력과 사진은 유지됩니다.', retryable=error.retryable)
                else:
                    response.status, response.variants = 'completed', variants
        except Exception:
            with self.locked():
                try:
                    record = self.uploads.get(owner, job)
                except UploadError:
                    return
                record.copies[key].status = 'failed'
                record.copies[key].attempts = attempts
                record.copies[key].error = CopyError(code='COPY_PROVIDER_FAILED', message='카피 생성에 실패했습니다. 입력과 사진은 유지됩니다.')
        finally:
            with self.lock:
                self.active = False

    def current_for_render(self, owner, job):
        """Future renderer must not use a stale snapshot. No rendering implemented here."""
        result = self.get(owner, job)
        if result.is_current and result.status == 'completed':
            return result
        return None
