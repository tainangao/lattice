from __future__ import annotations

from fastapi.testclient import TestClient

from lattice.prototype.models import QueryResponse, RetrievalMode, RouteDecision


def test_query_endpoint_derives_user_id_from_verified_token(
    monkeypatch,
) -> None:
    from main import app

    captured: dict[str, object] = {}

    class _FakeService:
        def __init__(self, config) -> None:
            _ = config

        async def run_query(
            self,
            question: str,
            runtime_user_id: str | None = None,
            runtime_access_token: str | None = None,
        ) -> QueryResponse:
            captured["question"] = question
            captured["runtime_user_id"] = runtime_user_id
            captured["runtime_access_token"] = runtime_access_token
            return QueryResponse(
                question=question,
                route=RouteDecision(mode=RetrievalMode.DIRECT, reason="ok"),
                answer="ok",
                snippets=[],
            )

    monkeypatch.setattr("main.PrototypeService", _FakeService)
    monkeypatch.setattr(
        "main.verify_supabase_bearer_token",
        lambda authorization, config: "token-subject-user",
    )

    client = TestClient(app)
    response = client.post(
        "/api/prototype/query",
        json={"question": "hello"},
        headers={"Authorization": "Bearer test-token", "X-User-Id": "spoofed-user"},
    )

    assert response.status_code == 200
    assert captured["runtime_user_id"] == "token-subject-user"
    assert captured["runtime_access_token"] == "Bearer test-token"


def test_private_upload_requires_valid_bearer_token(monkeypatch) -> None:
    from main import app
    from lattice.prototype.auth import AuthVerificationError

    monkeypatch.setattr(
        "main.verify_supabase_bearer_token",
        lambda authorization, config: (_ for _ in ()).throw(
            AuthVerificationError("bad token")
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/prototype/private/upload",
        json={"filename": "doc.txt", "content": "private"},
        headers={"Authorization": "Bearer invalid"},
    )

    assert response.status_code == 401
