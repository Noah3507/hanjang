"""Analysis lives on upload records: same ownership, expiry and restart limits."""
from threading import RLock
from app.schemas.analysis import AnalysisResponse, AnalysisError, ClipResult
from app.services.analysis_palette import extract_palette
from app.services.uploads import UploadError

class AnalysisStore:
    def __init__(self, uploads, executor):
        self.uploads, self.executor = uploads, executor
        self.lock = RLock()
        self.active = False

    def selected(self, owner, job):
        state = self.uploads.photo_state(owner, job)
        asset = state.processed if state.photo_source == 'processed' else state.original
        return state, asset

    def get(self, owner, job):
        with self.lock, self.uploads.lock:
            record = self.uploads.get(owner, job)
            state, asset = self.selected(owner, job)
            cached = record.analyses.get(asset.asset_id)
            if cached is None and record.last_analysis:
                cached = record.analyses.get(record.last_analysis)
            if cached is None:
                return AnalysisResponse(job_id=job, status='pending', source_asset_id=asset.asset_id,
                    photo_source=state.photo_source, is_current=True, expires_at=record.upload.expires_at,
                    status_url=f'/api/v1/jobs/{job}/photo-analysis')
            response = cached.model_copy(deep=True)
            response.is_current = response.source_asset_id == asset.asset_id
            return response

    def start(self, owner, job, expected):
        with self.lock, self.uploads.lock:
            state, asset = self.selected(owner, job)
            if asset.asset_id != expected:
                raise UploadError(409, 'ANALYSIS_SOURCE_CHANGED', '선택된 사진이 변경됐습니다. 상태를 다시 조회해 주세요.')
            if state.status == 'processing':
                raise UploadError(409, 'PHOTO_PROCESSING_BUSY', '사진 처리 완료 후 분석해 주세요.')
            record = self.uploads.get(owner, job)
            cached = record.analyses.get(expected)
            if cached and cached.status in ('processing', 'completed'):
                record.last_analysis = expected
                return self.get(owner, job), False
            if self.active:
                raise UploadError(503, 'ANALYSIS_BUSY', '다른 사진을 분석 중입니다. 잠시 후 다시 시도해 주세요.')
            response = AnalysisResponse(job_id=job, status='processing', source_asset_id=expected,
                photo_source=state.photo_source, is_current=True, expires_at=record.upload.expires_at,
                status_url=f'/api/v1/jobs/{job}/photo-analysis')
            record.analyses[expected] = response
            record.last_analysis = expected
            self.active = True
            return response.model_copy(deep=True), True

    def finish(self, owner, job, asset):
        try:
            data, _ = self.uploads.read_asset(owner, asset)
            palette = extract_palette(data)
            try:
                reply = self.executor(data) if palette.status == 'available' else {
                    'clip': {'status': 'unavailable'}, 'warning': 'ANALYSIS_NO_VISIBLE_PIXELS'}
                clip = ClipResult.model_validate(reply['clip'])
                warning = reply.get('warning')
            except Exception:
                clip, warning = ClipResult(), 'ANALYSIS_CLIP_FAILED'
            warnings = [warning] if warning else []
            if palette.status == 'unavailable' and 'ANALYSIS_NO_VISIBLE_PIXELS' not in warnings:
                warnings.append('ANALYSIS_NO_VISIBLE_PIXELS')
            if clip.status == 'unavailable' and not warning:
                warnings.append('ANALYSIS_CLIP_UNAVAILABLE')
            with self.lock, self.uploads.lock:
                record = self.uploads.get(owner, job)  # never publish after expiry
                response = record.analyses[asset]
                response.clip, response.palette, response.warnings = clip, palette, warnings
                response.status = 'completed' if palette.status == 'available' or clip.status == 'available' else 'failed'
                if response.status == 'failed':
                    response.error = AnalysisError(code='ANALYSIS_UNAVAILABLE', message='분석 가능한 결과가 없습니다. 사진과 입력은 유지됩니다.')
        except Exception:
            with self.lock, self.uploads.lock:
                try:
                    record = self.uploads.get(owner, job)
                except UploadError:
                    return
                result = record.analyses[asset]
                result.status = 'failed'
                result.error = AnalysisError(code='ANALYSIS_FAILED', message='사진 분석에 실패했습니다. 원본과 상품 정보는 유지됩니다.')
                result.warnings = ['ANALYSIS_FAILED']
        finally:
            with self.lock:
                self.active = False

    def context(self, owner, job):
        """Future LLM integration must use this gate, not raw cached metadata."""
        result = self.get(owner, job)
        if not result.is_current or result.status != 'completed':
            return None
        return {'visual_hints': result.clip.cues, 'palette': result.palette.colors}
