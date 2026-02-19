from __future__ import annotations

import json
import logging
from typing import Any

from lattice.prototype.models import RetrievalMode

DEFAULT_TELEMETRY_TAG = "phase3-orchestration"


def build_graph_invoke_config(request_id: str) -> dict[str, Any]:
    return {
        "tags": [DEFAULT_TELEMETRY_TAG],
        "metadata": {
            "request_id": request_id,
            "component": "prototype_orchestration",
        },
    }


def emit_orchestration_telemetry(
    state: dict[str, Any],
    logger: logging.Logger | None = None,
) -> None:
    active_logger = logger or logging.getLogger(__name__)
    request_id = _request_id(state)
    mode = _mode_value(state.get("route_mode"))
    snippet_count = _snippet_count(state.get("snippets"))

    for event in _events(state.get("telemetry_events")):
        payload = {
            "request_id": request_id,
            "mode": mode,
            "snippet_count": snippet_count,
            **event,
        }
        active_logger.info(
            "orchestration_event %s", json.dumps(payload, sort_keys=True)
        )


def _request_id(state: dict[str, Any]) -> str:
    request_id = state.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        return request_id
    return "unknown"


def _mode_value(mode: Any) -> str | None:
    if isinstance(mode, RetrievalMode):
        return mode.value
    if isinstance(mode, str) and mode.strip():
        return mode
    return None


def _snippet_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 0


def _events(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [event for event in value if isinstance(event, dict)]
