"""Transactional edits, preserving source copies and last successful four-PNG set."""
from hashlib import sha256
from dataclasses import dataclass
import os
import uuid
from app.schemas.editing import EditResponse
from app.schemas.rendering import RenderError, TextBox, Box
from app.services.copy_store import digest
from app.services.copy_glyphs import supported_text
from app.services.render_execution import RenderFailure, opaque_png, rgb
from app.services.uploads import UploadError

@dataclass
class EditEntry:
    source_key: str
    response: EditResponse
    request_key: str

class EditorStore:
    def __init__(self, renders):
        self.renders = renders
        self.uploads = renders.uploads

    def get(self, owner, job):
        with self.renders.locked():
            record, _, _, _, _, key = self.renders.snapshot(owner, job)
            entry = record.edits.get(record.last_edit)
            if not entry:
                return EditResponse(job_id=job, status_url=f'/api/v1/jobs/{job}/editing', expires_at=record.upload.expires_at)
            result = entry.response.model_copy(deep=True)
            render = self.renders.get(owner, job)
            result.is_current = (entry.source_key == key and render.is_current and
                (result.status == 'completed' and render.revision == result.target_revision or
                 result.status != 'completed' and render.revision == result.base_revision))
            return result

    def start(self, owner, job, candidate_id, body):
        with self.renders.locked():
            record, photo, asset, draft, copy, key = self.renders.snapshot(owner, job)
            request_key = digest({'source':key, 'candidate':candidate_id,'request':body.model_dump(mode='json',by_alias=True)})
            cached = record.edits.get(request_key)
            current = self.renders.get(owner, job)
            # Retry of a completed PATCH may legitimately carry its old base revision.
            if cached and cached.response.status in ('processing','completed') and cached.source_key == key:
                expected = cached.response.target_revision if cached.response.status == 'completed' else cached.response.base_revision
                if current.is_current and current.revision == expected:
                    record.last_edit=request_key
                    return self.get(owner,job), None
            if (not copy or not current.is_current or current.status != 'completed' or
                body.expected_revision != current.revision or body.expected_asset_id != asset.asset_id or
                body.expected_copy_key != copy.copy_key or body.expected_input != draft or
                set(body.expected_candidate_ids) != {c.candidate_id for c in current.candidates}):
                raise UploadError(409,'EDIT_SOURCE_CHANGED','광고·입력·사진이 변경됐습니다. 최신 성공본을 다시 조회해 주세요.')
            candidate = next((c for c in current.candidates if c.candidate_id == candidate_id),None)
            if not candidate:
                raise UploadError(404,'RESOURCE_NOT_FOUND','광고를 찾을 수 없습니다.')
            if not all(supported_text(t) for t in body.ad_copy.model_dump().values()):
                raise UploadError(422,'EDIT_UNSUPPORTED_GLYPH','지원하지 않는 문자나 이모지가 있습니다. 원문 광고는 유지됩니다.')
            if photo.status == 'processing':
                raise UploadError(409,'PHOTO_PROCESSING_BUSY','사진 처리 완료 후 편집해 주세요.')
            if self.renders.active:
                raise UploadError(409,'EDIT_BUSY','다른 렌더링·편집 작업이 진행 중입니다.')
            edit_id=uuid.uuid4().hex
            target=max([r.revision for r in [*record.renders.values(),*record.edited_renders.values()]]+
                       [e.response.target_revision or 0 for e in record.edits.values()])+1
            response=EditResponse(job_id=job,status='processing',status_url=f'/api/v1/jobs/{job}/editing',
                edit_id=edit_id,candidate_id=candidate_id,base_revision=current.revision,target_revision=target,
                is_current=True,expires_at=record.upload.expires_at)
            # No change: acknowledge without any Chromium execution or new revision.
            if candidate.ad_copy == body.ad_copy:
                response.status='completed';response.target_revision=current.revision
            if response.status == 'completed':
                record.edits[request_key]=EditEntry(key,response,request_key);record.last_edit=request_key
                return self.get(owner,job),None
            source,_=self.uploads.read_asset(owner,asset.asset_id)
            if sha256(source).hexdigest()!=asset.sha256:
                raise UploadError(409,'EDIT_ASSET_INVALID','선택 사진이 변경됐습니다. 사진을 다시 확인해 주세요.')
            for c in current.candidates:
                png,mime=self.uploads.read_asset(owner,c.png.asset_id)
                if mime!='image/png':raise UploadError(409,'EDIT_ASSET_INVALID','광고 PNG를 다시 생성해 주세요.')
                try:opaque_png(png)
                except Exception:raise UploadError(409,'EDIT_ASSET_INVALID','광고 PNG가 손상됐습니다.') from None
                if sha256(png).hexdigest()!=record.asset_hashes.get(c.png.asset_id):
                    raise UploadError(409,'EDIT_ASSET_INVALID','광고 PNG가 변경됐습니다. 다시 생성해 주세요.')
            edited_copy=copy.model_copy(deep=True)
            for v in edited_copy.variants:
                v.ad_copy = next(c.ad_copy.model_copy(deep=True) for c in current.candidates if c.strategy==v.strategy)
            for v in edited_copy.variants:
                if v.strategy==candidate.strategy:v.ad_copy=body.ad_copy.model_copy(deep=True)
            self.renders.active=True
            record.edits[request_key]=EditEntry(key,response,request_key);record.last_edit=request_key
            # Do not re-read TTL after reserving the renderer slot. If expiry
            # occurs now, finish() owns cleanup and always releases the slot.
            return response.model_copy(deep=True),(request_key,current.model_copy(deep=True),draft,edited_copy,source,candidate_id)

    def finish(self,owner,job,task):
        request_key,base,draft,edited_copy,source,candidate_id=task
        path=None
        try:
            # Only changed strategy is rendered by the real renderer.
            selected=next(c for c in base.candidates if c.candidate_id==candidate_id)
            partial=edited_copy.model_copy(deep=True)
            partial.variants=[v for v in partial.variants if v.strategy==selected.strategy]
            results=self.renders.executor(draft,partial,source)
            if len(results)!=1 or results[0]['strategy']!=selected.strategy:raise RenderFailure('RENDER_INVALID_RESULT')
            result=results[0]; png=opaque_png(result['png'])
            with self.renders.locked():
                record,_,_,_,_,key=self.renders.snapshot(owner,job)
                entry=record.edits[request_key];current=self.renders.get(owner,job)
                if key!=entry.source_key or not current.is_current or current.revision!=base.revision:
                    raise RenderFailure('EDIT_SOURCE_CHANGED')
                # Verify original and unchanged asset bytes again before publication.
                for c in base.candidates:
                    old,mime=self.uploads.read_asset(owner,c.png.asset_id)
                    if mime!='image/png':raise RenderFailure('EDIT_ASSET_INVALID')
                    opaque_png(old)
                    if sha256(old).hexdigest()!=record.asset_hashes.get(c.png.asset_id):raise RenderFailure('EDIT_ASSET_INVALID')
                selected_bytes,_=self.uploads.read_asset(owner,base.source_asset_id)
                if sha256(selected_bytes).hexdigest()!=sha256(source).hexdigest():raise RenderFailure('EDIT_ASSET_INVALID')
                asset=uuid.uuid4().hex;path=self.uploads.safe_path(asset+'.png')
                with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(png)
                stamp=record.upload.created_at.timestamp();os.utime(path,(stamp,stamp))
                self.uploads.get(owner,job)  # TTL can elapse while bytes are written.
                next_render=base.model_copy(deep=True);revision=entry.response.target_revision
                next_render.revision=revision
                for c in next_render.candidates:
                    c.revision=revision;c.png.revision=revision
                    if c.candidate_id==candidate_id:
                        c.ad_copy=next(v.ad_copy for v in edited_copy.variants if v.strategy==c.strategy)
                        c.png.asset_id=asset;c.png.url=f'/api/v1/assets/{asset}'
                        measurement=result['measurement']
                        boxes=[]
                        for raw in measurement['text']:
                            b={k:v for k,v in raw.items() if k not in ('line_count','font_family','actual_fonts')}
                            b['foreground']=rgb(b['foreground']);b['background']=None if b['background'].endswith(', 0)') else rgb(b['background'])
                            boxes.append(b)
                        c.renderer.text_boxes=[TextBox.model_validate(b) for b in boxes]
                        c.renderer.product_bbox=Box.model_validate(measurement['product'])
                        next_render.measurements[candidate_id]=measurement
                record.derived[asset]=path;self.uploads.assets[asset]=job
                record.asset_hashes[asset]=sha256(png).hexdigest()
                record.edited_renders[key]=next_render
                entry.response.status='completed';entry.response.is_current=True
        except Exception as error:
            if path:path.unlink(missing_ok=True)
            with self.renders.locked():
                try:record=self.uploads.get(owner,job)
                except UploadError:return
                entry=record.edits[request_key]
                entry.response.status='failed'
                entry.response.error=RenderError(code=error.code if isinstance(error,RenderFailure) else 'EDIT_FAILED',
                    message='광고를 적용하지 못했습니다. 마지막 성공본은 유지됩니다. 최신 상태를 확인한 뒤 다시 시도해 주세요.')
        finally:
            with self.renders.lock:self.renders.active=False
