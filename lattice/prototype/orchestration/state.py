from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from lattice.prototype.models import RetrievalMode, SourceSnippet


class OrchestrationState(TypedDict, total=False):
    request_id: str
    question: str
    runtime_user_id: str | None
    runtime_access_token: str | None
    route_mode: RetrievalMode | None
    route_reason: str | None
    document_snippets: list[SourceSnippet]
    graph_snippets: list[SourceSnippet]
    snippets: list[SourceSnippet]
    answer: str | None
    critic_confidence: float | None
    critic_needs_refinement: bool
    critic_reason_codes: list[str]
    refinement_attempt: int
    retrieval_limit: int
    telemetry_events: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]


def create_initial_state(
    question: str,
    request_id: str = "unknown",
    retrieval_limit: int = 3,
    runtime_user_id: str | None = None,
    runtime_access_token: str | None = None,
) -> OrchestrationState:
    return {
        "request_id": request_id,
        "question": question,
        "runtime_user_id": runtime_user_id,
        "runtime_access_token": runtime_access_token,
        "route_mode": None,
        "route_reason": None,
        "document_snippets": [],
        "graph_snippets": [],
        "snippets": [],
        "answer": None,
        "critic_confidence": None,
        "critic_needs_refinement": False,
        "critic_reason_codes": [],
        "refinement_attempt": 0,
        "retrieval_limit": retrieval_limit,
        "telemetry_events": [],
        "errors": [],
    }
