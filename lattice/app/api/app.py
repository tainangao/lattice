from __future__ import annotations

import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
from lattice.app.graph.neo4j_store import Neo4jGraphStore, Neo4jSettings
from lattice.app.ingestion.service import (
    IngestionWorker,
    enqueue_ingestion_job,
    get_user_ingestion_job,
    list_user_ingestion_jobs,
)
from lattice.app.llm.providers import build_critic_model
from lattice.app.memory.service import (
    append_turn,
    get_recent_turns,
    resolve_follow_up_question,
)
from lattice.app.observability.service import create_trace, tool_trace
from lattice.app.orchestration.service import run_orchestration
from lattice.app.retrieval.embeddings import (
    build_embedding_provider,
    build_runtime_embedding_provider,
)
from lattice.app.retrieval.supabase_store import SupabaseVectorStore
from lattice.app.runtime.store import runtime_store
from lattice.core.config import AppConfig, load_app_config


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    thread_id: str | None = None


class RuntimeKeyRequest(BaseModel):
    action: str
    key: str | None = None


def _build_supabase_store(config: AppConfig) -> SupabaseVectorStore | None:
    if not config.supabase_url or not config.supabase_anon_key:
        return None
    return SupabaseVectorStore(
        url=config.supabase_url, anon_key=config.supabase_anon_key
    )


def _build_neo4j_store(config: AppConfig) -> Neo4jGraphStore | None:
    if not config.neo4j_uri or not config.neo4j_username or not config.neo4j_password:
        return None
    try:
        return Neo4jGraphStore(
            Neo4jSettings(
                uri=config.neo4j_uri,
                username=config.neo4j_username,
                password=config.neo4j_password,
                database=config.neo4j_database,
            )
        )
    except Exception:
        return None


def create_app() -> FastAPI:
    config = load_app_config()
    auth_settings = load_supabase_auth_settings()
    embedding_provider = build_embedding_provider(config.embedding_dimensions)
    supabase_store = _build_supabase_store(config)
    neo4j_store = _build_neo4j_store(config)
    ingestion_worker = IngestionWorker(
        store=runtime_store,
        embedding_provider=embedding_provider,
        supabase_store=supabase_store,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await ingestion_worker.start()
        try:
            yield
        finally:
            await ingestion_worker.stop()
            if neo4j_store:
                neo4j_store.close()

    app = FastAPI(title=config.app_name, version=config.app_version, lifespan=lifespan)

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
        job = enqueue_ingestion_job(
            store=runtime_store,
            user_id=context.user_id,
            filename=file.filename or "uploaded-file",
            content_type=content_type,
            file_bytes=file_bytes,
            user_access_token=context.access_token,
        )
        await ingestion_worker.enqueue(job.job_id)
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

    @app.get("/api/v1/observability/traces")
    async def query_traces(
        context: AuthContext = Depends(require_auth_context),
    ) -> dict[str, object]:
        return {
            "user_id": context.user_id,
            "traces": [
                {
                    "trace_id": row.trace_id,
                    "route": row.route,
                    "confidence": row.confidence,
                    "access_mode": row.access_mode,
                    "latency_ms": row.latency_ms,
                }
                for row in runtime_store.query_trace_log[-50:]
            ],
        }

    @app.post("/api/v1/query")
    async def query(
        payload: QueryRequest,
        maybe_context: AuthContext | None = Depends(try_auth_context),
        demo_session_id: str = Header(default="anonymous", alias="X-Demo-Session"),
    ) -> dict[str, object]:
        query_started = time.perf_counter()
        access_mode = "authenticated" if maybe_context else "demo"
        if access_mode == "demo":
            if not consume_demo_query(store=runtime_store, session_id=demo_session_id):
                raise HTTPException(
                    status_code=429,
                    detail="Demo quota reached. Sign in to continue with private features.",
                )

        runtime_key = runtime_store.runtime_keys_by_session.get(demo_session_id)
        runtime_embedding_provider = build_runtime_embedding_provider(
            dimensions=config.embedding_dimensions,
            runtime_key=runtime_key,
            model=config.gemini_embedding_model,
            backend=config.embedding_backend,
        )
        critic_model = build_critic_model(
            runtime_key=runtime_key,
            backend=config.critic_backend,
            model=config.critic_model,
        )

        thread_id = payload.thread_id or f"thread-{uuid4().hex[:10]}"
        resolved_question, resolution_note = resolve_follow_up_question(
            store=runtime_store,
            thread_id=thread_id,
            question=payload.question,
        )

        route_started = time.perf_counter()
        result = run_orchestration(
            store=runtime_store,
            question=resolved_question,
            user_id=maybe_context.user_id if maybe_context else None,
            user_access_token=maybe_context.access_token if maybe_context else None,
            embedding_provider=runtime_embedding_provider,
            critic_model=critic_model,
            max_refinements=config.critic_max_refinements,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
            use_langgraph=config.enable_langgraph,
        )
        routing_trace = tool_trace("router_orchestrator", route_started)

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
            content=result["answer"].answer,
        )
        turns = get_recent_turns(store=runtime_store, thread_id=thread_id)
        total_latency_ms = int((time.perf_counter() - query_started) * 1000)
        trace = create_trace(
            route=result["route"],
            confidence=result["answer"].confidence,
            access_mode=access_mode,
            latency_ms=max(total_latency_ms, 0),
        )
        runtime_store.query_trace_log.append(trace)
        if len(runtime_store.query_trace_log) > 500:
            runtime_store.query_trace_log = runtime_store.query_trace_log[-500:]

        trace_decisions = [
            {
                "tool_name": decision.tool_name,
                "rationale": decision.rationale,
                "latency_ms": decision.latency_ms,
                "status": decision.status,
                "attempt": decision.attempt,
            }
            for decision in result["tool_decisions"]
        ]
        if resolution_note:
            trace_decisions.insert(
                0,
                {
                    "tool_name": "memory_resolver",
                    "rationale": resolution_note,
                    "latency_ms": None,
                    "status": "ok",
                    "attempt": 1,
                },
            )

        return {
            "thread_id": thread_id,
            "access_mode": access_mode,
            "resolved_question": resolved_question,
            "route": result["route"],
            "route_reason": result["route_reason"],
            "answer": result["answer"].answer,
            "confidence": result["answer"].confidence,
            "citations": [
                {"source_id": citation.source_id, "location": citation.location}
                for citation in result["answer"].citations
            ],
            "trace": {
                "trace_id": trace.trace_id,
                "route": trace.route,
                "confidence": trace.confidence,
                "access_mode": trace.access_mode,
                "latency_ms": trace.latency_ms,
                "tools": [
                    {
                        "tool_name": routing_trace.tool_name,
                        "latency_ms": routing_trace.latency_ms,
                        "status": routing_trace.status,
                        "error_message": routing_trace.error_message,
                        "attempt": routing_trace.attempt,
                    }
                ],
                "decisions": trace_decisions,
            },
            "memory": [{"role": turn.role, "content": turn.content} for turn in turns],
            "demo_quota_remaining": (
                get_demo_remaining(store=runtime_store, session_id=demo_session_id)
                if access_mode == "demo"
                else None
            ),
        }

    return app
