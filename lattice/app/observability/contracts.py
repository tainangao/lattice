from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolTrace:
    tool_name: str
    latency_ms: int
