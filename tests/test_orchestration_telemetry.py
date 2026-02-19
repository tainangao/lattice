import logging

from lattice.prototype.models import RetrievalMode
from lattice.prototype.orchestration.telemetry import (
    build_graph_invoke_config,
    emit_orchestration_telemetry,
)


def test_build_graph_invoke_config_includes_tags_and_request_id() -> None:
    config = build_graph_invoke_config("req-123")

    assert config["tags"] == ["phase3-orchestration"]
    assert config["metadata"]["request_id"] == "req-123"


def test_emit_orchestration_telemetry_logs_structured_events(
    caplog,
) -> None:
    state = {
        "request_id": "req-123",
        "route_mode": RetrievalMode.BOTH,
        "snippets": [{"source_type": "document", "source_id": "doc#1"}],
        "telemetry_events": [
            {
                "event": "graph_branch_completed",
                "count": 1,
                "fallback_used": True,
                "error_class": "RuntimeError",
                "retriever_mode": "seeded_fallback",
            }
        ],
    }

    logger = logging.getLogger("test.telemetry")
    with caplog.at_level(logging.INFO, logger="test.telemetry"):
        emit_orchestration_telemetry(state, logger=logger)

    assert any("orchestration_event" in message for message in caplog.messages)
    assert any('"request_id": "req-123"' in message for message in caplog.messages)
    assert any('"fallback_used": true' in message for message in caplog.messages)
    assert any(
        '"error_class": "RuntimeError"' in message for message in caplog.messages
    )
    assert any(
        '"retriever_mode": "seeded_fallback"' in message for message in caplog.messages
    )
