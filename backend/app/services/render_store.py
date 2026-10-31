"""Atomic four-PNG publication under existing private upload TTL."""
from contextlib import contextmanager
from hashlib import sha256
import os
from threading import RLock
import uuid
from app.schemas.rendering import RenderResponse, RenderError, Candidate
from app.services.copy_store import digest
from app.services.render_execution import VERSION, RenderFailure, rgb
from app.services.uploads import UploadError
from app.services.render_slot import RenderSlot

class RenderStore:
    def __init__(self, uploads, copies, executor):
        self.uploads, self.copies, self.executor = uploads, copies, executor
        self.lock = RLock()
        self.slot = RenderSlot()

    @property
    def active(self):
        return self.slot.lease is not None

    @contextmanager
    def locked(self):
        with self.lock, self.copies.locked():
            self.slot.recover()
            yield

    def cancel_dispatch(self, task):
        with self.locked():self.slot.cancel(task[-1])

    def publish(self, record, job, written, hashes, **updates):
        """Copy-on-write transaction, restoring all references on registration failure.

        Caller holds render -> copy -> analysis -> upload locks. Nothing becomes
        observable between assignments, including to other jobs' asset readers.
        """
        changes={'derived':{**record.derived,**dict(written)},
                 'asset_hashes':{**record.asset_hashes,**hashes},**updates}
        before={name:getattr(record,name) for name in changes}
        old_assets=self.uploads.assets
        try:
            record.derived=changes.pop('derived')
            self.uploads.assets={**old_assets,**{asset:job for asset,_ in written}}
            for name,value in changes.items():setattr(record,name,value)
        except BaseException:
            for name,value in before.items():object.__setattr__(record,name,value)
            object.__setattr__(self.uploads,'assets',old_assets)
            raise

    def snapshot(self, owner, job):
        record, photo, asset, draft, _, _, _ = self.copies.snapshot(owner, job)
        copy = self.copies.current_for_render(owner, job)
        key = digest({'draft': draft.model_dump(mode='json'), 'asset': asset.asset_id,
            'copy': copy.model_dump(mode='json') if copy else None, 'template': VERSION})
        return record, photo, asset, draft, copy, key

    def blank(self, job, record, asset, copy):
        return RenderResponse(job_id=job, status='pending', status_url=f'/api/v1/jobs/{job}/rendering',
            source_asset_id=asset.asset_id, copy_key=copy.copy_key if copy else None,
            revision=1, is_current=True, mock_copy=copy.provider == 'mock' if copy else True,
            expires_at=record.upload.expires_at)

    def get(self, owner, job):
        with self.locked():
            record, _, asset, _, copy, key = self.snapshot(owner, job)
            result = record.edited_renders.get(key) or record.renders.get(key) or record.edited_renders.get(record.last_render) or record.renders.get(record.last_render)
            if not result:
                return self.blank(job, record, asset, copy)
            response = result.model_copy(deep=True)
            response.is_current = copy is not None and (record.edited_renders.get(key) is result or record.renders.get(key) is result)
            return response

    def start(self, owner, job, body):
        with self.locked():
            record, photo, asset, draft, copy, key = self.snapshot(owner, job)
            if body.expected_asset_id != asset.asset_id or body.expected_input != draft or not copy or body.expected_copy_key != copy.copy_key:
                raise UploadError(409, 'RENDER_SOURCE_CHANGED', '현재 입력·사진·카피가 일치하지 않습니다. 최신 카피를 생성해 주세요.')
            if photo.status == 'processing':
                raise UploadError(409, 'PHOTO_PROCESSING_BUSY', '사진 처리 완료 후 렌더링해 주세요.')
            cached = record.renders.get(key)
            if cached and cached.status in ('processing', 'completed'):
                record.last_render = key
                return self.get(owner, job), None
            if self.active:
                raise UploadError(503, 'RENDER_BUSY', '다른 광고를 렌더링 중입니다. 잠시 후 다시 시도해 주세요.')
            result = self.blank(job, record, asset, copy)
            result.revision = max((r.revision for r in [*record.renders.values(), *record.edited_renders.values()]), default=0)+1
            result.status = 'processing'
            result.warnings = ['MOCK_COPY_NOT_LLM'] if result.mock_copy else ['COPY_REVIEW_REQUIRED']
            data, _ = self.uploads.read_asset(owner, asset.asset_id)
            record.renders[key], record.last_render = result, key
            def abandoned():
                result.status='failed'
                result.error=RenderError(code='RENDER_FAILED',message='렌더링 작업이 시작되지 않았습니다. 다시 요청해 주세요.')
            token=self.slot.reserve(abandoned)
            return result.model_copy(deep=True), (key, draft, copy, data, asset.sha256,token)

    def finish(self, owner, job, task):
        key, draft, copy, data, selected_hash,token = task
        with self.locked():
            if not self.slot.claim(token):return
        written = []
        try:
            results = self.executor(draft, copy, data)
            with self.locked():
                if not self.slot.owns(token):return
                record = self.uploads.get(owner, job)
                response = record.renders[key]
                candidates, measurements = [], {}
                for result in results:
                    asset, candidate = uuid.uuid4().hex, uuid.uuid4().hex
                    path = self.uploads.safe_path(asset+'.png')
                    with os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'wb') as stream:
                        written.append((asset, path)); stream.write(result['png'])
                    stamp = record.upload.created_at.timestamp(); os.utime(path, (stamp, stamp))
                    m = result['measurement']
                    boxes = [{k: v for k, v in b.items() if k not in ('line_count', 'font_family', 'actual_fonts')} for b in m['text']]
                    for b in boxes:
                        b['foreground'] = rgb(b['foreground'])
                        b['background'] = None if b['background'].endswith(', 0)') else rgb(b['background'])
                    variant = next(v for v in copy.variants if v.strategy == result['strategy'])
                    candidates.append(Candidate(candidate_id=candidate, strategy=variant.strategy, revision=response.revision,
                        facts=draft.facts.model_copy(deep=True), copy=variant.ad_copy.model_dump(),
                        png={'asset_id':asset,'url':f'/api/v1/assets/{asset}','revision':response.revision},
                        renderer={'template_version':variant.strategy+'-'+VERSION,'text_boxes':boxes,'product_bbox':m['product'],
                            'photo_sha256':record.upload.sha256,'processed_photo_sha256':selected_hash}))
                    measurements[candidate] = m
                if len(candidates) != 4 or len({c.strategy for c in candidates}) != 4:
                    raise RenderFailure('RENDER_INVALID_RESULT')
                # Compute current state again; old result is retained, never promoted as current.
                _, _, _, _, current_copy, current_key = self.snapshot(owner, job)
                response.is_current = current_copy is not None and current_key == key
                completed=response.model_copy(deep=True)
                completed.candidates,completed.measurements,completed.status=candidates,measurements,'completed'
                self.publish(record,job,written,{asset:sha256(path.read_bytes()).hexdigest() for asset,path in written},
                    renders={**record.renders,key:completed},exports={} if completed.is_current else record.exports)
        except BaseException as error:
            for _, path in written:
                try:path.unlink(missing_ok=True)
                except OSError:pass
            with self.locked():
                try: record = self.uploads.get(owner, job)
                except UploadError: return
                response = record.renders[key]
                response.status = 'failed'
                response.error = RenderError(code=error.code if isinstance(error, RenderFailure) else 'RENDER_FAILED',
                    message='입력에 광고 글꼴이 지원하지 않는 문자 또는 이모지가 있습니다. 가게명·상품명·연락처를 확인해 주세요. 원문은 유지됩니다.'
                    if isinstance(error, RenderFailure) and error.code == 'RENDER_UNSUPPORTED_GLYPH'
                    else '광고를 렌더링하지 못했습니다. 입력·사진·카피는 유지됩니다.')
            if not isinstance(error,Exception):raise
        finally:
            with self.lock:self.slot.release(token)
