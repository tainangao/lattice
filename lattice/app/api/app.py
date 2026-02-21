from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
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
from lattice.app.runtime.store import (
    CompletedOAuthSession,
    PendingOAuthState,
    runtime_store,
)
from lattice.core.config import AppConfig, load_app_config

SUPPORTED_OAUTH_PROVIDERS = {
    "apple",
    "azure",
    "bitbucket",
    "discord",
    "facebook",
    "github",
    "gitlab",
    "google",
    "kakao",
    "linkedin",
    "notion",
    "slack",
    "spotify",
    "twitch",
    "twitter",
    "workos",
    "zoom",
}
OAUTH_STATE_TTL_SECONDS = 15 * 60


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    thread_id: str | None = None


class RuntimeKeyRequest(BaseModel):
    action: str
    key: str | None = None


class OAuthStartRequest(BaseModel):
    provider: str


class OAuthCompleteRequest(BaseModel):
    state: str
    access_token: str | None = None
    refresh_token: str | None = None
    error: str | None = None


class OAuthClaimRequest(BaseModel):
    state: str


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

    def _cleanup_expired_oauth_states(now_epoch: int) -> None:
        expired_states = [
            state
            for state, pending in runtime_store.oauth_pending_by_state.items()
            if now_epoch - pending.created_at > OAUTH_STATE_TTL_SECONDS
        ]
        for state in expired_states:
            runtime_store.oauth_pending_by_state.pop(state, None)
            runtime_store.oauth_completed_by_state.pop(state, None)

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

    @app.get("/api/v1/auth/oauth/providers")
    async def oauth_providers() -> dict[str, list[str]]:
        return {"providers": sorted(SUPPORTED_OAUTH_PROVIDERS)}

    @app.post("/api/v1/auth/oauth/start")
    async def oauth_start(
        payload: OAuthStartRequest,
        demo_session_id: str = Header(default="anonymous", alias="X-Demo-Session"),
    ) -> dict[str, str | int]:
        provider = payload.provider.lower().strip()
        if provider not in SUPPORTED_OAUTH_PROVIDERS:
            raise HTTPException(
                status_code=400, detail=f"Unsupported provider: {provider}"
            )

        supabase_url = (config.supabase_url or "").strip()
        redirect_url = os.getenv("SUPABASE_OAUTH_REDIRECT_URL", "").strip()
        if not supabase_url or not redirect_url:
            raise HTTPException(
                status_code=503,
                detail="SUPABASE_URL and SUPABASE_OAUTH_REDIRECT_URL are required.",
            )

        now_epoch = int(time.time())
        _cleanup_expired_oauth_states(now_epoch)
        state = f"oauth-{uuid4().hex}"
        runtime_store.oauth_pending_by_state[state] = PendingOAuthState(
            session_id=demo_session_id,
            provider=provider,
            created_at=now_epoch,
        )

        authorize_url = f"{supabase_url.rstrip('/')}/auth/v1/authorize?" + urlencode(
            {
                "provider": provider,
                "redirect_to": redirect_url,
                "state": state,
            }
        )
        return {
            "provider": provider,
            "state": state,
            "authorize_url": authorize_url,
            "expires_in_seconds": OAUTH_STATE_TTL_SECONDS,
        }

    @app.get("/api/v1/auth/oauth/callback", response_class=HTMLResponse)
    async def oauth_callback() -> HTMLResponse:
        html = """<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>Lattice OAuth Callback</title>
    <style>
      body { font-family: sans-serif; margin: 2rem; max-width: 48rem; }
      .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }
      .ok { color: #1f6f3d; }
      .err { color: #9e2a2b; }
      code { background: #f5f5f5; padding: 0.1rem 0.3rem; border-radius: 4px; }
    </style>
  </head>
  <body>
    <div class=\"card\">
      <h2>Complete sign-in</h2>
      <p id=\"status\">Finalizing your OAuth session...</p>
      <p>After success, return to Chainlit and continue chatting.</p>
    </div>
    <script>
      const statusNode = document.getElementById('status');
      const hash = new URLSearchParams(window.location.hash.slice(1));
      const query = new URLSearchParams(window.location.search);
      const state = query.get('state') || hash.get('state') || '';
      const accessToken = hash.get('access_token') || query.get('access_token') || '';
      const refreshToken = hash.get('refresh_token') || query.get('refresh_token') || '';
      const error = query.get('error_description') || query.get('error') || hash.get('error') || '';

      if (!state) {
        statusNode.className = 'err';
        statusNode.textContent = 'Missing OAuth state. Start auth again from Chainlit.';
      } else {
        fetch('/api/v1/auth/oauth/complete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            state,
            access_token: accessToken || null,
            refresh_token: refreshToken || null,
            error: error || null,
          }),
        })
          .then(async (response) => {
            const payload = await response.json();
            if (!response.ok || payload.status !== 'stored') {
              const detail = payload.detail || payload.status || 'unknown error';
              statusNode.className = 'err';
              statusNode.innerHTML = 'OAuth callback failed: <code>' + detail + '</code>';
              return;
            }
            statusNode.className = 'ok';
            statusNode.textContent = 'OAuth callback stored. Return to Chainlit to finish linking this chat session.';
          })
          .catch((err) => {
            statusNode.className = 'err';
            statusNode.textContent = 'OAuth callback failed: ' + String(err);
          });
      }
    </script>
  </body>
</html>"""
        return HTMLResponse(content=html)

    @app.post("/api/v1/auth/oauth/complete")
    async def oauth_complete(payload: OAuthCompleteRequest) -> dict[str, str | None]:
        now_epoch = int(time.time())
        _cleanup_expired_oauth_states(now_epoch)
        pending = runtime_store.oauth_pending_by_state.get(payload.state)
        if not pending:
            raise HTTPException(
                status_code=404, detail="OAuth state not found or expired"
            )

        if payload.error:
            runtime_store.oauth_completed_by_state.pop(payload.state, None)
            raise HTTPException(
                status_code=400,
                detail=f"OAuth provider returned error: {payload.error}",
            )

        access_token = (payload.access_token or "").strip()
        refresh_token = (payload.refresh_token or "").strip() or None
        if not access_token:
            raise HTTPException(
                status_code=400, detail="Missing access token from callback"
            )

        runtime_store.oauth_completed_by_state[payload.state] = CompletedOAuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            created_at=now_epoch,
        )
        return {"status": "stored", "state": payload.state}

    @app.post("/api/v1/auth/oauth/claim")
    async def oauth_claim(
        payload: OAuthClaimRequest,
        demo_session_id: str = Header(default="anonymous", alias="X-Demo-Session"),
    ) -> dict[str, str | bool | None]:
        now_epoch = int(time.time())
        _cleanup_expired_oauth_states(now_epoch)
        pending = runtime_store.oauth_pending_by_state.get(payload.state)
        if not pending:
            return {"status": "missing", "state": payload.state, "complete": False}
        if pending.session_id != demo_session_id:
            raise HTTPException(
                status_code=403, detail="OAuth state belongs to another session"
            )

        completed = runtime_store.oauth_completed_by_state.get(payload.state)
        if not completed:
            return {"status": "pending", "state": payload.state, "complete": False}

        runtime_store.oauth_pending_by_state.pop(payload.state, None)
        runtime_store.oauth_completed_by_state.pop(payload.state, None)
        return {
            "status": "complete",
            "state": payload.state,
            "complete": True,
            "access_token": completed.access_token,
            "refresh_token": completed.refresh_token,
        }

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
            "stage": job.stage,
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
                    "stage": job.stage,
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
            "stage": job.stage,
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
        env_runtime_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        resolved_runtime_key = runtime_key or env_runtime_key
        runtime_key_source = (
            "session" if runtime_key else ("environment" if env_runtime_key else "none")
        )
        runtime_embedding_provider = build_runtime_embedding_provider(
            dimensions=config.embedding_dimensions,
            runtime_key=resolved_runtime_key,
            model=config.gemini_embedding_model,
            backend=config.embedding_backend,
        )
        critic_model = build_critic_model(
            runtime_key=resolved_runtime_key,
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
            planner_max_steps=config.planner_max_steps,
            rerank_backend=config.rerank_backend,
            rerank_model=config.rerank_model,
            runtime_key=resolved_runtime_key,
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
            "runtime_key_source": runtime_key_source,
            "resolved_question": resolved_question,
            "route": result["route"],
            "route_reason": result["route_reason"],
            "answer": result["answer"].answer,
            "confidence": result["answer"].confidence,
            "policy": result["answer"].policy,
            "action": result["answer"].action,
            "retrieval_degraded": result["retrieval"].degraded,
            "backend_failures": list(result["retrieval"].backend_failures),
            "rerank_strategy": result["retrieval"].rerank_strategy,
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
