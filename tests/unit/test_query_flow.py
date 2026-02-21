from __future__ import annotations

from fastapi.testclient import TestClient

import lattice.app.api.app as api_app
from lattice.app.auth.contracts import AuthContext
from main import app


def test_demo_quota_decrements_on_query() -> None:
    with TestClient(app) as client:
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
        assert response.json()["trace"]["latency_ms"] >= 0

        after = client.get("/api/v1/demo/quota", headers={"X-Demo-Session": "demo-1"})
        assert after.status_code == 200
        assert after.json()["remaining"] == 4


def test_demo_mode_can_query_shared_document_scope() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/query",
            json={"question": "summarize my uploaded pdf document"},
            headers={"X-Demo-Session": "demo-2"},
        )

        assert response.status_code == 200
        assert response.json()["access_mode"] == "demo"
        assert response.json()["route"] in {"document", "hybrid"}


def test_runtime_key_lifecycle() -> None:
    with TestClient(app) as client:
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


def test_runtime_key_uses_environment_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/query",
            json={"question": "show graph dependencies for project alpha"},
            headers={"X-Demo-Session": "demo-env-key"},
        )
        assert response.status_code == 200
        assert response.json()["runtime_key_source"] == "environment"


def test_authenticated_upload_and_document_query(monkeypatch) -> None:
    def fake_verify(authorization: str | None, _settings) -> AuthContext:
        assert authorization == "Bearer test-token"
        return AuthContext(
            user_id="user-abc",
            access_mode="authenticated",
            access_token="test-token",
        )

    monkeypatch.setattr(api_app, "verify_supabase_bearer_token", fake_verify)

    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/private/ingestion/upload",
            headers={"Authorization": "Bearer test-token"},
            files={
                "file": (
                    "notes.txt",
                    b"Engineering owns dependency mapping.",
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 200
        assert upload.json()["status"] == "queued"
        job_id = upload.json()["job_id"]

        for _ in range(20):
            job = client.get(
                f"/api/v1/private/ingestion/jobs/{job_id}",
                headers={"Authorization": "Bearer test-token"},
            )
            assert job.status_code == 200
            status = job.json()["status"]
            if status in {"success", "failed"}:
                break
        assert status == "success"

        query = client.post(
            "/api/v1/query",
            headers={"Authorization": "Bearer test-token"},
            json={"question": "what does my notes file say about engineering owners?"},
        )
        assert query.status_code == 200
        assert query.json()["access_mode"] == "authenticated"
        assert query.json()["route"] in {"document", "hybrid"}
        assert len(query.json()["citations"]) >= 1
        assert len(query.json()["trace"]["decisions"]) >= 3


def test_follow_up_reference_resolution_uses_memory() -> None:
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/query",
            json={"question": "show graph dependencies for project alpha"},
            headers={"X-Demo-Session": "demo-3"},
        )
        assert first.status_code == 200
        thread_id = first.json()["thread_id"]

        follow_up = client.post(
            "/api/v1/query",
            json={
                "question": "what about that relationship evidence?",
                "thread_id": thread_id,
            },
            headers={"X-Demo-Session": "demo-3"},
        )
        assert follow_up.status_code == 200
        assert (
            "Follow-up context from prior user turn"
            in follow_up.json()["resolved_question"]
        )
        decision_names = {
            row["tool_name"] for row in follow_up.json()["trace"]["decisions"]
        }
        assert "memory_resolver" in decision_names
