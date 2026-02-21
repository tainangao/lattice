from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolTrace:
    tool_name: str
    latency_ms: int
    status: str
    error_message: str | None = None
    attempt: int = 1


@dataclass(frozen=True)
class QueryTrace:
    trace_id: str
    route: str
    confidence: str
    access_mode: str
    latency_ms: int
