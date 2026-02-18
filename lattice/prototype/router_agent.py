from __future__ import annotations

import re

from lattice.prototype.models import RetrievalMode, RouteDecision

GREETING_PATTERNS = [
    r"^hi\b",
    r"^hello\b",
    r"^hey\b",
    r"^good (morning|afternoon|evening)\b",
]
DOCUMENT_HINTS = {"pdf", "document", "file", "timeline", "policy", "upload"}
GRAPH_HINTS = {
    "graph",
    "dependency",
    "dependencies",
    "relationship",
    "owner",
    "hierarchy",
}


def route_question(question: str) -> RouteDecision:
    normalized = question.strip().lower()
    if _is_greeting(normalized):
        return RouteDecision(mode=RetrievalMode.DIRECT, reason="Greeting detected")

    tokens = set(re.findall(r"[a-zA-Z0-9_]+", normalized))
    wants_docs = bool(tokens.intersection(DOCUMENT_HINTS))
    wants_graph = bool(tokens.intersection(GRAPH_HINTS))

    if wants_docs and wants_graph:
        return RouteDecision(
            mode=RetrievalMode.BOTH, reason="Query needs document and graph context"
        )
    if wants_docs:
        return RouteDecision(
            mode=RetrievalMode.DOCUMENT, reason="Query needs document context"
        )
    if wants_graph:
        return RouteDecision(
            mode=RetrievalMode.GRAPH, reason="Query needs graph context"
        )
    return RouteDecision(
        mode=RetrievalMode.BOTH, reason="Default to hybrid retrieval for prototype"
    )


def _is_greeting(normalized_question: str) -> bool:
    return any(re.match(pattern, normalized_question) for pattern in GREETING_PATTERNS)
