from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import chainlit as cl
import httpx

API_BASE_URL = os.getenv("LATTICE_API_URL", "http://localhost:8000").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

SUPPORTED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}
SUPPORTED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


def _session_id() -> str:
    session_id = cl.user_session.get("demo_session_id")
    if isinstance(session_id, str) and session_id:
        return session_id
    session_id = f"chainlit-{uuid4().hex[:10]}"
    cl.user_session.set("demo_session_id", session_id)
    return session_id


def _auth_token() -> str | None:
    token = cl.user_session.get("supabase_access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _refresh_token() -> str | None:
    token = cl.user_session.get("supabase_refresh_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _set_auth_tokens(access_token: str, refresh_token: str | None) -> None:
    cl.user_session.set("supabase_access_token", access_token)
    cl.user_session.set("supabase_refresh_token", refresh_token)


def _clear_auth_tokens() -> None:
    cl.user_session.set("supabase_access_token", None)
    cl.user_session.set("supabase_refresh_token", None)


def _pending_oauth_state() -> str | None:
    state = cl.user_session.get("pending_oauth_state")
    if isinstance(state, str) and state.strip():
        return state.strip()
    return None


def _set_pending_oauth_state(state: str) -> None:
    cl.user_session.set("pending_oauth_state", state)


def _clear_pending_oauth_state() -> None:
    cl.user_session.set("pending_oauth_state", None)


def _headers() -> dict[str, str]:
    headers = {"X-Demo-Session": _session_id()}
    token = _auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _request(
    *,
    method: str,
    path: str,
    json_payload: dict[str, object] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    timeout: float = 45.0,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}{path}",
            json=json_payload,
            files=files,
            headers=_headers(),
        )

    if response.status_code == 401 and _refresh_token():
        refreshed, _ = await _supabase_refresh_session()
        if refreshed:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.request(
                    method,
                    f"{API_BASE_URL}{path}",
                    json=json_payload,
                    files=files,
                    headers=_headers(),
                )
    return response


async def _post(path: str, payload: dict[str, object]) -> httpx.Response:
    return await _request(method="POST", path=path, json_payload=payload, timeout=45.0)


async def _get(path: str) -> httpx.Response:
    return await _request(method="GET", path=path, timeout=20.0)


async def _post_files(
    path: str,
    files: dict[str, tuple[str, bytes, str]],
    *,
    timeout: float = 120.0,
) -> httpx.Response:
    return await _request(method="POST", path=path, files=files, timeout=timeout)


async def _supabase_password_login(email: str, password: str) -> tuple[bool, str]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "SUPABASE_URL and SUPABASE_ANON_KEY are required."

    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    payload = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        return False, f"Login failed: {response.text}"

    body = response.json()
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        return False, "Login failed: missing access/refresh token"

    _set_auth_tokens(access_token, refresh_token)
    return True, "Supabase login successful for this chat session."


async def _supabase_password_signup(email: str, password: str) -> tuple[bool, str]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "SUPABASE_URL and SUPABASE_ANON_KEY are required."

    url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    payload = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code not in {200, 201}:
        return False, f"Sign-up failed: {response.text}"

    body = response.json()
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    if isinstance(access_token, str):
        _set_auth_tokens(
            access_token, refresh_token if isinstance(refresh_token, str) else None
        )
        return True, "Sign-up successful and session attached to this chat."

    return (
        True,
        "Sign-up request submitted. Check your inbox for confirmation, then log in.",
    )


async def _supabase_refresh_session() -> tuple[bool, str]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "SUPABASE_URL and SUPABASE_ANON_KEY are required."

    refresh_token = _refresh_token()
    if not refresh_token:
        return False, "No refresh token in this chat session."

    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    payload = {"refresh_token": refresh_token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        return False, f"Refresh failed: {response.text}"

    body = response.json()
    access_token = body.get("access_token")
    next_refresh_token = body.get("refresh_token")
    if not isinstance(access_token, str) or not isinstance(next_refresh_token, str):
        return False, "Refresh failed: missing access/refresh token"

    _set_auth_tokens(access_token, next_refresh_token)
    return True, "Session refreshed successfully."


def _parse_oauth_callback_input(value: str) -> dict[str, str | None]:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        query = parse_qs(parsed.query)
        fragment = parse_qs(parsed.fragment)

        def first(name: str) -> str | None:
            values = query.get(name) or fragment.get(name)
            if not values:
                return None
            candidate = values[0].strip()
            return candidate or None

        return {
            "state": first("state"),
            "access_token": first("access_token"),
            "refresh_token": first("refresh_token"),
            "error": first("error_description") or first("error"),
        }

    tokens = value.split()
    access_token = tokens[0].strip() if tokens else ""
    refresh_token = tokens[1].strip() if len(tokens) > 1 else ""
    return {
        "state": _pending_oauth_state(),
        "access_token": access_token or None,
        "refresh_token": refresh_token or None,
        "error": None,
    }


async def _start_oauth(provider: str) -> tuple[bool, str]:
    response = await _post("/api/v1/auth/oauth/start", {"provider": provider})
    if response.status_code != 200:
        return False, f"OAuth start failed: {response.text}"
    body = response.json()
    authorize_url = body.get("authorize_url")
    state = body.get("state")
    if not isinstance(authorize_url, str) or not isinstance(state, str):
        return False, "OAuth start failed: invalid response payload"
    _set_pending_oauth_state(state)
    return (
        True,
        (
            f"Open this URL to authenticate with `{provider}`:\n{authorize_url}\n\n"
            "After sign-in, return to this chat and send any message. "
            "I will auto-link the OAuth session to this conversation."
        ),
    )


async def _claim_pending_oauth(*, notify: bool) -> bool:
    state = _pending_oauth_state()
    if not state:
        return False

    response = await _post("/api/v1/auth/oauth/claim", {"state": state})
    if response.status_code != 200:
        if notify:
            await cl.Message(content=f"OAuth claim failed: {response.text}").send()
        return False

    body = response.json()
    status = body.get("status")
    if status == "pending":
        return False
    if status in {"missing", "expired"}:
        _clear_pending_oauth_state()
        if notify:
            await cl.Message(
                content="OAuth session expired or missing. Start again with `/auth oauth <provider>`."
            ).send()
        return False
    if status != "complete":
        return False

    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    if not isinstance(access_token, str) or not access_token.strip():
        if notify:
            await cl.Message(content="OAuth claim returned no access token.").send()
        return False

    _set_auth_tokens(
        access_token.strip(),
        refresh_token if isinstance(refresh_token, str) else None,
    )
    _clear_pending_oauth_state()
    if notify:
        await cl.Message(content="OAuth session linked successfully.").send()
    return True


def _upload_error_hint(error_message: str | None) -> str:
    if not error_message:
        return "Retry upload. If this repeats, verify backend connectivity and auth."
    normalized = error_message.lower()
    if "unsupported" in normalized:
        return "Use PDF, DOCX, MD, or TXT and retry."
    if "parse" in normalized:
        return "File parsing failed. Try a cleaner export or another file format."
    if "supabase" in normalized:
        return "Supabase upsert failed. Verify auth token, RLS, and RPC schema setup."
    return "Retry upload. If it persists, inspect ingestion logs and backend status."


def _is_supported_upload(file_name: str, mime_type: str) -> bool:
    if mime_type in SUPPORTED_UPLOAD_MIME_TYPES:
        return True
    suffix = Path(file_name).suffix.lower()
    return suffix in SUPPORTED_UPLOAD_EXTENSIONS


async def _poll_ingestion_job(
    job_id: str, timeout_seconds: int = 120
) -> dict[str, object] | None:
    last_stage: str | None = None
    for _ in range(timeout_seconds):
        response = await _get(f"/api/v1/private/ingestion/jobs/{job_id}")
        if response.status_code != 200:
            await cl.Message(
                content=f"Ingestion polling failed: {response.text}"
            ).send()
            return None
        body = response.json()
        stage = body.get("stage")
        if isinstance(stage, str) and stage != last_stage:
            last_stage = stage
            await cl.Message(content=f"Ingestion update: `{stage}`.").send()

        status = body.get("status")
        if status in {"success", "failed"}:
            return body if isinstance(body, dict) else None
        await asyncio.sleep(1.0)

    await cl.Message(
        content="Ingestion is still processing. Check `/upload` status again shortly."
    ).send()
    return None


async def _show_trace_steps(trace: dict[str, object]) -> None:
    decisions = trace.get("decisions", [])
    if not isinstance(decisions, list):
        return

    for item in decisions:
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool_name", "tool"))
        rationale = str(item.get("rationale", ""))
        status = str(item.get("status", "ok"))
        latency_ms = item.get("latency_ms")
        attempt = item.get("attempt")
        latency_suffix = f" ({latency_ms} ms)" if isinstance(latency_ms, int) else ""
        attempt_suffix = f", attempt {attempt}" if isinstance(attempt, int) else ""
        async with cl.Step(name=tool_name, type="tool") as step:
            step.input = rationale
            step.output = f"status={status}{latency_suffix}{attempt_suffix}"


def _format_citations(citations: object) -> str:
    if not isinstance(citations, list) or not citations:
        return "No citations available."
    rows: list[str] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id")
        location = item.get("location")
        if isinstance(source_id, str) and isinstance(location, str):
            rows.append(f"- `{source_id}` at `{location}`")
    return "\n".join(rows) if rows else "No citations available."


@cl.on_chat_start
async def on_chat_start() -> None:
    _session_id()
    quota_response = await _get("/api/v1/demo/quota")
    remaining = "unknown"
    if quota_response.status_code == 200:
        body = quota_response.json()
        if isinstance(body, dict):
            value = body.get("remaining")
            if isinstance(value, int):
                remaining = str(value)

    await cl.Message(
        content=(
            "Welcome to Lattice Agentic Graph RAG.\n\n"
            "Commands:\n"
            "- `/key set <gemini_key>`\n"
            "- `/key clear`\n"
            "- `/key status`\n"
            "- `/auth set <supabase_jwt>`\n"
            "- `/auth signup <email> <password>`\n"
            "- `/auth login <email> <password>`\n"
            "- `/auth providers`\n"
            "- `/auth oauth <provider>`\n"
            "- `/auth callback <callback_url or tokens>`\n"
            "- `/auth refresh`\n"
            "- `/auth status`\n"
            "- `/auth clear`\n"
            "- `/upload` (private files require auth)\n\n"
            f"Current demo quota remaining: **{remaining}**"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    content = message.content.strip()
    await _claim_pending_oauth(notify=True)

    if content.startswith("/auth "):
        parts = content.split(" ", 2)
        action = parts[1] if len(parts) > 1 else ""

        if action == "signup":
            signup_parts = content.split(" ", 3)
            if len(signup_parts) < 4:
                await cl.Message(
                    content="Use `/auth signup <email> <password>`."
                ).send()
                return
            email = signup_parts[2].strip()
            password = signup_parts[3].strip()
            _, detail = await _supabase_password_signup(email, password)
            await cl.Message(content=detail).send()
            return

        if action == "login":
            login_parts = content.split(" ", 3)
            if len(login_parts) < 4:
                await cl.Message(content="Use `/auth login <email> <password>`.").send()
                return
            email = login_parts[2].strip()
            password = login_parts[3].strip()
            _, detail = await _supabase_password_login(email, password)
            await cl.Message(content=detail).send()
            return

        if action == "providers":
            response = await _get("/api/v1/auth/oauth/providers")
            if response.status_code != 200:
                await cl.Message(
                    content=f"Provider lookup failed: {response.text}"
                ).send()
                return
            body = response.json()
            providers = body.get("providers")
            if not isinstance(providers, list) or not providers:
                await cl.Message(content="No OAuth providers available.").send()
                return
            await cl.Message(
                content="OAuth providers: " + ", ".join(str(item) for item in providers)
            ).send()
            return

        if action in {"oauth", "oauth-url"}:
            if len(parts) < 3 or not parts[2].strip():
                await cl.Message(content="Use `/auth oauth <provider>`.").send()
                return
            provider = parts[2].strip().lower()
            ok, detail = await _start_oauth(provider)
            if not ok:
                await cl.Message(content=detail).send()
                return
            await cl.Message(content=detail).send()
            return

        if action == "callback":
            callback_parts = content.split(" ", 2)
            if len(callback_parts) < 3 or not callback_parts[2].strip():
                await cl.Message(
                    content="Use `/auth callback <callback_url or access_token [refresh_token]>`."
                ).send()
                return

            parsed = _parse_oauth_callback_input(callback_parts[2].strip())
            state = parsed.get("state")
            access_token = parsed.get("access_token")
            refresh_token = parsed.get("refresh_token")
            error = parsed.get("error")

            if isinstance(error, str) and error:
                await cl.Message(content=f"OAuth provider error: {error}").send()
                return

            if isinstance(state, str) and state:
                complete_payload = {
                    "state": state,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "error": error,
                }
                complete_response = await _post(
                    "/api/v1/auth/oauth/complete",
                    complete_payload,
                )
                if complete_response.status_code != 200:
                    await cl.Message(
                        content=f"OAuth callback completion failed: {complete_response.text}"
                    ).send()
                    return
                _set_pending_oauth_state(state)
                claimed = await _claim_pending_oauth(notify=False)
                if claimed:
                    await cl.Message(
                        content="OAuth callback linked successfully."
                    ).send()
                else:
                    await cl.Message(
                        content="OAuth callback stored. Send any message to finish linking."
                    ).send()
                return

            if isinstance(access_token, str) and access_token.strip():
                _set_auth_tokens(
                    access_token.strip(),
                    refresh_token if isinstance(refresh_token, str) else None,
                )
                await cl.Message(
                    content="Callback token(s) stored for this chat session."
                ).send()
                return

            await cl.Message(content="Missing callback state or access token.").send()
            return

        if action == "refresh":
            _, detail = await _supabase_refresh_session()
            await cl.Message(content=detail).send()
            return

        if action == "status":
            await _claim_pending_oauth(notify=False)
            has_access = bool(_auth_token())
            has_refresh = bool(_refresh_token())
            pending_state = _pending_oauth_state()
            next_step = (
                "Start auth with `/auth login` or `/auth oauth <provider>`."
                if not has_access
                else "You can now use `/upload` for private docs."
            )
            await cl.Message(
                content=(
                    f"Auth status:\n- access token: {has_access}\n"
                    f"- refresh token: {has_refresh}\n"
                    f"- pending oauth state: {bool(pending_state)}\n"
                    f"Next step: {next_step}"
                )
            ).send()
            return

        if action == "set" and len(parts) == 3 and parts[2].strip():
            _set_auth_tokens(parts[2].strip(), _refresh_token())
            await cl.Message(content="Supabase JWT set for this chat session.").send()
            return
        if action == "clear":
            _clear_auth_tokens()
            _clear_pending_oauth_state()
            await cl.Message(
                content="Supabase tokens and pending OAuth state cleared for this chat session."
            ).send()
            return
        await cl.Message(
            content=(
                "Use `/auth signup <email> <password>`, `/auth login <email> <password>`, "
                "`/auth providers`, `/auth oauth <provider>`, `/auth callback <callback_url or tokens>`, "
                "`/auth refresh`, `/auth status`, `/auth set <jwt>`, or `/auth clear`."
            )
        ).send()
        return

    if content.startswith("/key "):
        parts = content.split(" ", 2)
        action = parts[1] if len(parts) > 1 else "help"
        payload: dict[str, object] = {"action": action}
        if action == "set" and len(parts) == 3:
            payload["key"] = parts[2].strip()

        response = await _post("/api/v1/runtime/key", payload)
        if response.status_code != 200:
            await cl.Message(
                content=f"Runtime key command failed: {response.text}"
            ).send()
            return
        await cl.Message(content=f"Runtime key response: {response.json()}").send()
        return

    if content == "/upload":
        if not _auth_token():
            await cl.Message(
                content=(
                    "Upload is a private feature. Authenticate first with `/auth login` "
                    "or `/auth oauth <provider>`."
                )
            ).send()
            return

        files = await cl.AskFileMessage(
            content="Upload one PDF, DOCX, MD, or TXT file.",
            accept=[
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
                "text/markdown",
            ],
            max_files=1,
            max_size_mb=25,
            timeout=120,
        ).send()
        if not files:
            await cl.Message(content="Upload cancelled.").send()
            return

        file_response = files[0]
        file_path = Path(file_response.path)
        if not file_path.exists():
            await cl.Message(content="Upload path not found.").send()
            return

        file_name = file_response.name or file_path.name
        mime_type = file_response.type or "application/octet-stream"
        if not _is_supported_upload(file_name, mime_type):
            await cl.Message(
                content=(
                    "Unsupported upload type. Use one of: PDF, DOCX, MD, TXT. "
                    f"Detected file `{file_name}` with MIME `{mime_type}`."
                )
            ).send()
            return

        file_bytes = file_path.read_bytes()
        response = await _post_files(
            "/api/v1/private/ingestion/upload",
            {
                "file": (
                    file_name,
                    file_bytes,
                    mime_type,
                )
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            await cl.Message(content=f"Upload failed: {response.text}").send()
            return

        body = response.json()
        job_id = body.get("job_id")
        if not isinstance(job_id, str):
            await cl.Message(content=f"Upload response missing job_id: {body}").send()
            return

        await cl.Message(
            content=(
                f"Ingestion queued for `{file_name}` (job `{job_id}`). "
                "I will monitor progress to completion."
            )
        ).send()

        final_job = await _poll_ingestion_job(job_id)
        if not isinstance(final_job, dict):
            return

        final_status = final_job.get("status")
        final_stage = final_job.get("stage")
        chunk_count = final_job.get("chunk_count")
        error_message = final_job.get("error_message")
        if final_status == "success":
            await cl.Message(
                content=(
                    f"Ingestion complete: status=`{final_status}`, stage=`{final_stage}`, "
                    f"chunks={chunk_count}. Ask a question about `{file_name}` now."
                )
            ).send()
            return

        hint = _upload_error_hint(
            error_message if isinstance(error_message, str) else None
        )
        await cl.Message(
            content=(
                f"Ingestion failed at stage `{final_stage}`: {error_message}\n"
                f"Suggested fix: {hint}"
            )
        ).send()
        return

    response = await _post(
        "/api/v1/query",
        {"question": content, "thread_id": cl.user_session.get("thread_id")},
    )
    if response.status_code != 200:
        await cl.Message(content=f"Query failed: {response.text}").send()
        return

    payload = response.json()
    thread_id = payload.get("thread_id")
    if isinstance(thread_id, str):
        cl.user_session.set("thread_id", thread_id)

    trace = payload.get("trace")
    if isinstance(trace, dict):
        await _show_trace_steps(trace)

    answer = str(payload.get("answer", ""))
    confidence = str(payload.get("confidence", "unknown"))
    policy = str(payload.get("policy", "unknown"))
    action = str(payload.get("action", ""))
    rerank_strategy = str(payload.get("rerank_strategy", "unknown"))
    citations_md = _format_citations(payload.get("citations"))
    quota = payload.get("demo_quota_remaining")
    quota_line = (
        f"\n\nDemo quota remaining: **{quota}**" if isinstance(quota, int) else ""
    )

    await cl.Message(
        content=(
            f"{answer}\n\n"
            f"Confidence: **{confidence}**\n\n"
            f"Policy: **{policy}**\n"
            f"Rerank: **{rerank_strategy}**\n"
            f"Next action: {action}\n\n"
            f"Citations:\n{citations_md}{quota_line}"
        )
    ).send()
