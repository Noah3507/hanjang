"""Session-owned strategy sets with atomic rendering, edit and snapshot fencing."""
from dataclasses import dataclass, field, replace
from hashlib import sha256
import os
from uuid import uuid4
from threading import Lock
from app.schemas.designs import DesignResponse, DesignCandidate
from app.schemas.rendering import RenderError
from app.schemas.ranking import Ranking
from app.schemas.copy import Copy
from app.schemas.diagnostics import CandidateDiagnostics
from app.services.template_v3 import TemplateInput, VERSION, REGISTRY, render_templates, measured_diagnostics
from app.services.render_execution import opaque_png, rgb, RenderFailure
from app.services.copy_store import digest
from app.services.copy_glyphs import supported_text
from app.services.template_v3_claims import amount
from app.services.export_service import PdfExecution
from app.services.uploads import UploadError
from app.ml_adapter.mock_ranker import ordered_items


@dataclass
class DesignEntry:
    source_key: str
    response: DesignResponse
    inputs: dict = field(default_factory=dict)
    measurements: dict = field(default_factory=dict)
    edit_ticket: str | None = None
    ranking_token: str | None = None


class DesignStore:
    def __init__(self, renders, ranker):
        self.renders, self.uploads, self.ranker = renders, renders.uploads, ranker
        self.executor = render_templates
        self.pdf = PdfExecution()
        self.pdf_lock = Lock()

    def context(self, owner, job):
        record, photo, asset, draft, copy, _ = self.renders.snapshot(owner,job)
        source = self.renders.get(owner,job)
        key = digest({'v2':source.model_dump(mode='json',exclude={'measurements'}), 'version':VERSION,
                      'asset_hash':asset.sha256})
        return record,asset,draft,copy,source,key

    def check_ready(self, source):
        if source.status!='completed' or not source.is_current:
            raise UploadError(409,'V3_SOURCE_CHANGED','최신 4전략 광고를 먼저 생성해 주세요.')

    def get(self, owner, job, strategy):
        with self.renders.locked():
            record,asset,_,copy,source,key=self.context(owner,job)
            entry=record.design_sets.get(strategy)
            if not entry:
                return DesignResponse(job_id=job,strategy=strategy,status='pending',source_revision=source.revision,
                    source_asset_id=asset.asset_id,copy_key=copy.copy_key if copy else None,
                    template_version=VERSION,mock_copy=copy.provider=='mock' if copy else True,expires_at=record.upload.expires_at)
            result=entry.response.model_copy(deep=True)
            result.editing=entry.edit_ticket is not None
            result.is_current=source.is_current and source.status=='completed' and entry.source_key==key
            if not result.is_current:
                result.ranking=None
            elif result.ranking is not None and entry.ranking_token != self.ranker_token():
                result.ranking=None;result.ranking_status='pending'
            elif result.status=='completed':
                for c in result.candidates:self.asset(owner,job,record,c)
            return result

    def start(self, owner, job, strategy, body):
        with self.renders.locked():
            record,asset,draft,copy,source,key=self.context(owner,job)
            self.check_ready(source)
            if (source.revision!=body.expected_render_revision or asset.asset_id!=body.expected_source_asset_id
                or not copy or copy.copy_key!=body.expected_copy_key):
                raise UploadError(409,'V3_SOURCE_CHANGED','원본 광고가 변경됐습니다. 최신 상태를 다시 조회해 주세요.')
            old=record.design_sets.get(strategy)
            commercial=body.promotion.model_dump()
            if old and old.source_key==key and old.response.status in ('completed','processing'):
                if any(getattr(next(iter(old.inputs.values())),k)!=v for k,v in commercial.items()):
                    raise UploadError(409,'V3_PROMOTION_CHANGED','기존 행사 정보를 보존하고 있습니다. 변경한 상품 정보로 광고를 다시 생성해 주세요.')
                return self.get(owner,job,strategy),None
            if self.renders.active:
                raise UploadError(503,'RENDER_BUSY','다른 광고 처리 중입니다. 잠시 후 이 전략을 다시 요청해 주세요.')
            selected=next(c for c in source.candidates if c.strategy==strategy)
            data=TemplateInput(draft.facts.store_name,draft.facts.product_name,draft.facts.price_text,
                selected.ad_copy.headline,selected.ad_copy.body,selected.ad_copy.cta,**commercial)
            try:data.validate()
            except RenderFailure as e:raise UploadError(422,e.code,'가격·할인율·통화·행사 기간을 확인해 주세요.') from None
            raw,_=self.uploads.read_asset(owner,asset.asset_id)
            if sha256(raw).hexdigest()!=asset.sha256:
                raise UploadError(409,'V3_ASSET_CHANGED','선택 사진이 변경됐습니다.')
            revision=(old.response.revision if old else 0)+1
            response=DesignResponse(job_id=job,strategy=strategy,status='processing',revision=revision,
                source_revision=source.revision,source_asset_id=asset.asset_id,copy_key=copy.copy_key,
                template_version=VERSION,is_current=True,mock_copy=source.mock_copy,expires_at=record.upload.expires_at)
            response.promotion=body.promotion.model_copy(deep=True)
            entry=DesignEntry(key,response,{f'{strategy}_{c}':data for c in 'abcd'})
            record.design_sets[strategy]=entry
            def abandoned():
                response.status='failed';response.error=RenderError(code='V3_DISPATCH_FAILED',message='작업이 시작되지 않았습니다. 다시 시도해 주세요.')
            lease=self.renders.slot.reserve(abandoned)
            return self.get(owner,job,strategy),(strategy,entry,raw,draft,lease,None)

    def identity(self, response):
        return digest({'source':response.source_asset_id,'copy':response.copy_key,'revision':response.revision,
            'version':response.template_version,'candidates':[c.model_dump(mode='json',by_alias=True) for c in response.candidates]})

    def current(self,owner,job,strategy,body):
        response=self.get(owner,job,strategy)
        if (response.status!='completed' or not response.is_current or body.expected_revision!=response.revision
            or body.expected_snapshot!=response.snapshot):
            raise UploadError(409,'V3_SOURCE_CHANGED','시안이 변경됐습니다. 최신 결과를 다시 조회해 주세요.')
        record=self.uploads.get(owner,job)
        for c in response.candidates:
            self.asset(owner,job,record,c)
        return record,record.design_sets[strategy],response

    def asset(self,owner,job,record,candidate):
        asset=candidate.png.asset_id
        if self.uploads.assets.get(asset)!=job or asset not in record.derived:
            raise UploadError(404,'RESOURCE_NOT_FOUND','광고 파일에 접근할 수 없습니다.')
        data,mime=self.uploads.read_asset(owner,asset)
        try:
            opaque_png(data)
            if mime!='image/png' or sha256(data).hexdigest()!=record.asset_hashes.get(asset):raise ValueError()
        except Exception:raise UploadError(409,'V3_ASSET_CHANGED','광고 파일을 다시 생성해 주세요.') from None
        return data

    def edit(self,owner,job,strategy,candidate_id,body):
        with self.renders.locked():
            record,entry,current=self.current(owner,job,strategy,body)
            candidate=next((c for c in current.candidates if c.candidate_id==candidate_id),None)
            if not candidate:raise UploadError(404,'RESOURCE_NOT_FOUND','시안을 찾을 수 없습니다.')
            if body.expected_asset_id!=candidate.png.asset_id:raise UploadError(409,'V3_SOURCE_CHANGED','이미지가 변경됐습니다.')
            if self.renders.active:raise UploadError(409,'EDIT_BUSY','다른 렌더링이 진행 중입니다.')
            if not all(supported_text(t) for t in [*body.ad_copy.model_dump().values(),body.price_text]):
                raise UploadError(422,'EDIT_UNSUPPORTED_GLYPH','지원하지 않는 문자입니다.')
            if not body.price_text.strip():raise UploadError(422,'V3_PRICE_REQUIRED','가격 비공개인 경우 가격 비공개라고 입력해 주세요.')
            data=replace(entry.inputs[candidate.template_id],**body.ad_copy.model_dump(),price_text=body.price_text)
            # A price change cannot silently preserve a claim/copy for the old price.
            if body.price_text!=candidate.facts.price_text:
                compact=lambda value:''.join(value.split())
                if compact(candidate.facts.price_text) in compact(' '.join(body.ad_copy.model_dump().values())):
                    raise UploadError(422,'V3_PRICE_COPY_CONFLICT','문구에 남은 이전 가격도 직접 수정해 주세요.')
                if body.price_text not in {'가격 비공개','가격 문의','별도 문의'}:
                    try:
                        value,_=amount(body.price_text)
                        if value<0:raise ValueError()
                    except (RenderFailure,ValueError):
                        raise UploadError(422,'V3_PRICE_REVIEW_REQUIRED','금액과 통화를 확인해 주세요. 원문을 자동 변환하지 않습니다.') from None
            try:data.validate()
            except RenderFailure as e:raise UploadError(422,e.code,'가격과 기존 할인 정보의 정합성을 확인해 주세요.') from None
            _,asset,draft,_,_,_=self.context(owner,job)
            raw,_=self.uploads.read_asset(owner,asset.asset_id)
            if sha256(raw).hexdigest()!=asset.sha256:raise UploadError(409,'V3_ASSET_CHANGED','선택 사진이 변경됐습니다.')
            ticket=uuid4().hex;entry.edit_ticket=ticket
            def abandoned():entry.edit_ticket=None
            lease=self.renders.slot.reserve(abandoned)
            next_entry=DesignEntry(entry.source_key,current.model_copy(deep=True),{**entry.inputs,candidate.template_id:data},dict(entry.measurements),ticket)
            next_entry.response.status='processing'
            return next_entry.response,(strategy,next_entry,raw,draft,lease,(candidate_id,current.snapshot,ticket))

    def finish(self,owner,job,task):
        strategy,entry,raw,draft,lease,edit=task
        with self.renders.locked():
            if not self.renders.slot.claim(lease):return
        written=[]
        try:
            ids=[next(c.template_id for c in entry.response.candidates if c.candidate_id==edit[0])] if edit else list(entry.inputs)
            results=self.executor(entry.inputs[ids[0]],raw,ids)
            if [r['template_id'] for r in results]!=ids:raise RenderFailure('RENDER_INVALID_RESULT')
            with self.renders.locked():
                if not self.renders.slot.owns(lease):return
                record,asset,_,_,source,key=self.context(owner,job)
                if key!=entry.source_key or not source.is_current:raise RenderFailure('V3_SOURCE_CHANGED')
                if edit:
                    old=record.design_sets[strategy]
                    if old.response.snapshot!=edit[1] or old.edit_ticket!=edit[2]:raise RenderFailure('V3_SOURCE_CHANGED')
                    for c in old.response.candidates:self.asset(owner,job,record,c)
                else:
                    if record.design_sets.get(strategy) is not entry:raise RenderFailure('V3_SOURCE_CHANGED')
                current_raw,_=self.uploads.read_asset(owner,asset.asset_id)
                if sha256(current_raw).hexdigest()!=sha256(raw).hexdigest():raise RenderFailure('V3_ASSET_CHANGED')
                response=entry.response.model_copy(deep=True)
                response.revision += 1 if edit else 0
                candidates=list(response.candidates) if edit else []
                for result in results:
                    png=opaque_png(result['png']);asset_id=uuid4().hex;path=self.uploads.safe_path(asset_id+'.png')
                    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
                        written.append((asset_id,path));f.write(png)
                    stamp=record.upload.created_at.timestamp();os.utime(path,(stamp,stamp))
                    tid=result['template_id'];data=entry.inputs[tid];m=result['measurement'];old=next((c for c in candidates if c.template_id==tid),None)
                    boxes=[]
                    for t in m['text']:
                        box={k:t[k] for k in ('x','y','width','height','field','text','font_size_px','font_weight','overflow')}
                        box.update(foreground=rgb(t['foreground']),background=None);boxes.append(box)
                    c=DesignCandidate(candidate_id=old.candidate_id if old else uuid4().hex,strategy=strategy,revision=response.revision,
                        facts=draft.facts.model_copy(update={'price_text':data.price_text}),copy=Copy(headline=data.headline,body=data.body,cta=data.cta),
                        png={'asset_id':asset_id,'url':f'/api/v1/assets/{asset_id}','revision':response.revision},
                        renderer={'template_version':tid+'-'+VERSION,'text_boxes':boxes,'product_bbox':m['product'],
                            'photo_sha256':record.upload.sha256,'processed_photo_sha256':sha256(raw).hexdigest()},
                        template_id=tid,design_name=REGISTRY[tid]['name'],generation_revision=old.generation_revision if old else response.revision,
                        edit_revision=old.edit_revision+1 if old else 0,original_price_text=draft.facts.price_text)
                    candidates=[c if x.template_id==tid else x for x in candidates] if old else [*candidates,c]
                    entry.measurements[c.candidate_id]=m
                for c in candidates:c.revision=response.revision;c.png.revision=response.revision
                if len(candidates)!=4 or len({c.candidate_id for c in candidates})!=4:raise RenderFailure('RENDER_INVALID_RESULT')
                self.uploads.get(owner,job)
                response.candidates=candidates;response.status='completed';response.error=None;response.is_current=True
                response.failed_templates=[];response.failed_fields=[]
                response.ranking=None;response.ranking_status='pending';response.ranking_error=None
                hashes={a:sha256(p.read_bytes()).hexdigest() for a,p in written}
                response.diagnostics=[CandidateDiagnostics.model_validate(measured_diagnostics(c.candidate_id,c.png.asset_id,strategy,entry.measurements[c.candidate_id],
                    hashes.get(c.png.asset_id) or record.asset_hashes[c.png.asset_id])) for c in candidates]
                response.snapshot=self.identity(response)
                response.warnings=['SAME_STRATEGY_MODEL_NOT_VALIDATED','CHECK_DIAGNOSTICS_SEPARATELY']
                completed=DesignEntry(entry.source_key,response,entry.inputs,entry.measurements)
                self.renders.publish(record,job,written,hashes,design_sets={**record.design_sets,strategy:completed})
        except BaseException as e:
            for _,p in written:
                try:p.unlink(missing_ok=True)
                except OSError:pass
            with self.renders.locked():
                try:
                    record=self.uploads.get(owner,job);live=record.design_sets.get(strategy)
                    if live:
                        live.edit_ticket=None
                        evidence=getattr(e,'measurement',None) or {}
                        tid=evidence.get('template_id')
                        live.response.failed_templates=[tid] if tid in REGISTRY else []
                        live.response.failed_fields=[t['field'] for t in evidence.get('text',[]) if t.get('overflow') and t.get('field') in TemplateInput.__dataclass_fields__]
                        live.response.error=RenderError(code=e.code if isinstance(e,RenderFailure) else 'V3_RENDER_FAILED',
                            message='시안을 적용하지 못했습니다. 마지막 성공본을 유지합니다. 문구 길이와 최신 상태를 확인해 주세요.')
                        if not edit:live.response.status='failed'
                except UploadError:pass
            if not isinstance(e,Exception):raise
        finally:
            with self.renders.lock:self.renders.slot.release(lease)

    def rank(self,owner,job,strategy,body):
        with self.renders.locked():
            record,entry,response=self.current(owner,job,strategy,body)
            token=self.ranker_token()
            if response.ranking_status=='processing':raise UploadError(409,'RANKING_BUSY','모델 평가가 진행 중입니다.')
            entry.response.ranking_status='processing';entry.response.ranking=None
            pngs={c.candidate_id:self.asset(owner,job,record,c) for c in response.candidates}
        try:
            if getattr(self.ranker,'mode','mock')=='model':
                result=self.ranker.rank_snapshot(response.candidates,response.revision,pngs)
            else:
                # Explicit development mode only. No fake strategy remapping.
                result=Ranking(source='mock',model_version='mock-v1',feature_version=None,revision=response.revision,
                    items=ordered_items([(c.candidate_id,0.) for c in response.candidates]))
            result=Ranking.model_validate(result.model_dump(mode='json'))
            if getattr(self.ranker,'mode','mock')=='model' and result.source!='model':
                raise ValueError('Actual model required')
            if {i.candidate_id for i in result.items}!={c.candidate_id for c in response.candidates} or result.revision!=response.revision:
                raise ValueError('Invalid mapping')
            with self.renders.locked():
                _,live,current=self.current(owner,job,strategy,body)
                if token!=self.ranker_token():raise ValueError('Model changed')
                live.response.ranking=result;live.response.ranking_status='completed';live.response.ranking_error=None
                live.ranking_token=token
                return self.get(owner,job,strategy)
        except Exception as e:
            with self.renders.locked():
                try:
                    record=self.uploads.get(owner,job);live=record.design_sets[strategy]
                    if live.response.snapshot==response.snapshot:
                        live.response.ranking=None;live.response.ranking_status='failed'
                        live.response.ranking_error=RenderError(code=getattr(e,'code','V3_RANKING_FAILED'),message='모델 평가를 완료하지 못했습니다. 광고·편집·다운로드는 유지됩니다. 자동 Mock 대체는 없습니다.')
                except (UploadError,KeyError):pass
            if isinstance(e,UploadError):raise
            return self.get(owner,job,strategy)

    def download(self,owner,job,strategy,candidate_id,body,format):
        with self.renders.locked():
            record,entry,response=self.current(owner,job,strategy,body)
            c=next((c for c in response.candidates if c.candidate_id==candidate_id),None)
            if not c:raise UploadError(404,'RESOURCE_NOT_FOUND','시안을 찾을 수 없습니다.')
            png=self.asset(owner,job,record,c)
        if format=='pdf':
            if not self.pdf_lock.acquire(blocking=False):raise UploadError(503,'PDF_BUSY','다른 PDF가 처리 중입니다. 잠시 후 다시 시도해 주세요.')
            try:data=self.pdf(png)
            finally:self.pdf_lock.release()
        else:data=png
        with self.renders.locked():self.current(owner,job,strategy,body)
        return data,'application/pdf' if format=='pdf' else 'image/png',f'hanjang-{c.template_id}-r{c.revision}.{format}'

    def ranker_token(self):
        return self.ranker.cache_token() if hasattr(self.ranker,'cache_token') else getattr(self.ranker,'mode','mock')
