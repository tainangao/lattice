from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import chainlit as cl
import httpx

API_BASE_URL = os.getenv("LATTICE_API_URL", "http://localhost:8000").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


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


def _headers() -> dict[str, str]:
    headers = {"X-Demo-Session": _session_id()}
    token = _auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _post(path: str, payload: dict[str, object]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45.0) as client:
        return await client.post(
            f"{API_BASE_URL}{path}",
            json=payload,
            headers=_headers(),
        )


async def _get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=20.0) as client:
        return await client.get(f"{API_BASE_URL}{path}", headers=_headers())


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

    cl.user_session.set("supabase_access_token", access_token)
    cl.user_session.set("supabase_refresh_token", refresh_token)
    return True, "Supabase login successful for this chat session."


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

    cl.user_session.set("supabase_access_token", access_token)
    cl.user_session.set("supabase_refresh_token", next_refresh_token)
    return True, "Session refreshed successfully."


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
            "- `/auth login <email> <password>`\n"
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

    if content.startswith("/auth "):
        parts = content.split(" ", 2)
        action = parts[1] if len(parts) > 1 else ""

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

        if action == "refresh":
            _, detail = await _supabase_refresh_session()
            await cl.Message(content=detail).send()
            return

        if action == "status":
            has_access = bool(_auth_token())
            has_refresh = bool(_refresh_token())
            await cl.Message(
                content=(
                    f"Auth status:\n- access token: {has_access}\n"
                    f"- refresh token: {has_refresh}"
                )
            ).send()
            return

        if action == "set" and len(parts) == 3 and parts[2].strip():
            cl.user_session.set("supabase_access_token", parts[2].strip())
            await cl.Message(content="Supabase JWT set for this chat session.").send()
            return
        if action == "clear":
            cl.user_session.set("supabase_access_token", None)
            cl.user_session.set("supabase_refresh_token", None)
            await cl.Message(
                content="Supabase tokens cleared for this chat session."
            ).send()
            return
        await cl.Message(
            content=(
                "Use `/auth login <email> <password>`, `/auth refresh`, `/auth status`, "
                "`/auth set <jwt>`, or `/auth clear`."
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
                    "Upload is a private feature. Set auth first with `/auth set <supabase_jwt>` "
                    "to enable private ingestion."
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

        file_bytes = file_path.read_bytes()
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/private/ingestion/upload",
                headers=_headers(),
                files={
                    "file": (
                        file_response.name,
                        file_bytes,
                        file_response.type or "application/octet-stream",
                    )
                },
            )

        if response.status_code != 200:
            await cl.Message(content=f"Upload failed: {response.text}").send()
            return
        await cl.Message(content=f"Ingestion queued: {response.json()}").send()
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
    citations_md = _format_citations(payload.get("citations"))
    quota = payload.get("demo_quota_remaining")
    quota_line = (
        f"\n\nDemo quota remaining: **{quota}**" if isinstance(quota, int) else ""
    )

    await cl.Message(
        content=(
            f"{answer}\n\n"
            f"Confidence: **{confidence}**\n\n"
            f"Citations:\n{citations_md}{quota_line}"
        )
    ).send()
