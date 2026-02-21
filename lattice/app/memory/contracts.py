from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationRef:
    thread_id: str
    user_id: str | None


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str
