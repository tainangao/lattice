from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from lattice.prototype.models import RetrievalMode
from lattice.prototype.orchestration.nodes import Retriever

from .nodes import (
    make_critic_node,
    make_document_retrieval_node,
    make_finalize_node,
    make_graph_retrieval_node,
    make_refinement_node,
    make_synthesize_node,
    merge_node,
    router_node,
)
from .state import OrchestrationState


def build_orchestration_graph(
    document_retriever: Retriever | None,
    graph_retriever: Retriever | None,
    seed_document_retriever: Retriever,
    seed_graph_retriever: Retriever,
    allow_seeded_fallback: bool,
    gemini_api_key: str | None,
    phase4_enable_critic: bool,
    phase4_confidence_threshold: float,
    phase4_min_snippets: int,
    phase4_max_refinement_rounds: int,
    phase4_refinement_retrieval_limit: int,
):
    graph_builder = StateGraph(OrchestrationState)

    document_node = make_document_retrieval_node(
        primary_retriever=document_retriever,
        fallback_retriever=seed_document_retriever,
        allow_seeded_fallback=allow_seeded_fallback,
    )
    graph_node = make_graph_retrieval_node(
        primary_retriever=graph_retriever,
        fallback_retriever=seed_graph_retriever,
        allow_seeded_fallback=allow_seeded_fallback,
    )
    synthesize_node = make_synthesize_node(gemini_api_key)
    critic_node = make_critic_node(
        confidence_threshold=phase4_confidence_threshold,
        min_snippets=phase4_min_snippets,
        max_refinement_rounds=phase4_max_refinement_rounds,
        enable_critic=phase4_enable_critic,
    )
    refinement_node = make_refinement_node(phase4_refinement_retrieval_limit)
    finalize_node = make_finalize_node(phase4_confidence_threshold)

    graph_builder.add_node("router", router_node)
    graph_builder.add_node("document_retrieval", document_node)
    graph_builder.add_node("graph_retrieval", graph_node)
    graph_builder.add_node("merge", merge_node)
    graph_builder.add_node("synthesize", synthesize_node)
    graph_builder.add_node("critic", critic_node)
    graph_builder.add_node("refine", refinement_node)
    graph_builder.add_node("finalize", finalize_node)

    graph_builder.add_edge(START, "router")
    graph_builder.add_conditional_edges("router", _route_after_router)

    graph_builder.add_edge("document_retrieval", "merge")
    graph_builder.add_edge("graph_retrieval", "merge")
    graph_builder.add_edge("merge", "synthesize")
    graph_builder.add_edge("synthesize", "critic")
    graph_builder.add_conditional_edges("critic", _route_after_critic)
    graph_builder.add_conditional_edges("refine", _route_after_refine)
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


def _route_after_critic(state: OrchestrationState) -> str:
    if state.get("critic_needs_refinement"):
        return "refine"
    return "finalize"


def _route_after_refine(state: OrchestrationState) -> str | list[str]:
    mode = state.get("route_mode")
    if mode == RetrievalMode.DOCUMENT:
        return "document_retrieval"
    if mode == RetrievalMode.GRAPH:
        return "graph_retrieval"
    if mode == RetrievalMode.BOTH:
        return ["document_retrieval", "graph_retrieval"]
    return "finalize"
