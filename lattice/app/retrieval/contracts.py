from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    score: float
    content: str
    source_type: str
    location: str


@dataclass(frozen=True)
class RetrievalBundle:
    route: str
    hits: tuple[RetrievalHit, ...]
