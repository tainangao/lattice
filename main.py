from __future__ import annotations

import asyncio

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

from lattice.prototype.config import load_config, with_runtime_gemini_key
from lattice.prototype.data_health import build_data_health_report
from lattice.prototype.models import QueryRequest
from lattice.prototype.service import PrototypeService

app = FastAPI(title="Lattice Phase 1 Prototype", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


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
) -> JSONResponse:
    config = with_runtime_gemini_key(load_config(), x_gemini_api_key)
    service = PrototypeService(config)
    result = await service.run_query(payload.question)
    return JSONResponse(content=result.model_dump())


def mount_chat_interface(application: FastAPI) -> None:
    from chainlit.utils import mount_chainlit

    mount_chainlit(app=application, target="lattice/chainlit_app.py", path="/chainlit")


mount_chat_interface(app)
