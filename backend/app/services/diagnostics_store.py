"""Synchronous snapshot-bound diagnostics; no render slot or persistent job queue."""
from dataclasses import dataclass
from hashlib import sha256
import json
from app.schemas.diagnostics import DiagnosticsResponse
from app.schemas.rendering import RenderError
from app.services import diagnostics_engine as engine
from app.services.render_execution import opaque_png
from app.services.uploads import UploadError

@dataclass
class DiagnosticEntry:
    identity: str
    response: DiagnosticsResponse

class DiagnosticsStore:
    def __init__(self,renders,analyzer=None):
        self.renders=renders;self.uploads=renders.uploads
        self.analyzer=analyzer if analyzer is not None else engine.analyze
        self.busy={}

    def snapshot(self,owner,job):
        record,_,_,draft,copy,source_key=self.renders.snapshot(owner,job)
        render=self.renders.get(owner,job)
        if not copy or render.status!='completed' or not render.is_current:
            raise UploadError(409,'DIAGNOSTICS_RENDER_NOT_READY','최신 성공 광고를 먼저 생성해 주세요.')
        cs=render.candidates
        if (len(cs)!=4 or len({c.candidate_id for c in cs})!=4 or len({c.png.asset_id for c in cs})!=4
            or {c.strategy for c in cs}!={'emotional','price','visual','brand'}
            or any(c.revision!=render.revision or c.png.revision!=render.revision or c.facts!=draft.facts for c in cs)):
            raise UploadError(409,'DIAGNOSTICS_SOURCE_CHANGED','광고 후보 snapshot이 일치하지 않습니다.')
        hashes=[]
        for c in cs:
            if self.uploads.assets.get(c.png.asset_id)!=job:raise UploadError(409,'DIAGNOSTICS_ASSET_INVALID','광고 파일 소유 정보가 일치하지 않습니다.')
            try:
                data,mime=self.uploads.read_asset(owner,c.png.asset_id)
                opaque_png(data)
            except UploadError:raise
            except Exception:raise UploadError(409,'DIAGNOSTICS_ASSET_INVALID','광고 PNG가 손상됐거나 규격이 다릅니다.') from None
            value=sha256(data).hexdigest()
            if mime!='image/png' or value!=record.asset_hashes.get(c.png.asset_id):
                raise UploadError(409,'DIAGNOSTICS_ASSET_INVALID','광고 파일 내용이 변경됐습니다.')
            hashes.append(value)
        # Nonfinite metadata is fingerprinted, never emitted as a numeric result.
        key=sha256(json.dumps({'source':source_key,'render':render.model_dump(mode='python',by_alias=True),
            'hashes':hashes,'rules':engine.RULES_VERSION,'font':engine.SMALL_FONT_PX,'density':engine.DENSITY_LIMIT},
            ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
        return record,render,hashes,key

    def blank(self,job,record,status='pending',revision=None,is_current=False):
        return DiagnosticsResponse(job_id=job,status=status,revision=revision,is_current=is_current,
            rules_version=engine.RULES_VERSION,expires_at=record.upload.expires_at)

    def get(self,owner,job):
        with self.renders.locked():
            record=self.uploads.get(owner,job)
            entry=record.diagnostic_result
            active=self.busy.get(job)
            if not entry and not active:return self.blank(job,record)
            try:_,render,hashes,key=self.snapshot(owner,job)
            except UploadError as error:
                if error.code!='DIAGNOSTICS_RENDER_NOT_READY':raise
                key=None
            if active:
                return self.blank(job,record,'processing',active[1],active[0]==key)
            result=entry.response.model_copy(deep=True)
            result.is_current=key==entry.identity
            return result

    def run(self,owner,job,body):
        with self.renders.locked():
            record,render,hashes,key=self.snapshot(owner,job)
            expected={(c.candidate_id,c.asset_id) for c in body.expected_candidates}
            if body.expected_render_revision!=render.revision or expected!={(c.candidate_id,c.png.asset_id) for c in render.candidates}:
                raise UploadError(409,'DIAGNOSTICS_SOURCE_CHANGED','진단 대상 revision과 사진이 변경됐습니다. 다시 조회해 주세요.')
            entry=record.diagnostic_result
            if entry and entry.identity==key and entry.response.status=='completed':return self.get(owner,job)
            if job in self.busy:raise UploadError(503,'DIAGNOSTICS_BUSY','같은 작업의 진단이 진행 중입니다. 잠시 후 다시 조회해 주세요.')
            result=self.blank(job,record,'completed',render.revision,True)
            self.busy[job]=(key,render.revision)
        try:
            try:
                measurements=render.measurements if isinstance(render.measurements,dict) else {}
                result.results=[self.analyzer(c.model_dump(mode='python',by_alias=True),measurements.get(c.candidate_id),h)
                                for c,h in zip(render.candidates,hashes)]
                # Validate injected executors and prevent malformed/nonfinite output.
                result=DiagnosticsResponse.model_validate(result.model_dump(mode='python'))
                if len(result.results)!=4 or {(c.candidate_id,c.asset_id,c.strategy) for c in result.results}!={(c.candidate_id,c.png.asset_id,c.strategy) for c in render.candidates}:raise ValueError('Invalid diagnostics')
                if any(c.coverage!='complete' for c in result.results):result.warnings=['PARTIAL_OR_UNAVAILABLE_MEASUREMENTS']
            except Exception:
                result.status='failed';result.results=[]
                result.error=RenderError(code='DIAGNOSTICS_FAILED',message='진단하지 못했습니다. 광고·편집·다운로드는 유지됩니다. 다시 시도해 주세요.')
            with self.renders.locked():
                try:record,_,_,current=self.snapshot(owner,job)
                except UploadError as error:
                    if error.code=='DIAGNOSTICS_RENDER_NOT_READY':
                        raise UploadError(409,'DIAGNOSTICS_SOURCE_CHANGED','진단 중 입력·사진·카피가 변경됐습니다. 최신 광고를 다시 진단해 주세요.') from None
                    raise
                if current!=key:raise UploadError(409,'DIAGNOSTICS_SOURCE_CHANGED','진단 중 광고가 변경됐습니다. 최신 광고를 다시 진단해 주세요.')
                record.diagnostic_result=DiagnosticEntry(key,result)
                return result.model_copy(deep=True)
        finally:
            with self.renders.lock:self.busy.pop(job,None)
