from datetime import timedelta
from io import BytesIO
import subprocess

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.config import Settings
from app.main import create_app
from app.services.photo_processor import process_photo
from app.services.photo_execution import PhotoExecution
from app.services.uploads import now


@pytest.fixture
def setup(tmp_path):
    app = create_app(Settings(_env_file=None, upload_root=tmp_path / "originals"))
    def fake(data):
        def mask(image):
            value = Image.new("L", image.size, 0)
            value.paste(255, (60, 60, 240, 240))
            return value
        return process_photo(data, mask)
    app.state.photo_processor = fake
    with TestClient(app) as client:
        headers = {"X-Hanjang-Session": client.post("/api/v1/sessions").json()["session_token"]}
        stream = BytesIO()
        Image.new("RGB", (300, 300), (123, 65, 210)).save(stream, "PNG")
        data = stream.getvalue()
        meta = client.post("/api/v1/uploads", headers=headers, files={"photo": ("a.png", data, "image/png")}).json()
        yield app, client, headers, meta, data


def route(meta):
    return f'/api/v1/jobs/{meta["job_id"]}/photo-processing'


def test_processing_original_draft_selection_and_duplicate(setup):
    app, client, headers, meta, data = setup
    job = meta["job_id"]
    draft = {"facts": {"store_name": "  가게  ", "product_name": "상품", "price_text": " 1,000 원 "}, "mood": "warm"}
    client.put(f"/api/v1/jobs/{job}/input", headers=headers, json=draft)
    initial = client.get(route(meta), headers=headers).json()
    assert initial["status"] == "pending"
    response = client.post(route(meta), headers=headers)
    assert response.status_code == 202 and response.json()["status"] == "processing"
    state = client.get(route(meta), headers=headers).json()
    assert state["status"] == "completed" and state["photo_source"] == "processed"
    assert state["expires_at"] == meta["expires_at"]
    result = client.get('/api/v1/assets/' + state["processed"]["asset_id"], headers=headers)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    stranger = {"X-Hanjang-Session": client.post("/api/v1/sessions").json()["session_token"]}
    assert client.get('/api/v1/assets/' + state["processed"]["asset_id"], headers=stranger).status_code == 404
    assert Image.open(BytesIO(result.content)).mode == "RGBA"
    assert client.get('/api/v1/assets/' + meta["asset_id"], headers=headers).content == data
    assert client.get(f"/api/v1/jobs/{job}/input", headers=headers).json()["facts"]["price_text"] == " 1,000 원 "
    assert client.put(f"/api/v1/jobs/{job}/photo-source", headers=headers, json={"photo_source": "original"}).json()["photo_source"] == "original"
    before = set(app.state.upload_store.records[job].derived)
    assert client.post(route(meta), headers=headers).status_code == 202
    assert set(app.state.upload_store.records[job].derived) == before
    assert client.post("/api/v1/jobs", headers=headers).status_code == 404


def test_busy_missing_private_and_invalid_source(setup):
    app, client, headers, meta, data = setup
    storage = app.state.upload_store
    path = f'/api/v1/jobs/{meta["job_id"]}/photo-source'
    assert client.put(path, headers=headers, json={"photo_source": "processed"}).status_code == 409
    assert client.put(path, headers=headers, json={"photo_source": "evil"}).status_code == 422
    assert client.post(route(meta)).status_code == 401
    stranger = {"X-Hanjang-Session": client.post("/api/v1/sessions").json()["session_token"]}
    for method in [client.post, client.get]:
        assert method(route(meta), headers=stranger).status_code == 404
        assert method('/api/v1/jobs/missing/photo-processing', headers=headers).status_code == 404
    storage.start_photo(storage.authenticate(headers["X-Hanjang-Session"]), meta["job_id"])
    assert client.post(route(meta), headers=headers).status_code == 409
    assert client.put(path, headers=headers, json={"photo_source": "original"}).status_code == 409


def test_failed_processing_retry_and_quality_warning(setup):
    app, client, headers, meta, data = setup
    app.state.photo_processor = lambda data: process_photo(data, lambda image: Image.new("L", image.size, 0))
    client.post(route(meta), headers=headers)
    result = client.get(route(meta), headers=headers).json()
    assert result["status"] == "failed" and result["photo_source"] == "original"
    def small(data):
        def mask(image):
            value = Image.new("L", image.size, 0)
            value.paste(255, (0, 0, 10, 10))
            return value
        return process_photo(data, mask)
    app.state.photo_processor = small
    assert client.post(route(meta), headers=headers).status_code == 202
    state = client.get(route(meta), headers=headers).json()
    assert state["status"] == "completed" and state["photo_source"] == "original"
    assert state["warnings"] == ["PHOTO_MASK_REVIEW_REQUIRED"]


def test_ttl_removes_original_processed_and_mask(setup):
    app, client, headers, meta, data = setup
    client.post(route(meta), headers=headers)
    record = app.state.upload_store.records[meta["job_id"]]
    paths = [record.path, *record.derived.values()]
    assert len(paths) == 3
    record.upload.expires_at = now() - timedelta(seconds=1)
    assert client.get(route(meta), headers=headers).status_code == 410
    app.state.upload_store.cleanup()
    assert not any(path.exists() for path in paths)
    assert not app.state.upload_store.assets


def test_missing_model_actual_subprocess_and_safe_source(setup, tmp_path):
    app, client, headers, meta, data = setup
    app.state.photo_processor = PhotoExecution(tmp_path / "missing.onnx", 30, 1600)
    client.post(route(meta), headers=headers)
    state = client.get(route(meta), headers=headers).json()
    assert state["status"] == "failed" and state["warnings"] == ["PHOTO_MODEL_UNAVAILABLE"]
    assert state["photo_source"] == "original" and state["processed"] is None


def test_processing_capacity_is_bounded(setup):
    app, client, headers, meta, data = setup
    storage = app.state.upload_store
    user = storage.authenticate(headers["X-Hanjang-Session"])
    storage.start_photo(user, meta["job_id"])
    other = client.post("/api/v1/uploads", headers=headers, files={"photo": ("other.png", data, "image/png")}).json()
    assert client.post(route(other), headers=headers).status_code == 503


def test_timeout_kills_inference_process(monkeypatch, tmp_path):
    class Worker:
        returncode = None
        killed = False
        def communicate(self, data=None, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired("worker", timeout)
            return b"", b""
        def kill(self):
            self.killed = True
    worker = Worker()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: worker)
    result = PhotoExecution(tmp_path / "absent.onnx", 1, 1600)(b"image")
    assert result.warnings == ["PHOTO_PROCESSING_TIMEOUT"] and worker.killed
