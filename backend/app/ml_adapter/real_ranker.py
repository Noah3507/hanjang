"""A-owned subprocess boundary. The service environment never imports B/torch."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
from threading import RLock, Thread
import uuid
import re
import time
from hashlib import sha256
from app.schemas.ranking import Ranking


class RankFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class RealRanker:
    mode = 'model'

    def __init__(self, python: Path, model_file: Path | None, temp_root: Path, timeout=30):
        self.python, self.model_file = Path(python), model_file
        self.temp_root, self.timeout = Path(temp_root).resolve(), timeout
        self.process = None
        self.lock = RLock()
        self.last_metrics = {}

    def cache_token(self):
        try:
            paths=sorted((str(p.relative_to(self.model_file.parent)),p.stat().st_size,p.stat().st_mtime_ns)
                for p in self.model_file.parent.rglob('*') if p.is_file()) if self.model_file else []
            manifest=self.model_file.parent/'manifest.json' if self.model_file else None
            data=manifest.read_bytes() if manifest and manifest.is_file() else b''
            return sha256(json.dumps(paths).encode()+data).hexdigest()
        except OSError:
            return 'unavailable'

    def close(self):
        with self.lock:
            if self.process:
                if self.process.poll() is None:
                    if os.name == 'nt':
                        subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
                    if self.process.poll() is None: self.process.kill()
                self.process.wait(timeout=10)
                self.process.stdin.close(); self.process.stdout.close()
                self.process = None

    def cleanup_expired(self):
        # Never touch legacy/unmarked directories or an active inference snapshot.
        if not self.lock.acquire(blocking=False):return
        try:
            if not self.temp_root.is_dir():return
            for folder in self.temp_root.iterdir():
                if (not re.fullmatch(r'ranking-[a-z0-9_]{8}',folder.name) or folder.is_symlink()
                    or not folder.is_dir() or folder.resolve().parent!=self.temp_root
                    or time.time()-folder.stat().st_mtime<86400):continue
                marker=folder/'.hanjang-snapshot'
                if marker.is_symlink() or not marker.is_file() or marker.read_bytes()!=b'owned-snapshot-v1':continue
                children=list(folder.iterdir())
                if any(p.is_symlink() or not p.is_file() or p.name not in {'.hanjang-snapshot','0.png','1.png','2.png','3.png'} for p in children):continue
                for path in children:
                    if path!=marker:path.unlink()
                marker.unlink()
                folder.rmdir()
        finally:self.lock.release()

    def rank_snapshot(self, candidates, revision, pngs):
        with self.lock:
            if not self.model_file or not self.model_file.is_file():
                self.close()
                raise RankFailure('RANKING_MODEL_UNAVAILABLE')
            if not self.python.is_file(): raise RankFailure('RANKING_ENV_UNAVAILABLE')
            self.temp_root.mkdir(parents=True,exist_ok=True)
            # These immutable private copies bind inference to the bytes checked at POST.
            # Cleanup is limited to the newly created owned TemporaryDirectory.
            with tempfile.TemporaryDirectory(prefix='ranking-',dir=self.temp_root) as folder:
                (Path(folder)/'.hanjang-snapshot').write_bytes(b'owned-snapshot-v1')
                items=[]
                for index,candidate in enumerate(candidates):
                    path=Path(folder)/f'{index}.png'
                    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as stream:
                        stream.write(pngs[candidate.candidate_id])
                    items.append({'candidate_id':candidate.candidate_id,'rendered_image_path':str(path)})
                try:
                    if self.process is None or self.process.poll() is not None:
                        self.close()
                        repo=Path(__file__).resolve().parents[3]
                        env=os.environ.copy()
                        env.update(PYTHONPATH=str(repo)+os.pathsep+str(repo/'backend'),
                            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
                        self.process=subprocess.Popen([str(self.python),'-m','app.ml_adapter.ranking_worker',
                            str(self.model_file),str(self.temp_root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,env=env,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    ticket=uuid.uuid4().hex
                    self.process.stdin.write((json.dumps({'request_id':ticket,'items':items})+'\n').encode())
                    self.process.stdin.flush()
                    replies=queue.Queue();stream=self.process.stdout
                    def read():
                        try: replies.put(stream.readline())
                        except Exception: replies.put(b'')
                    reader=Thread(target=read,daemon=True);reader.start()
                    try: raw=replies.get(timeout=self.timeout)
                    except queue.Empty:
                        raise RankFailure('RANKING_TIMEOUT') from None
                    body=json.loads(raw)
                    if body.get('request_id')!=ticket: raise RankFailure('RANKING_OUTPUT_INVALID')
                    if body.get('error'):
                        allowed={'RANKING_MODEL_UNAVAILABLE','RANKING_ARTIFACT_INVALID','RANKING_IMAGE_INVALID','RANKING_INFERENCE_FAILED'}
                        raise RankFailure(body['error'] if body['error'] in allowed else 'RANKING_INFERENCE_FAILED')
                    output=body['result']
                    if [i['candidate_id'] for i in output['items']] != [c.candidate_id for c in candidates]:
                        raise RankFailure('RANKING_OUTPUT_INVALID')
                    result=Ranking.model_validate(dict(output,source='model',revision=revision,
                        items=sorted(output['items'],key=lambda i:i['rank'])))
                    self.last_metrics=body.get('metrics',{})
                    return result
                except Exception as error:
                    self.close()
                    if isinstance(error,RankFailure): raise
                    raise RankFailure('RANKING_OUTPUT_INVALID') from None
