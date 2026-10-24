from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config import PROJECT_ROOT, Settings
from app.main import create_app


@pytest.mark.parametrize("value", [None, "", "artifacts/models/ranking/missing.onnx"])
def test_optional_or_missing_model_does_not_prevent_service_start(monkeypatch, tmp_path, value):
    monkeypatch.delenv("RANKING_MODEL_PATH", raising=False)
    if value is not None:
        monkeypatch.setenv("RANKING_MODEL_PATH", value)
    settings = Settings(_env_file=None, upload_root=tmp_path / "uploads")
    expected = None if not value else PROJECT_ROOT / value
    assert settings.ranking_model_path == expected
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["status"] == "ok"
    if value:
        assert not settings.ranking_model_path.exists()  # No download or artifact creation.


def test_exact_environment_name_and_cwd_independence(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RANKING_MODEL_PATH", "artifacts/models/ranking/v1/model.onnx")
    monkeypatch.setenv("HANJANG_RANKING_MODEL_PATH", "wrong.onnx")
    assert Settings(_env_file=None).ranking_model_path == PROJECT_ROOT / "artifacts/models/ranking/v1/model.onnx"


def test_absolute_file_and_dotenv_alias(monkeypatch, tmp_path):
    monkeypatch.delenv("RANKING_MODEL_PATH", raising=False)
    path = tmp_path / "approved-model.onnx"
    config = tmp_path / "settings.env"
    config.write_text(f"RANKING_MODEL_PATH={path.as_posix()}\n", encoding="utf-8")
    assert Settings(_env_file=config).ranking_model_path == path


def test_photo_and_ranking_environment_settings_coexist(monkeypatch, tmp_path):
    photo_path = tmp_path / "rembg" / "missing.onnx"
    monkeypatch.setenv("HANJANG_PHOTO_MODEL_PATH", str(photo_path))
    monkeypatch.setenv("HANJANG_PHOTO_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("HANJANG_PHOTO_MAX_SIDE", "1024")
    monkeypatch.setenv("RANKING_MODEL_PATH", "artifacts/models/ranking/missing.onnx")
    settings = Settings(_env_file=None, upload_root=tmp_path / "uploads")
    assert settings.photo_model_path == photo_path
    assert settings.photo_timeout_seconds == 45
    assert settings.photo_max_side == 1024
    assert settings.ranking_model_path == PROJECT_ROOT / "artifacts/models/ranking/missing.onnx"
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
