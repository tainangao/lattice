from __future__ import annotations

from fastapi.testclient import TestClient

import lattice.app.api.app as api_app
from lattice.app.auth.contracts import AuthContext
from main import app


def test_demo_quota_decrements_on_query() -> None:
    client = TestClient(app)

    before = client.get("/api/v1/demo/quota", headers={"X-Demo-Session": "demo-1"})
    assert before.status_code == 200
    assert before.json()["remaining"] == 5

    response = client.post(
        "/api/v1/query",
        json={"question": "show graph dependencies for project alpha"},
        headers={"X-Demo-Session": "demo-1"},
    )

    assert response.status_code == 200
    assert response.json()["access_mode"] == "demo"
    assert response.json()["route"] == "graph"

    after = client.get("/api/v1/demo/quota", headers={"X-Demo-Session": "demo-1"})
    assert after.status_code == 200
    assert after.json()["remaining"] == 4


def test_demo_mode_blocks_private_document_route() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/query",
        json={"question": "summarize my uploaded pdf document"},
        headers={"X-Demo-Session": "demo-2"},
    )

    assert response.status_code == 401
    assert "requires authentication" in response.json()["detail"].lower()


def test_runtime_key_lifecycle() -> None:
    client = TestClient(app)
    headers = {"X-Demo-Session": "demo-key"}

    status_before = client.post(
        "/api/v1/runtime/key",
        json={"action": "status"},
        headers=headers,
    )
    assert status_before.status_code == 200
    assert status_before.json()["has_key"] is False

    set_response = client.post(
        "/api/v1/runtime/key",
        json={"action": "set", "key": "gemini-test-key"},
        headers=headers,
    )
    assert set_response.status_code == 200
    assert set_response.json()["has_key"] is True

    clear_response = client.post(
        "/api/v1/runtime/key",
        json={"action": "clear"},
        headers=headers,
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["has_key"] is False


def test_authenticated_upload_and_document_query(monkeypatch) -> None:
    client = TestClient(app)

    def fake_verify(authorization: str | None, _settings) -> AuthContext:
        assert authorization == "Bearer test-token"
        return AuthContext(user_id="user-abc", access_mode="authenticated")

    monkeypatch.setattr(api_app, "verify_supabase_bearer_token", fake_verify)

    upload = client.post(
        "/api/v1/private/ingestion/upload",
        headers={"Authorization": "Bearer test-token"},
        files={
            "file": ("notes.txt", b"Engineering owns dependency mapping.", "text/plain")
        },
    )
    assert upload.status_code == 200
    assert upload.json()["status"] == "success"
    assert upload.json()["chunk_count"] >= 1

    query = client.post(
        "/api/v1/query",
        headers={"Authorization": "Bearer test-token"},
        json={"question": "what does my notes file say about engineering owners?"},
    )
    assert query.status_code == 200
    assert query.json()["access_mode"] == "authenticated"
    assert query.json()["route"] == "document"
    assert len(query.json()["citations"]) >= 1
