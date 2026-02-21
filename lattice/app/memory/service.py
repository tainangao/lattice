from __future__ import annotations

from lattice.app.memory.contracts import ConversationTurn
from lattice.app.runtime.store import RuntimeStore


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
