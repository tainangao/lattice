from __future__ import annotations

from lattice.app.orchestration.contracts import RouteDecision

GRAPH_HINTS = {"graph", "relationship", "depends", "netflix", "cypher"}
DOC_HINTS = {"document", "doc", "pdf", "file", "notes", "report", "upload"}
COUNT_HINTS = {"count", "how many", "number of", "total"}


def select_route(query: str) -> RouteDecision:
    normalized = query.lower()
    has_graph = any(token in normalized for token in GRAPH_HINTS)
    has_docs = any(token in normalized for token in DOC_HINTS)
    is_count = any(token in normalized for token in COUNT_HINTS)

    if is_count:
        return RouteDecision(path="aggregate", reason="count-oriented request")
    if has_graph and has_docs:
        return RouteDecision(
            path="hybrid", reason="question references graph and files"
        )
    if has_graph:
        return RouteDecision(
            path="graph", reason="question maps to relationship lookup"
        )
    if has_docs:
        return RouteDecision(path="document", reason="question targets private files")
    return RouteDecision(path="direct", reason="no retrieval hint detected")
