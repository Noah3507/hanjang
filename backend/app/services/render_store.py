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

class RenderStore:
    def __init__(self, uploads, copies, executor):
        self.uploads, self.copies, self.executor = uploads, copies, executor
        self.lock = RLock()
        self.active = False

    @contextmanager
    def locked(self):
        with self.lock, self.copies.locked():
            yield

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
            result = record.renders.get(key) or record.renders.get(record.last_render)
            if not result:
                return self.blank(job, record, asset, copy)
            response = result.model_copy(deep=True)
            response.is_current = copy is not None and record.renders.get(key) is result
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
            result.revision = max((r.revision for r in record.renders.values()), default=0)+1
            result.status = 'processing'
            result.warnings = ['MOCK_COPY_NOT_LLM'] if result.mock_copy else ['COPY_REVIEW_REQUIRED']
            record.renders[key], record.last_render = result, key
            data, _ = self.uploads.read_asset(owner, asset.asset_id)
            self.active = True
            return result.model_copy(deep=True), (key, draft, copy, data, asset.sha256)

    def finish(self, owner, job, task):
        key, draft, copy, data, selected_hash = task
        written = []
        try:
            results = self.executor(draft, copy, data)
            with self.locked():
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
                record.derived.update(dict(written))
                for asset, _ in written: self.uploads.assets[asset] = job
                response.candidates, response.measurements, response.status = candidates, measurements, 'completed'
        except Exception as error:
            for _, path in written: path.unlink(missing_ok=True)
            with self.locked():
                try: record = self.uploads.get(owner, job)
                except UploadError: return
                response = record.renders[key]
                response.status = 'failed'
                response.error = RenderError(code=error.code if isinstance(error, RenderFailure) else 'RENDER_FAILED',
                    message='광고를 렌더링하지 못했습니다. 입력·사진·카피는 유지됩니다.')
        finally:
            with self.lock: self.active = False
