from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from lattice.prototype.models import RetrievalMode, SourceSnippet


class OrchestrationState(TypedDict, total=False):
    request_id: str
    question: str
    route_mode: RetrievalMode | None
    route_reason: str | None
    document_snippets: Annotated[list[SourceSnippet], operator.add]
    graph_snippets: Annotated[list[SourceSnippet], operator.add]
    snippets: list[SourceSnippet]
    answer: str | None
    telemetry_events: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]


def create_initial_state(
    question: str,
    request_id: str = "unknown",
) -> OrchestrationState:
    return {
        "request_id": request_id,
        "question": question,
        "route_mode": None,
        "route_reason": None,
        "document_snippets": [],
        "graph_snippets": [],
        "snippets": [],
        "answer": None,
        "telemetry_events": [],
        "errors": [],
    }
