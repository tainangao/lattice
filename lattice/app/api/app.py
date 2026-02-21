from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from lattice.app.auth.config import load_supabase_auth_settings
from lattice.app.auth.contracts import AuthContext
from lattice.app.auth.verify import (
    AuthConfigurationError,
    AuthVerificationError,
    verify_supabase_bearer_token,
)
from lattice.core.config import load_app_config


def create_app() -> FastAPI:
    config = load_app_config()
    auth_settings = load_supabase_auth_settings()
    app = FastAPI(title=config.app_name, version=config.app_version)

    def require_auth_context(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> AuthContext:
        try:
            return verify_supabase_bearer_token(authorization, auth_settings)
        except AuthConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AuthVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/")
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "name": config.app_name,
                "version": config.app_version,
                "environment": config.environment,
                "docs": "/docs",
            }
        )

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "bootstrap-ready"}

    @app.get("/api/v1/status")
    async def status() -> dict[str, str]:
        return {"phase": "rebuild", "source": "Docs/new_app_requirements.md"}

    @app.get("/api/v1/auth/session")
    async def auth_session(
        context: AuthContext = Depends(require_auth_context),
    ) -> dict[str, str]:
        return {"user_id": context.user_id, "access_mode": context.access_mode}

    @app.get("/api/v1/private/ping")
    async def private_ping(
        context: AuthContext = Depends(require_auth_context),
    ) -> dict[str, str | bool]:
        return {"ok": True, "user_id": context.user_id}

    return app
