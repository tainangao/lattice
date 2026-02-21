from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionJob:
    job_id: str
    status: str
