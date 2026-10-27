"""Single serialized reusable worker, hard timeout and bounded idle lifetime."""
import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import uuid

class AnalysisExecution:
    def __init__(self, python: Path, model: Path, timeout=120., idle=300.):
        self.python, self.model, self.timeout, self.idle = python, model, timeout, idle
        self.process = None
        self.lock = threading.RLock()
        self.timer = None

    def close(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            if self.process:
                if self.process.poll() is None:
                    # Windows venv python.exe is a launcher: kill its owned child too.
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                    if self.process.poll() is None:
                        self.process.kill()
                self.process.wait()
                self.process.stdin.close()
                self.process.stdout.close()
                self.process = None

    def __call__(self, data):
        with self.lock:
            if not self.model.is_file():
                return {'clip': {'status': 'unavailable'}, 'warning': 'ANALYSIS_MODEL_UNAVAILABLE'}
            if not self.python.is_file():
                return {'clip': {'status': 'unavailable'}, 'warning': 'ANALYSIS_ENV_UNAVAILABLE'}
            if self.timer:
                self.timer.cancel()
            try:
                if self.process is None or self.process.poll() is not None:
                    self.close()
                    env = os.environ.copy()
                    env.update(PYTHONPATH=str(Path(__file__).resolve().parents[2]), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONUTF8='1')
                    self.process = subprocess.Popen([str(self.python), '-m', 'app.services.analysis_worker', str(self.model)],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                ticket = uuid.uuid4().hex
                self.process.stdin.write((json.dumps({'request_id': ticket, 'data': base64.b64encode(data).decode()})+'\n').encode())
                self.process.stdin.flush()
                replies = queue.Queue()
                stream = self.process.stdout
                def read():
                    try:
                        replies.put(stream.readline())
                    except Exception:
                        replies.put(b'')
                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                try:
                    raw = replies.get(timeout=self.timeout)
                except queue.Empty:
                    self.close()
                    reader.join(timeout=2)
                    return {'clip': {'status': 'unavailable'}, 'warning': 'ANALYSIS_TIMEOUT'}
                body = json.loads(raw)
                if body['request_id'] != ticket:
                    raise ValueError('Wrong worker response')
                if body.get('warning'):
                    self.close()  # allow recovery after repaired model/environment
                else:
                    self.timer = threading.Timer(self.idle, self.close)
                    self.timer.daemon = True
                    self.timer.start()
                return body
            except Exception:
                self.close()
                return {'clip': {'status': 'unavailable'}, 'warning': 'ANALYSIS_WORKER_FAILED'}
