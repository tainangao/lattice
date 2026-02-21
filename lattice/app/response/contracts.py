from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    source_id: str
    location: str


@dataclass(frozen=True)
class AnswerEnvelope:
    answer: str
    confidence: str
    citations: tuple[Citation, ...]
    policy: str
    action: str
