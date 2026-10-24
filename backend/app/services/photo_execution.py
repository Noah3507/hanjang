import base64
import json
import os
from pathlib import Path
import subprocess
import sys

from app.services.photo_processor import ProcessedPhoto


class PhotoExecution:
    def __init__(self, model: Path, timeout: float, max_side: int):
        self.model, self.timeout, self.max_side = model, timeout, max_side

    def __call__(self, data: bytes) -> ProcessedPhoto:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        process = subprocess.Popen(
            [sys.executable, "-m", "app.services.photo_worker", str(self.model), str(self.max_side)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            output, _ = process.communicate(data, timeout=self.timeout)
            if process.returncode != 0:
                raise ValueError("worker failed")
            body = json.loads(output)
            return ProcessedPhoto(base64.b64decode(body["png"]) if body["png"] else None,
                                  base64.b64decode(body["mask"]) if body["mask"] else None,
                                  body["width"], body["height"], body["warnings"])
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return ProcessedPhoto(None, None, 0, 0, ["PHOTO_PROCESSING_TIMEOUT"])
        except Exception:
            if process.poll() is None:
                process.kill()
            process.communicate()
            return ProcessedPhoto(None, None, 0, 0, ["PHOTO_PROCESSING_FAILED"])
