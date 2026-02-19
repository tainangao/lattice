from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from lattice.prototype.models import RetrievalMode

from .nodes import (
    document_retrieval_node,
    finalize_node,
    graph_retrieval_node,
    merge_node,
    router_node,
    synthesize_node,
)
from .state import OrchestrationState


def build_orchestration_graph():
    graph_builder = StateGraph(OrchestrationState)

    graph_builder.add_node("router", router_node)
    graph_builder.add_node("document_retrieval", document_retrieval_node)
    graph_builder.add_node("graph_retrieval", graph_retrieval_node)
    graph_builder.add_node("merge", merge_node)
    graph_builder.add_node("synthesize", synthesize_node)
    graph_builder.add_node("finalize", finalize_node)

    graph_builder.add_edge(START, "router")
    graph_builder.add_conditional_edges("router", _route_after_router)

    graph_builder.add_edge("document_retrieval", "merge")
    graph_builder.add_edge("graph_retrieval", "merge")
    graph_builder.add_edge("merge", "synthesize")
    graph_builder.add_edge("synthesize", "finalize")
    graph_builder.add_edge("finalize", END)

    return graph_builder.compile()


def _route_after_router(state: OrchestrationState) -> str | list[str]:
    mode = state.get("route_mode")
    if mode == RetrievalMode.DIRECT:
        return "synthesize"
    if mode == RetrievalMode.DOCUMENT:
        return "document_retrieval"
    if mode == RetrievalMode.GRAPH:
        return "graph_retrieval"
    return ["document_retrieval", "graph_retrieval"]
