"""Revision-authorized binary downloads; PDF failures never modify PNGs."""
import base64
from hashlib import sha256
import json
import os
import shutil
import subprocess
from threading import Lock
from urllib.parse import quote
from app.services.render_execution import ROOT, opaque_png
from app.services.uploads import UploadError

class PdfExecution:
    def __call__(self,png):
        proc=None
        try:
            node=shutil.which('node') or (r'C:\Program Files\nodejs\node.exe' if os.name=='nt' else 'node')
            proc=subprocess.Popen([node,str(ROOT/'scripts/service_pdf_worker.mjs')],cwd=ROOT,
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,start_new_session=os.name!='nt')
            out,_=proc.communicate(json.dumps({'png':base64.b64encode(png).decode()}).encode(),timeout=90)
            result=json.loads(out)
            if proc.returncode or result.get('error'):raise ValueError('PDF failed')
            pdf=base64.b64decode(result['pdf'],validate=True)
            if not pdf.startswith(b'%PDF-'):raise ValueError('PDF failed')
            return pdf
        except Exception:
            raise UploadError(503,'PDF_FAILED','PDF를 만들지 못했습니다. PNG는 유지됩니다. 다시 시도해 주세요.') from None
        finally:
            if proc is not None:
                try:
                    if proc.poll() is None:
                        if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=5)
                        else:
                            import signal
                            os.killpg(proc.pid,signal.SIGKILL)
                        proc.communicate(timeout=5)
                except Exception:
                    # Cleanup failures must never replace the safe public error.
                    try:proc.kill()
                    except Exception:pass

class ExportService:
    def __init__(self,renders,pdf=None):
        self.renders=renders;self.uploads=renders.uploads
        self.pdf=pdf if pdf is not None else PdfExecution()
        self.pdf_lock=Lock()

    def snapshot(self,owner,job,candidate_id,revision):
        record=self.uploads.get(owner,job)
        render=self.renders.get(owner,job)
        if render.status!='completed' or not render.is_current or render.revision!=revision:
            raise UploadError(409,'DOWNLOAD_SOURCE_CHANGED','최신 성공 광고를 다시 조회한 뒤 다운로드해 주세요.')
        candidate=next((c for c in render.candidates if c.candidate_id==candidate_id),None)
        if not candidate:raise UploadError(404,'RESOURCE_NOT_FOUND','광고를 찾을 수 없습니다.')
        if self.uploads.assets.get(candidate.png.asset_id)!=job:
            raise UploadError(409,'DOWNLOAD_ASSET_INVALID','광고 파일 정보가 일치하지 않습니다.')
        data,mime=self.uploads.read_asset(owner,candidate.png.asset_id)
        try:opaque_png(data)
        except Exception:raise UploadError(409,'DOWNLOAD_ASSET_INVALID','광고 파일이 손상됐습니다.') from None
        if mime!='image/png' or sha256(data).hexdigest()!=record.asset_hashes.get(candidate.png.asset_id):
            raise UploadError(409,'DOWNLOAD_ASSET_INVALID','광고 파일이 변경됐습니다.')
        return record,candidate,data

    def download(self,owner,job,candidate_id,revision,format):
        with self.renders.locked():
            record,candidate,data=self.snapshot(owner,job,candidate_id,revision)
            key=(candidate_id,revision,sha256(data).hexdigest())
            cached=record.exports.get(key)
        if format=='pdf':
            if cached is None:
                if not self.pdf_lock.acquire(blocking=False):
                    raise UploadError(503,'PDF_BUSY','다른 PDF를 생성 중입니다. 잠시 후 다시 시도해 주세요.')
                try:
                    cached=self.pdf(data)
                except UploadError:
                    raise
                except Exception:
                    raise UploadError(503,'PDF_FAILED','PDF를 만들지 못했습니다. PNG는 유지됩니다.') from None
                finally:self.pdf_lock.release()
            with self.renders.locked():
                record,_,latest=self.snapshot(owner,job,candidate_id,revision)
                if sha256(latest).hexdigest()!=key[2]:raise UploadError(409,'DOWNLOAD_SOURCE_CHANGED','광고가 변경됐습니다.')
                record.exports={k:v for k,v in record.exports.items() if k[1]==revision}
                record.exports[key]=cached
            data=cached
        fallback=f'hanjang-{candidate.strategy}-r{revision}.{format}'
        localized=quote(f'한장-{candidate.strategy}-r{revision}.{format}')
        return data,'image/png' if format=='png' else 'application/pdf',f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{localized}'
