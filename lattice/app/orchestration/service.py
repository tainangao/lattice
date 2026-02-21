from __future__ import annotations

import operator
from typing import Annotated, Literal
from typing import TypedDict

from lattice.app.graph.neo4j_store import Neo4jGraphStore
from lattice.app.orchestration.contracts import RouteDecision
from lattice.app.response.contracts import AnswerEnvelope
from lattice.app.response.service import build_answer
from lattice.app.retrieval.contracts import RetrievalBundle, RetrievalHit
from lattice.app.retrieval.embeddings import EmbeddingProvider
from lattice.app.retrieval.service import retrieve
from lattice.app.retrieval.supabase_store import SupabaseVectorStore
from lattice.app.runtime.store import RuntimeStore

GRAPH_HINTS = {"graph", "relationship", "depends", "netflix", "cypher"}
DOC_HINTS = {"document", "doc", "pdf", "docx", "file", "notes", "report", "upload"}
COUNT_HINTS = {"count", "how many", "number of", "total"}


class OrchestrationResult(TypedDict):
    route: str
    route_reason: str
    retrieval: RetrievalBundle
    answer: AnswerEnvelope


class _GraphState(TypedDict, total=False):
    question: str
    user_id: str | None
    user_access_token: str | None
    route: str
    route_reason: str
    doc_hits: Annotated[tuple[RetrievalHit, ...], operator.add]
    graph_hits: Annotated[tuple[RetrievalHit, ...], operator.add]
    retrieval: RetrievalBundle
    answer: AnswerEnvelope


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


def _run_without_langgraph(
    *,
    store: RuntimeStore,
    question: str,
    user_id: str | None,
    user_access_token: str | None,
    embedding_provider: EmbeddingProvider,
    supabase_store: SupabaseVectorStore | None,
    neo4j_store: Neo4jGraphStore | None,
) -> OrchestrationResult:
    route_decision = select_route(question)
    retrieval = retrieve(
        store=store,
        route=route_decision.path,
        query=question,
        user_id=user_id,
        user_access_token=user_access_token,
        embedding_provider=embedding_provider,
        supabase_store=supabase_store,
        neo4j_store=neo4j_store,
    )
    answer = build_answer(question, retrieval)
    return {
        "route": route_decision.path,
        "route_reason": route_decision.reason,
        "retrieval": retrieval,
        "answer": answer,
    }


def run_orchestration(
    *,
    store: RuntimeStore,
    question: str,
    user_id: str | None,
    user_access_token: str | None,
    embedding_provider: EmbeddingProvider,
    supabase_store: SupabaseVectorStore | None,
    neo4j_store: Neo4jGraphStore | None,
    use_langgraph: bool,
) -> OrchestrationResult:
    if not use_langgraph:
        return _run_without_langgraph(
            store=store,
            question=question,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )

    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:
        return _run_without_langgraph(
            store=store,
            question=question,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )

    def router_node(state: _GraphState) -> _GraphState:
        decision = select_route(state["question"])
        return {"route": decision.path, "route_reason": decision.reason}

    def single_retrieval_node(state: _GraphState) -> _GraphState:
        retrieval = retrieve(
            store=store,
            route=state["route"],
            query=state["question"],
            user_id=state.get("user_id"),
            user_access_token=state.get("user_access_token"),
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )
        return {"retrieval": retrieval}

    def document_branch_node(state: _GraphState) -> _GraphState:
        if state["route"] not in {"document", "hybrid"}:
            return {"doc_hits": tuple()}
        document_bundle = retrieve(
            store=store,
            route="document",
            query=state["question"],
            user_id=state.get("user_id"),
            user_access_token=state.get("user_access_token"),
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )
        return {"doc_hits": document_bundle.hits}

    def graph_branch_node(state: _GraphState) -> _GraphState:
        if state["route"] not in {"graph", "hybrid"}:
            return {"graph_hits": tuple()}
        graph_bundle = retrieve(
            store=store,
            route="graph",
            query=state["question"],
            user_id=state.get("user_id"),
            user_access_token=state.get("user_access_token"),
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )
        return {"graph_hits": graph_bundle.hits}

    def merge_retrieval_node(state: _GraphState) -> _GraphState:
        doc_hits = list(state.get("doc_hits", tuple()))
        graph_hits = list(state.get("graph_hits", tuple()))

        if state["route"] == "document":
            return {
                "retrieval": RetrievalBundle(route="document", hits=tuple(doc_hits[:5]))
            }
        if state["route"] == "graph":
            return {
                "retrieval": RetrievalBundle(route="graph", hits=tuple(graph_hits[:5]))
            }

        deduped: dict[str, RetrievalHit] = {}
        ranked = sorted(doc_hits + graph_hits, key=lambda row: row.score, reverse=True)
        for hit in ranked:
            if hit.source_id not in deduped:
                deduped[hit.source_id] = hit
        return {
            "retrieval": RetrievalBundle(
                route="hybrid",
                hits=tuple(list(deduped.values())[:6]),
            )
        }

    def route_mode(state: _GraphState) -> Literal["single", "parallel"]:
        if state["route"] in {"direct", "aggregate"}:
            return "single"
        return "parallel"

    def route_targets(state: _GraphState) -> str | list[str]:
        if route_mode(state) == "single":
            return "single_retrieval"
        return ["document_branch", "graph_branch"]

    def synthesis_node(state: _GraphState) -> _GraphState:
        answer = build_answer(state["question"], state["retrieval"])
        return {"answer": answer}

    graph = StateGraph(_GraphState)
    graph.add_node("router", router_node)
    graph.add_node("single_retrieval", single_retrieval_node)
    graph.add_node("document_branch", document_branch_node)
    graph.add_node("graph_branch", graph_branch_node)
    graph.add_node("merge_retrieval", merge_retrieval_node)
    graph.add_node("synthesis", synthesis_node)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_targets,
        ["single_retrieval", "document_branch", "graph_branch"],
    )
    graph.add_edge("single_retrieval", "synthesis")
    graph.add_edge("document_branch", "merge_retrieval")
    graph.add_edge("graph_branch", "merge_retrieval")
    graph.add_edge("merge_retrieval", "synthesis")
    graph.add_edge("synthesis", END)

    compiled = graph.compile()
    output = compiled.invoke(
        {
            "question": question,
            "user_id": user_id,
            "user_access_token": user_access_token,
            "doc_hits": tuple(),
            "graph_hits": tuple(),
        }
    )

    return {
        "route": output["route"],
        "route_reason": output["route_reason"],
        "retrieval": output["retrieval"],
        "answer": output["answer"],
    }
