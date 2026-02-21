from __future__ import annotations

import time
from uuid import uuid4

from lattice.app.observability.contracts import QueryTrace, ToolTrace


def create_trace(
    route: str,
    confidence: str,
    access_mode: str,
    latency_ms: int,
) -> QueryTrace:
    return QueryTrace(
        trace_id=f"trace-{uuid4().hex[:10]}",
        route=route,
        confidence=confidence,
        access_mode=access_mode,
        latency_ms=latency_ms,
    )


def tool_trace(
    tool_name: str,
    started_at: float,
    *,
    status: str = "ok",
    error_message: str | None = None,
    attempt: int = 1,
) -> ToolTrace:
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return ToolTrace(
        tool_name=tool_name,
        latency_ms=max(elapsed_ms, 0),
        status=status,
        error_message=error_message,
        attempt=attempt,
    )
