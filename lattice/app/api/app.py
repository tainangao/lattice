from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from lattice.core.config import load_app_config


def create_app() -> FastAPI:
    config = load_app_config()
    app = FastAPI(title=config.app_name, version=config.app_version)

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

    return app
