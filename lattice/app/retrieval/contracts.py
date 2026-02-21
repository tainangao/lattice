from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    score: float
