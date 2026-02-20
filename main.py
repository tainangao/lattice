from __future__ import annotations

import asyncio

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.responses import JSONResponse

from lattice.prototype.auth import AuthVerificationError, verify_supabase_bearer_token
from lattice.prototype.config import (
    load_config,
    with_runtime_gemini_key,
)
from lattice.prototype.data_health import build_data_health_report
from lattice.prototype.models import PrivateUploadRequest, QueryRequest
from lattice.prototype.readiness import build_readiness_report
from lattice.prototype.service import PrototypeService

app = FastAPI(title="Lattice Phase 1 Prototype", version="0.1.0")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/ready")
async def readiness() -> JSONResponse:
    report = build_readiness_report(load_config())
    status_code = 200 if bool(report.get("ready")) else 503
    return JSONResponse(content=report, status_code=status_code)


@app.get("/health/data")
async def health_data() -> JSONResponse:
    config = load_config()
    report = await asyncio.to_thread(build_data_health_report, config)
    status_code = 200 if bool(report.get("ok")) else 503
    return JSONResponse(content=report, status_code=status_code)


@app.post("/api/prototype/query")
async def query_prototype(
    payload: QueryRequest,
    x_gemini_api_key: str | None = Header(default=None, alias="X-Gemini-Api-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> JSONResponse:
    config = with_runtime_gemini_key(load_config(), x_gemini_api_key)
    runtime_user_id: str | None = None
    if authorization is not None:
        try:
            runtime_user_id = verify_supabase_bearer_token(authorization, config)
        except AuthVerificationError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    service = PrototypeService(config)
    result = await service.run_query(
        payload.question,
        runtime_user_id=runtime_user_id,
        runtime_access_token=authorization,
    )
    return JSONResponse(content=result.model_dump())


@app.post("/api/prototype/private/upload")
async def upload_private_document(
    payload: PrivateUploadRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> JSONResponse:
    config = load_config()
    try:
        runtime_user_id = verify_supabase_bearer_token(authorization, config)
    except AuthVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    service = PrototypeService(config)
    ingested_count = await service.ingest_private_document(
        source=payload.filename,
        content=payload.content,
        runtime_user_id=runtime_user_id,
    )
    return JSONResponse(
        content={
            "ok": True,
            "ingested_chunks": ingested_count,
            "user_id": runtime_user_id,
        }
    )


def mount_chat_interface(application: FastAPI) -> None:
    from chainlit.utils import mount_chainlit

    mount_chainlit(app=application, target="lattice/chainlit_app.py", path="/chainlit")


mount_chat_interface(app)
