from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.config import Settings
from app.main import create_app
from app.services.uploads import MAX_BYTES, UploadError, now, validate_image


def photo_bytes(fmt="PNG", size=(300, 300)):
    stream = BytesIO()
    Image.new("RGB", size, "#a87840").save(stream, format=fmt)
    return stream.getvalue()


@pytest.fixture
def setup(tmp_path):
    app = create_app(Settings(_env_file=None, upload_root=tmp_path / "originals"))
    with TestClient(app) as client:
        token = client.post("/api/v1/sessions", json={}).json()["session_token"]
        yield client, {"X-Hanjang-Session": token}, app.state.upload_store


def upload(client, headers, data=None, mime="image/png", filename="photo.png"):
    return client.post("/api/v1/uploads", headers=headers, files={"photo": (filename, data or photo_bytes(), mime)})


def draft():
    return {"facts": {"store_name": "  테스트 가게  ", "product_name": "한글 메뉴 🍜", "price_text": " 10,500 원 ", "address": None, "instagram_handle": None}, "mood": "warm"}


@pytest.mark.parametrize("fmt,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg")])
def test_original_bytes_and_facts_roundtrip(setup, fmt, mime):
    client, headers, storage = setup
    data = photo_bytes(fmt)
    response = upload(client, headers, data, mime, "../../user.key")
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    meta = response.json()
    assert meta["sha256"] == sha256(data).hexdigest()
    assert meta["width"] == meta["height"] == 300
    assert set(meta) == {"job_id", "asset_id", "width", "height", "mime_type", "sha256", "created_at", "expires_at"}
    saved = client.put(f'/api/v1/jobs/{meta["job_id"]}/input', json=draft(), headers=headers)
    assert saved.status_code == 200
    assert saved.json()["facts"] == draft()["facts"]
    assert saved.json()["status"] == "pending"
    read = client.get(f'/api/v1/jobs/{meta["job_id"]}/input', headers=headers)
    assert read.json() == saved.json()
    original = client.get(f'/api/v1/assets/{meta["asset_id"]}', headers=headers)
    assert original.content == data
    assert original.headers["cache-control"] == "no-store"
    assert storage.records[meta["job_id"]].path.resolve().parent == storage.root
    assert client.post("/api/v1/jobs", json={}).status_code == 404


def test_session_ownership_and_missing_token(setup):
    client, headers, storage = setup
    assert upload(client, {}).status_code == 401
    meta = upload(client, headers).json()
    stranger = {"X-Hanjang-Session": client.post("/api/v1/sessions").json()["session_token"]}
    for route in [f'/api/v1/assets/{meta["asset_id"]}', f'/api/v1/jobs/{meta["job_id"]}/input']:
        assert client.get(route, headers=stranger).status_code == 404
        assert client.get(route).status_code == 401
    assert client.put(f'/api/v1/jobs/{meta["job_id"]}/input', json=draft(), headers=stranger).status_code == 404


@pytest.mark.parametrize("data,mime,status", [
    (b"not an image", "image/png", 422),
    (b"<svg/>", "image/svg+xml", 415),
    (photo_bytes("JPEG"), "image/png", 415),
    (photo_bytes(size=(255, 300)), "image/png", 422),
    (photo_bytes()[:60], "image/png", 422),
    (b"x" * (MAX_BYTES + 1), "image/png", 413),
], ids=["invalid-bytes", "unsupported-svg", "mismatched-type", "small-image", "truncated-image", "oversized-file"])
def test_invalid_upload_leaves_no_original(setup, data, mime, status):
    client, headers, storage = setup
    response = upload(client, headers, data, mime)
    assert response.status_code == status
    assert response.json()["error"]["code"]
    assert not storage.records
    assert not storage.root.exists() or not list(storage.root.iterdir())


def test_multipart_overall_body_is_bounded(setup):
    client, headers, storage = setup
    response = upload(client, headers, b"x" * (MAX_BYTES + 100_000))
    assert response.status_code == 413
    assert not storage.records


def test_extra_photo_or_form_field_is_rejected(setup):
    client, headers, _ = setup
    response = client.post("/api/v1/uploads", headers=headers, files=[
        ("photo", ("a.png", photo_bytes(), "image/png")),
        ("photo", ("b.png", photo_bytes(), "image/png")),
    ])
    assert response.status_code == 422


@pytest.mark.parametrize("key,value", [("store_name", "   "), ("product_name", "x" * 81), ("price_text", 10500), ("price_text", "10\n원")])
def test_invalid_facts_are_not_stored_or_echoed(setup, key, value):
    client, headers, storage = setup
    meta = upload(client, headers).json()
    data = draft(); data["facts"][key] = value
    response = client.put(f'/api/v1/jobs/{meta["job_id"]}/input', json=data, headers=headers)
    assert response.status_code == 422
    assert "input" not in response.json()["error"]
    assert storage.records[meta["job_id"]].draft is None


def test_unknown_fields_and_mood_rejected(setup):
    client, headers, _ = setup
    meta = upload(client, headers).json()
    for payload in [{**draft(), "extra": "no"}, {**draft(), "mood": "unapproved"}]:
        assert client.put(f'/api/v1/jobs/{meta["job_id"]}/input', json=payload, headers=headers).status_code == 422


def test_expiry_removes_original_and_draft_without_extending_ttl(setup):
    client, headers, storage = setup
    meta = upload(client, headers).json()
    job = meta["job_id"]
    client.put(f"/api/v1/jobs/{job}/input", json=draft(), headers=headers)
    assert storage.records[job].upload.expires_at.isoformat().replace("+00:00", "Z") == meta["expires_at"]
    record = storage.records[job]
    record.upload.expires_at = now() - timedelta(seconds=1)
    assert client.get(f'/api/v1/assets/{meta["asset_id"]}', headers=headers).status_code == 410
    assert client.put(f"/api/v1/jobs/{job}/input", json=draft(), headers=headers).status_code == 410
    storage.cleanup()
    assert not record.path.exists()
    assert job not in storage.records


def test_restart_orphan_cleanup_does_not_delete_other_files(setup):
    _, _, storage = setup
    storage.root.mkdir()
    owned = storage.root / ("a" * 32 + ".png")
    owned.write_bytes(photo_bytes())
    old = (now() - timedelta(hours=25)).timestamp()
    os.utime(owned, (old, old))
    unrelated = storage.root / "do-not-delete.txt"
    unrelated.write_text("keep")
    storage.cleanup()
    assert not owned.exists()
    assert unrelated.exists()


def test_path_escape_is_rejected(setup):
    _, _, storage = setup
    with pytest.raises(UploadError): storage.safe_path("../../secret.png")


def test_decoded_pixel_limit():
    data = photo_bytes(size=(6000, 4001))
    with pytest.raises(UploadError) as error: validate_image(data, "image/png")
    assert error.value.status == 413


def test_direct_cors_upload_headers(setup):
    client, _, _ = setup
    response = client.options("/api/v1/uploads", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-hanjang-session,content-type",
    })
    assert response.status_code == 200
