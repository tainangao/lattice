from __future__ import annotations

from lattice.app.memory.contracts import ConversationTurn
from lattice.app.runtime.store import RuntimeStore

FOLLOW_UP_HINTS = {
    "that movie",
    "this movie",
    "that doc",
    "this doc",
    "that file",
    "this file",
    "that relationship",
    "that result",
    "those findings",
}


def append_turn(
    *,
    store: RuntimeStore,
    thread_id: str,
    role: str,
    content: str,
) -> None:
    turns = store.conversation_turns_by_thread.setdefault(thread_id, [])
    turns.append(ConversationTurn(role=role, content=content))


def get_recent_turns(
    *,
    store: RuntimeStore,
    thread_id: str,
    limit: int = 6,
) -> tuple[ConversationTurn, ...]:
    turns = store.conversation_turns_by_thread.get(thread_id, [])
    return tuple(turns[-limit:])


def resolve_follow_up_question(
    *,
    store: RuntimeStore,
    thread_id: str,
    question: str,
) -> tuple[str, str | None]:
    normalized = question.lower().strip()
    if not any(hint in normalized for hint in FOLLOW_UP_HINTS):
        return question, None

    turns = store.conversation_turns_by_thread.get(thread_id, [])
    last_user_turn = next(
        (turn for turn in reversed(turns) if turn.role == "user"), None
    )
    if not last_user_turn:
        return question, None

    resolved = (
        f"{question}\n\n"
        f"Follow-up context from prior user turn: {last_user_turn.content}"
    )
    return resolved, "resolved follow-up reference using previous user turn"
