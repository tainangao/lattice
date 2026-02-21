from fastapi.testclient import TestClient

from main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_status_reports_rebuild_phase() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/status")

    assert response.status_code == 200
    assert response.json()["phase"] == "rebuild"
