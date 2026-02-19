from __future__ import annotations

import os

import chainlit as cl

from lattice.prototype.config import load_config, with_runtime_gemini_key
from lattice.prototype.service import PrototypeService


DEFAULT_PUBLIC_DEMO_QUERY_LIMIT = 3


@cl.on_chat_start
async def on_chat_start() -> None:
    demo_limit = _resolve_demo_query_limit(os.getenv("PUBLIC_DEMO_QUERY_LIMIT"))
    cl.user_session.set("demo_queries_used", 0)
    await cl.Message(content=_build_welcome_message(demo_limit)).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    command = message.content.strip()
    if command.lower() == "/help":
        await cl.Message(content=_help_message()).send()
        return

    if command.lower() == "/clearkey":
        cl.user_session.set("gemini_api_key", None)
        await cl.Message(content="Session Gemini key removed for this chat.").send()
        return

    if message.content.lower().startswith("/setkey "):
        provided_key = message.content.split(" ", 1)[1].strip()
        cl.user_session.set("gemini_api_key", provided_key)
        masked = _mask_key(provided_key)
        await cl.Message(
            content=(f"Session Gemini key updated for this chat only (`{masked}`).")
        ).send()
        return

    demo_limit = _resolve_demo_query_limit(os.getenv("PUBLIC_DEMO_QUERY_LIMIT"))
    used_count = _resolve_demo_queries_used(cl.user_session.get("demo_queries_used"))
    has_session_key = _has_session_key(cl.user_session.get("gemini_api_key"))

    if _is_demo_quota_exhausted(
        has_session_key=has_session_key,
        used_count=used_count,
        demo_limit=demo_limit,
    ):
        await cl.Message(content=_quota_exhausted_message(demo_limit)).send()
        return

    runtime_key = cl.user_session.get("gemini_api_key")
    effective_key = runtime_key if isinstance(runtime_key, str) else None
    config = with_runtime_gemini_key(load_config(), effective_key)
    service = PrototypeService(config)

    if not has_session_key:
        cl.user_session.set("demo_queries_used", used_count + 1)

    route_step = cl.Step(name="Router Agent", type="tool")
    await route_step.send()
    result = await service.run_query(message.content)
    route_step.output = f"{result.route.mode.value}: {result.route.reason}"
    await route_step.update()

    snippet_lines = [
        f"- [{item.source_type}] {item.source_id} (score={item.score:.2f})"
        for item in result.snippets
    ]
    snippets_block = (
        "\n".join(snippet_lines) if snippet_lines else "- no retrieval snippets"
    )
    remaining = _remaining_demo_queries(
        demo_limit=demo_limit,
        used_count=used_count + (0 if has_session_key else 1),
    )
    footer = _build_demo_footer(has_session_key=has_session_key, remaining=remaining)
    await cl.Message(
        content=f"{result.answer}\n\nSources:\n{snippets_block}{footer}"
    ).send()


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def _resolve_demo_query_limit(raw_value: str | None) -> int:
    if raw_value is None:
        return DEFAULT_PUBLIC_DEMO_QUERY_LIMIT
    try:
        parsed = int(raw_value)
    except ValueError:
        return DEFAULT_PUBLIC_DEMO_QUERY_LIMIT
    return max(parsed, 0)


def _resolve_demo_queries_used(value: object) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _has_session_key(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_demo_quota_exhausted(
    has_session_key: bool,
    used_count: int,
    demo_limit: int,
) -> bool:
    return not has_session_key and demo_limit >= 0 and used_count >= demo_limit


def _remaining_demo_queries(demo_limit: int, used_count: int) -> int:
    return max(demo_limit - used_count, 0)


def _build_welcome_message(demo_limit: int) -> str:
    return (
        "Welcome to Lattice Phase 5 preview.\n\n"
        "- Ask questions about project timelines, dependencies, and ownership links.\n"
        "- Public demo mode includes a limited number of queries per chat session.\n"
        f"- Remaining in this session: {demo_limit}.\n"
        "- Use `/setkey <gemini-key>` for your own key, `/clearkey` to remove it, and `/help` for commands."
    )


def _help_message() -> str:
    return (
        "Available commands:\n"
        "- `/setkey <gemini-key>`: use your own Gemini key for this session only\n"
        "- `/clearkey`: remove the session key\n"
        "- `/help`: show this command list"
    )


def _quota_exhausted_message(demo_limit: int) -> str:
    return (
        "Public demo quota reached for this session "
        f"({demo_limit} queries). Use `/setkey <gemini-key>` to continue."
    )


def _build_demo_footer(has_session_key: bool, remaining: int) -> str:
    if has_session_key:
        return "\n\nSession key mode: active."
    return f"\n\nPublic demo queries remaining in this session: {remaining}."
