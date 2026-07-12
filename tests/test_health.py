from app.main import app
from fastapi.testclient import TestClient


def test_health_endpoint_returns_dev_status() -> None:
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dev_auth_returns_super_admin() -> None:
    client = TestClient(app)
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["is_authenticated"] is True
    assert body["is_super"] is True
    assert body["auth_mode"] == "dev"
    assert body["oauth_configured"] is False
    assert "game:create" in body["permissions"]
