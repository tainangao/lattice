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
HYBRID_INTENT_HINTS = {"compare", "comparison", "versus", "vs", "between", "across"}
NETFLIX_GRAPH_HINTS = {
    "title",
    "titles",
    "genre",
    "genres",
    "actor",
    "actors",
    "cast",
    "director",
    "directors",
    "rating",
    "ratings",
    "thriller",
    "thrillers",
    "drama",
    "dramas",
    "comedy",
    "comedies",
    "movie",
    "movies",
    "show",
    "shows",
    "tv",
}


def route_question(question: str) -> RouteDecision:
    normalized = question.strip().lower()
    if _is_greeting(normalized):
        return RouteDecision(mode=RetrievalMode.DIRECT, reason="Greeting detected")

    tokens = set(re.findall(r"[a-zA-Z0-9_]+", normalized))
    document_score = _match_score(tokens, DOCUMENT_HINTS)
    graph_score = _match_score(tokens, GRAPH_HINTS.union(NETFLIX_GRAPH_HINTS))

    if tokens.intersection(HYBRID_INTENT_HINTS) and document_score and graph_score:
        return RouteDecision(
            mode=RetrievalMode.BOTH,
            reason="Query has comparison intent across sources",
        )

    wants_docs = document_score > 0
    wants_graph = graph_score > 0

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


def _match_score(tokens: set[str], hints: set[str]) -> int:
    return len(tokens.intersection(hints))
