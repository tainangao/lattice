from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from lattice.prototype.config import load_config
from lattice.prototype.models import QueryRequest
from lattice.prototype.service import PrototypeService

app = FastAPI(title="Lattice Phase 1 Prototype", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/prototype/query")
async def query_prototype(payload: QueryRequest) -> JSONResponse:
    service = PrototypeService(load_config())
    result = await service.run_query(payload.question)
    return JSONResponse(content=result.model_dump())


def mount_chat_interface(application: FastAPI) -> None:
    from chainlit.utils import mount_chainlit

    mount_chainlit(app=application, target="lattice/chainlit_app.py", path="/chainlit")


mount_chat_interface(app)
