from __future__ import annotations

import operator
import time
from typing import Annotated, Literal
from typing import TypedDict

from lattice.app.graph.neo4j_store import Neo4jGraphStore
from lattice.app.llm.providers import CriticModel
from lattice.app.orchestration.contracts import RouteDecision, ToolDecision
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
    tool_decisions: tuple[ToolDecision, ...]


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
    router_started = time.perf_counter()
    route_decision = select_route(question)
    router_latency_ms = int((time.perf_counter() - router_started) * 1000)

    retrieval_started = time.perf_counter()
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
    retrieval_latency_ms = int((time.perf_counter() - retrieval_started) * 1000)

    synthesis_started = time.perf_counter()
    answer = build_answer(question, retrieval)
    synthesis_latency_ms = int((time.perf_counter() - synthesis_started) * 1000)
    return {
        "route": route_decision.path,
        "route_reason": route_decision.reason,
        "retrieval": retrieval,
        "answer": answer,
        "tool_decisions": (
            ToolDecision(
                tool_name="router",
                rationale=route_decision.reason,
                latency_ms=max(router_latency_ms, 0),
            ),
            ToolDecision(
                tool_name="retrieval",
                rationale=f"route={route_decision.path}",
                latency_ms=max(retrieval_latency_ms, 0),
            ),
            ToolDecision(
                tool_name="synthesis",
                rationale=f"confidence={answer.confidence}",
                latency_ms=max(synthesis_latency_ms, 0),
            ),
        ),
    }


def run_orchestration(
    *,
    store: RuntimeStore,
    question: str,
    user_id: str | None,
    user_access_token: str | None,
    embedding_provider: EmbeddingProvider,
    critic_model: CriticModel,
    max_refinements: int,
    supabase_store: SupabaseVectorStore | None,
    neo4j_store: Neo4jGraphStore | None,
    use_langgraph: bool,
) -> OrchestrationResult:
    if not use_langgraph:
        initial = _run_without_langgraph(
            store=store,
            question=question,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )
        return _maybe_refine(
            question=question,
            initial=initial,
            store=store,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            critic_model=critic_model,
            max_refinements=max_refinements,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )

    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:
        initial = _run_without_langgraph(
            store=store,
            question=question,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )
        return _maybe_refine(
            question=question,
            initial=initial,
            store=store,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            critic_model=critic_model,
            max_refinements=max_refinements,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )

    timings: dict[str, int] = {}

    def router_node(state: _GraphState) -> _GraphState:
        started = time.perf_counter()
        decision = select_route(state["question"])
        timings["router_ms"] = int((time.perf_counter() - started) * 1000)
        return {"route": decision.path, "route_reason": decision.reason}

    def single_retrieval_node(state: _GraphState) -> _GraphState:
        started = time.perf_counter()
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
        timings["retrieval_ms"] = int((time.perf_counter() - started) * 1000)
        return {"retrieval": retrieval}

    def document_branch_node(state: _GraphState) -> _GraphState:
        started = time.perf_counter()
        if state["route"] not in {"document", "hybrid"}:
            timings["document_branch_ms"] = int((time.perf_counter() - started) * 1000)
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
        timings["document_branch_ms"] = int((time.perf_counter() - started) * 1000)
        return {"doc_hits": document_bundle.hits}

    def graph_branch_node(state: _GraphState) -> _GraphState:
        started = time.perf_counter()
        if state["route"] not in {"graph", "hybrid"}:
            timings["graph_branch_ms"] = int((time.perf_counter() - started) * 1000)
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
        timings["graph_branch_ms"] = int((time.perf_counter() - started) * 1000)
        return {"graph_hits": graph_bundle.hits}

    def merge_retrieval_node(state: _GraphState) -> _GraphState:
        started = time.perf_counter()
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
        timings["merge_ms"] = int((time.perf_counter() - started) * 1000)
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
        started = time.perf_counter()
        answer = build_answer(state["question"], state["retrieval"])
        timings["synthesis_ms"] = int((time.perf_counter() - started) * 1000)
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

    initial = {
        "route": output["route"],
        "route_reason": output["route_reason"],
        "retrieval": output["retrieval"],
        "answer": output["answer"],
        "tool_decisions": (
            ToolDecision(
                tool_name="router",
                rationale=output["route_reason"],
                latency_ms=max(timings.get("router_ms", 0), 0),
            ),
            ToolDecision(
                tool_name="retrieval",
                rationale=f"route={output['route']}",
                latency_ms=max(timings.get("retrieval_ms", 0), 0),
            ),
            ToolDecision(
                tool_name="document_branch",
                rationale="parallel document retrieval branch",
                latency_ms=max(timings.get("document_branch_ms", 0), 0),
                status="ok" if timings.get("document_branch_ms", 0) > 0 else "skipped",
            ),
            ToolDecision(
                tool_name="graph_branch",
                rationale="parallel graph retrieval branch",
                latency_ms=max(timings.get("graph_branch_ms", 0), 0),
                status="ok" if timings.get("graph_branch_ms", 0) > 0 else "skipped",
            ),
            ToolDecision(
                tool_name="merge_retrieval",
                rationale="hybrid merge and dedupe",
                latency_ms=max(timings.get("merge_ms", 0), 0),
                status="ok" if timings.get("merge_ms", 0) > 0 else "skipped",
            ),
            ToolDecision(
                tool_name="synthesis",
                rationale=f"confidence={output['answer'].confidence}",
                latency_ms=max(timings.get("synthesis_ms", 0), 0),
            ),
        ),
    }

    return _maybe_refine(
        question=question,
        initial=initial,
        store=store,
        user_id=user_id,
        user_access_token=user_access_token,
        embedding_provider=embedding_provider,
        critic_model=critic_model,
        max_refinements=max_refinements,
        supabase_store=supabase_store,
        neo4j_store=neo4j_store,
    )


def _maybe_refine(
    *,
    question: str,
    initial: OrchestrationResult,
    store: RuntimeStore,
    user_id: str | None,
    user_access_token: str | None,
    embedding_provider: EmbeddingProvider,
    critic_model: CriticModel,
    max_refinements: int,
    supabase_store: SupabaseVectorStore | None,
    neo4j_store: Neo4jGraphStore | None,
) -> OrchestrationResult:
    current = initial
    decisions = list(current["tool_decisions"])
    refinement_budget = max(0, max_refinements)

    for attempt in range(1, refinement_budget + 1):
        if current["route"] not in {"document", "graph"}:
            decisions.append(
                ToolDecision(
                    tool_name="critic",
                    rationale="no refinement needed for current route",
                    status="skipped",
                    attempt=attempt,
                )
            )
            break

        top_score = (
            current["retrieval"].hits[0].score if current["retrieval"].hits else 0.0
        )
        hit_count = len(current["retrieval"].hits)
        critic_started = time.perf_counter()
        critique = critic_model.evaluate(
            question=question,
            route=current["route"],
            top_score=top_score,
            hit_count=hit_count,
        )
        critic_latency_ms = int((time.perf_counter() - critic_started) * 1000)

        if not critique.should_refine:
            decisions.append(
                ToolDecision(
                    tool_name="critic",
                    rationale=critique.reason,
                    latency_ms=max(critic_latency_ms, 0),
                    attempt=attempt,
                )
            )
            break

        refine_started = time.perf_counter()
        refined_retrieval = retrieve(
            store=store,
            route="hybrid",
            query=question,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            neo4j_store=neo4j_store,
        )
        refine_latency_ms = int((time.perf_counter() - refine_started) * 1000)
        refined_answer = build_answer(question, refined_retrieval)
        decisions.append(
            ToolDecision(
                tool_name="critic",
                rationale=critique.reason,
                latency_ms=max(critic_latency_ms, 0),
                attempt=attempt,
            )
        )
        decisions.append(
            ToolDecision(
                tool_name="retrieval_refine",
                rationale="rerouted to hybrid for stronger evidence",
                latency_ms=max(refine_latency_ms, 0),
                attempt=attempt,
            )
        )
        current = {
            "route": "hybrid",
            "route_reason": "critic requested hybrid refinement",
            "retrieval": refined_retrieval,
            "answer": refined_answer,
            "tool_decisions": tuple(decisions),
        }

    if not decisions:
        return current

    return {
        "route": current["route"],
        "route_reason": current["route_reason"],
        "retrieval": current["retrieval"],
        "answer": current["answer"],
        "tool_decisions": tuple(decisions),
    }
