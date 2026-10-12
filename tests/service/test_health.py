import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, upload_root=tmp_path / "uploads")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/health", "/api/v1/health"])
def test_health_contract(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api_version": "v1-draft"}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_local_origin_is_allowed(client, origin):
    response = client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers


def test_unknown_origin_is_not_allowed(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_can_be_configured_without_reading_local_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HANJANG_CORS_ORIGINS", '["http://localhost:6000"]')
    settings = Settings(_env_file=None, upload_root=tmp_path / "uploads")
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"Origin": "http://localhost:6000"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:6000"


def test_future_service_routes_are_not_implemented(client):
    assert client.post("/api/v1/jobs", json={}).status_code == 404
