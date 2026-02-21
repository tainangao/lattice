from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    path: str
    reason: str


@dataclass(frozen=True)
class ToolDecision:
    tool_name: str
    rationale: str
    latency_ms: int | None = None
    status: str = "ok"
    attempt: int = 1
