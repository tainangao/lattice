from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from lattice.app.auth.access import (
    clear_runtime_key,
    consume_demo_query,
    get_demo_remaining,
    has_runtime_key,
    set_runtime_key,
)
from lattice.app.auth.config import load_supabase_auth_settings
from lattice.app.auth.contracts import AuthContext
from lattice.app.auth.verify import (
    AuthConfigurationError,
    AuthVerificationError,
    verify_supabase_bearer_token,
)
from lattice.app.ingestion.service import (
    create_ingestion_job,
    get_user_ingestion_job,
    list_user_ingestion_jobs,
)
from lattice.app.memory.service import append_turn, get_recent_turns
from lattice.app.observability.service import create_trace, tool_trace
from lattice.app.orchestration.service import select_route
from lattice.app.response.service import build_answer
from lattice.app.retrieval.service import retrieve
from lattice.app.runtime.store import runtime_store
from lattice.core.config import load_app_config


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    thread_id: str | None = None


class RuntimeKeyRequest(BaseModel):
    action: str
    key: str | None = None


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

    def try_auth_context(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> AuthContext | None:
        if not authorization:
            return None
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
        return {"phase": "rebuild", "source": "Docs/PRD.md"}

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

    @app.get("/api/v1/demo/quota")
    async def demo_quota(
        demo_session_id: str = Header(default="anonymous", alias="X-Demo-Session"),
    ) -> dict[str, int | str]:
        remaining = get_demo_remaining(store=runtime_store, session_id=demo_session_id)
        return {
            "access_mode": "demo",
            "session_id": demo_session_id,
            "remaining": remaining,
        }

    @app.post("/api/v1/runtime/key")
    async def runtime_key(
        payload: RuntimeKeyRequest,
        demo_session_id: str = Header(default="anonymous", alias="X-Demo-Session"),
    ) -> dict[str, str | bool]:
        action = payload.action.lower().strip()
        if action == "help":
            return {
                "action": "help",
                "message": "Use action=set with key, action=clear, or action=status.",
            }
        if action == "set":
            if not payload.key:
                raise HTTPException(
                    status_code=400, detail="Missing key for action=set"
                )
            set_runtime_key(
                store=runtime_store,
                session_id=demo_session_id,
                runtime_key=payload.key,
            )
            return {"action": "set", "has_key": True, "session_id": demo_session_id}
        if action == "clear":
            clear_runtime_key(store=runtime_store, session_id=demo_session_id)
            return {"action": "clear", "has_key": False, "session_id": demo_session_id}
        if action == "status":
            return {
                "action": "status",
                "has_key": has_runtime_key(
                    store=runtime_store, session_id=demo_session_id
                ),
                "session_id": demo_session_id,
            }
        raise HTTPException(status_code=400, detail="Unsupported action")

    @app.post("/api/v1/private/ingestion/upload")
    async def upload_private_file(
        file: UploadFile = File(...),
        context: AuthContext = Depends(require_auth_context),
    ) -> dict[str, str | int | None]:
        file_bytes = await file.read()
        content_type = file.content_type or "application/octet-stream"
        job = create_ingestion_job(
            store=runtime_store,
            user_id=context.user_id,
            filename=file.filename or "uploaded-file",
            content_type=content_type,
            file_bytes=file_bytes,
        )
        return {
            "job_id": job.job_id,
            "status": job.status,
            "filename": job.filename,
            "chunk_count": job.chunk_count,
            "error_message": job.error_message,
        }

    @app.get("/api/v1/private/ingestion/jobs")
    async def list_private_ingestion_jobs(
        context: AuthContext = Depends(require_auth_context),
    ) -> dict[str, list[dict[str, str | int | None]]]:
        jobs = list_user_ingestion_jobs(store=runtime_store, user_id=context.user_id)
        return {
            "jobs": [
                {
                    "job_id": job.job_id,
                    "status": job.status,
                    "filename": job.filename,
                    "chunk_count": job.chunk_count,
                    "error_message": job.error_message,
                }
                for job in jobs
            ]
        }

    @app.get("/api/v1/private/ingestion/jobs/{job_id}")
    async def private_ingestion_job(
        job_id: str,
        context: AuthContext = Depends(require_auth_context),
    ) -> dict[str, str | int | None]:
        job = get_user_ingestion_job(
            store=runtime_store,
            user_id=context.user_id,
            job_id=job_id,
        )
        if not job:
            raise HTTPException(status_code=404, detail="Ingestion job not found")
        return {
            "job_id": job.job_id,
            "status": job.status,
            "filename": job.filename,
            "chunk_count": job.chunk_count,
            "error_message": job.error_message,
        }

    @app.post("/api/v1/query")
    async def query(
        payload: QueryRequest,
        maybe_context: AuthContext | None = Depends(try_auth_context),
        demo_session_id: str = Header(default="anonymous", alias="X-Demo-Session"),
    ) -> dict[str, object]:
        access_mode = "authenticated" if maybe_context else "demo"
        if access_mode == "demo":
            if not consume_demo_query(store=runtime_store, session_id=demo_session_id):
                raise HTTPException(
                    status_code=429,
                    detail="Demo quota reached. Sign in to continue with private features.",
                )

        route_started = time.perf_counter()
        route_decision = select_route(payload.question)
        routing_trace = tool_trace("router", route_started)

        if access_mode == "demo" and route_decision.path in {"document", "hybrid"}:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Private document retrieval requires authentication. "
                    "Sign in with Supabase Auth to upload/query private files."
                ),
            )

        retrieval_started = time.perf_counter()
        retrieval = retrieve(
            store=runtime_store,
            route=route_decision.path,
            query=payload.question,
            user_id=maybe_context.user_id if maybe_context else None,
        )
        retrieval_trace = tool_trace("retrieval", retrieval_started)

        answer_started = time.perf_counter()
        answer = build_answer(payload.question, retrieval)
        synthesis_trace = tool_trace("synthesis", answer_started)

        thread_id = payload.thread_id or f"thread-{uuid4().hex[:10]}"
        append_turn(
            store=runtime_store,
            thread_id=thread_id,
            role="user",
            content=payload.question,
        )
        append_turn(
            store=runtime_store,
            thread_id=thread_id,
            role="assistant",
            content=answer.answer,
        )
        turns = get_recent_turns(store=runtime_store, thread_id=thread_id)

        trace = create_trace(route=route_decision.path, confidence=answer.confidence)

        return {
            "thread_id": thread_id,
            "access_mode": access_mode,
            "route": route_decision.path,
            "route_reason": route_decision.reason,
            "answer": answer.answer,
            "confidence": answer.confidence,
            "citations": [
                {"source_id": citation.source_id, "location": citation.location}
                for citation in answer.citations
            ],
            "trace": {
                "trace_id": trace.trace_id,
                "route": trace.route,
                "confidence": trace.confidence,
                "tools": [
                    {
                        "tool_name": routing_trace.tool_name,
                        "latency_ms": routing_trace.latency_ms,
                        "status": routing_trace.status,
                    },
                    {
                        "tool_name": retrieval_trace.tool_name,
                        "latency_ms": retrieval_trace.latency_ms,
                        "status": retrieval_trace.status,
                    },
                    {
                        "tool_name": synthesis_trace.tool_name,
                        "latency_ms": synthesis_trace.latency_ms,
                        "status": synthesis_trace.status,
                    },
                ],
            },
            "memory": [{"role": turn.role, "content": turn.content} for turn in turns],
            "demo_quota_remaining": (
                get_demo_remaining(store=runtime_store, session_id=demo_session_id)
                if access_mode == "demo"
                else None
            ),
        }

    return app
