from fastapi.testclient import TestClient

import lattice.app.api.app as api_app
from lattice.app.auth.contracts import AuthContext
from lattice.app.auth.verify import AuthConfigurationError
from main import app


def test_auth_session_requires_bearer_header() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401


def test_auth_session_returns_verified_identity(monkeypatch) -> None:
    client = TestClient(app)

    def fake_verify(authorization: str | None, _settings) -> AuthContext:
        assert authorization == "Bearer test-token"
        return AuthContext(user_id="user-123", access_mode="authenticated")

    monkeypatch.setattr(api_app, "verify_supabase_bearer_token", fake_verify)

    response = client.get(
        "/api/v1/auth/session",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-123",
        "access_mode": "authenticated",
    }


def test_auth_session_reports_configuration_error(monkeypatch) -> None:
    client = TestClient(app)

    def fake_verify(_authorization: str | None, _settings) -> AuthContext:
        raise AuthConfigurationError("Supabase auth verification is not configured")

    monkeypatch.setattr(api_app, "verify_supabase_bearer_token", fake_verify)

    response = client.get(
        "/api/v1/auth/session",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 503
