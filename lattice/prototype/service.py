from __future__ import annotations

import asyncio
import logging
from uuid import uuid4
from typing import Protocol

from lattice.prototype.config import AppConfig, select_supabase_retrieval_key
from lattice.prototype.models import (
    QueryResponse,
    RetrievalMode,
    RouteDecision,
    SourceSnippet,
)
from lattice.prototype.orchestration import (
    build_orchestration_graph,
    create_initial_state,
)
from lattice.prototype.orchestration.telemetry import (
    build_graph_invoke_config,
    emit_orchestration_telemetry,
)
from lattice.prototype.retrievers.merge import rank_and_trim_snippets
from lattice.prototype.retrievers.document_retriever import (
    SeedDocumentRetriever,
    SupabaseDocumentRetriever,
)
from lattice.prototype.retrievers.graph_retriever import (
    Neo4jGraphRagRetriever,
    Neo4jGraphRetriever,
    SeedGraphRetriever,
    build_graphrag_embedder,
)

LOGGER = logging.getLogger(__name__)


class Retriever(Protocol):
    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]: ...


class PrototypeService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._seed_document_retriever = SeedDocumentRetriever(
            config.prototype_docs_path
        )
        self._seed_graph_retriever = SeedGraphRetriever(config.prototype_graph_path)
        self._document_retriever = _build_document_retriever(config)
        self._graph_retriever = _build_graph_retriever(config)
        self._orchestration_graph = build_orchestration_graph(
            document_retriever=self._document_retriever,
            graph_retriever=self._graph_retriever,
            seed_document_retriever=self._seed_document_retriever,
            seed_graph_retriever=self._seed_graph_retriever,
            allow_seeded_fallback=config.allow_seeded_fallback,
            gemini_api_key=config.gemini_api_key,
            phase4_enable_critic=config.phase4_enable_critic,
            phase4_confidence_threshold=config.phase4_confidence_threshold,
            phase4_min_snippets=config.phase4_min_snippets,
            phase4_max_refinement_rounds=config.phase4_max_refinement_rounds,
            phase4_refinement_retrieval_limit=config.phase4_refinement_retrieval_limit,
        )

    async def run_query(self, question: str) -> QueryResponse:
        request_id = uuid4().hex
        state = create_initial_state(
            question,
            request_id=request_id,
            retrieval_limit=self._config.phase4_initial_retrieval_limit,
        )
        result_state = await self._orchestration_graph.ainvoke(
            state,
            config=build_graph_invoke_config(request_id),
        )
        emit_orchestration_telemetry(result_state)
        route = _route_from_state(result_state)
        snippets = _snippets_from_state(result_state)
        answer = _answer_from_state(result_state, route.mode)
        return QueryResponse(
            question=question, route=route, answer=answer, snippets=snippets
        )


async def _retrieve_snippets(
    mode: RetrievalMode,
    question: str,
    document_retriever: Retriever | None,
    graph_retriever: Retriever | None,
    seed_document_retriever: SeedDocumentRetriever,
    seed_graph_retriever: SeedGraphRetriever,
    allow_seeded_fallback: bool,
) -> list[SourceSnippet]:
    if mode == RetrievalMode.DOCUMENT:
        return await _run_retriever_with_fallback(
            question=question,
            primary_retriever=document_retriever,
            fallback_retriever=seed_document_retriever,
            allow_seeded_fallback=allow_seeded_fallback,
            retriever_name="document",
        )
    if mode == RetrievalMode.GRAPH:
        return await _run_retriever_with_fallback(
            question=question,
            primary_retriever=graph_retriever,
            fallback_retriever=seed_graph_retriever,
            allow_seeded_fallback=allow_seeded_fallback,
            retriever_name="graph",
        )

    document_task = _run_retriever_with_fallback(
        question=question,
        primary_retriever=document_retriever,
        fallback_retriever=seed_document_retriever,
        allow_seeded_fallback=allow_seeded_fallback,
        retriever_name="document",
    )
    graph_task = _run_retriever_with_fallback(
        question=question,
        primary_retriever=graph_retriever,
        fallback_retriever=seed_graph_retriever,
        allow_seeded_fallback=allow_seeded_fallback,
        retriever_name="graph",
    )
    document_results, graph_results = await asyncio.gather(document_task, graph_task)
    return rank_and_trim_snippets([*document_results, *graph_results])


async def _run_retriever_with_fallback(
    question: str,
    primary_retriever: Retriever | None,
    fallback_retriever: Retriever,
    allow_seeded_fallback: bool,
    retriever_name: str,
) -> list[SourceSnippet]:
    if primary_retriever is None:
        return await fallback_retriever.retrieve(question)

    try:
        return await primary_retriever.retrieve(question)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Primary retriever failed",
            extra={"retriever": retriever_name},
            exc_info=exc,
        )
        if allow_seeded_fallback:
            return await fallback_retriever.retrieve(question)
        return [_build_retriever_error_snippet(retriever_name, exc)]


def _build_retriever_error_snippet(
    retriever_name: str,
    exc: Exception,
) -> SourceSnippet:
    return SourceSnippet(
        source_type="system",
        source_id=f"retrieval_error:{retriever_name}",
        text=(
            f"Retriever '{retriever_name}' failed ({exc.__class__.__name__}). "
            "Seeded fallback is disabled."
        ),
        score=0.0,
    )


def _answer_from_state(state: dict[str, object], mode: RetrievalMode) -> str:
    answer = state.get("answer")
    if isinstance(answer, str) and answer.strip():
        return answer
    if mode == RetrievalMode.DIRECT:
        return (
            "Hello! Ask me about project timelines, dependencies, or document context."
        )
    return (
        "I could not find matching prototype context yet. "
        "Try asking about project timelines, dependencies, or ownership links."
    )


def _snippets_from_state(state: dict[str, object]) -> list[SourceSnippet]:
    snippets = state.get("snippets")
    if isinstance(snippets, list):
        resolved: list[SourceSnippet] = []
        for snippet in snippets:
            if isinstance(snippet, SourceSnippet):
                resolved.append(snippet)
            elif isinstance(snippet, dict):
                resolved.append(SourceSnippet.model_validate(snippet))
        return resolved
    return []


def _route_from_state(state: dict[str, object]) -> RouteDecision:
    mode = state.get("route_mode")
    reason = state.get("route_reason")
    if isinstance(mode, RetrievalMode):
        resolved_mode = mode
    elif isinstance(mode, str) and mode in {item.value for item in RetrievalMode}:
        resolved_mode = RetrievalMode(mode)
    else:
        resolved_mode = RetrievalMode.DIRECT
    if isinstance(reason, str) and reason.strip():
        resolved_reason = reason
    else:
        resolved_reason = "Routing fallback: defaulted to direct mode."
    return RouteDecision(mode=resolved_mode, reason=resolved_reason)


def _build_document_retriever(config: AppConfig) -> Retriever | None:
    if not config.use_real_supabase:
        return None
    supabase_key, _ = select_supabase_retrieval_key(config)
    if not config.supabase_url or not supabase_key:
        return None
    return SupabaseDocumentRetriever(
        supabase_url=config.supabase_url,
        supabase_key=supabase_key,
        table_name=config.supabase_documents_table,
    )


def _build_graph_retriever(config: AppConfig) -> Retriever | None:
    if not config.use_real_neo4j:
        return None
    if not config.neo4j_uri or not config.neo4j_username or not config.neo4j_password:
        return None
    if config.use_neo4j_graphrag_hybrid:
        return _build_graphrag_hybrid_retriever(config)
    return Neo4jGraphRetriever(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database,
        scan_limit=config.neo4j_scan_limit,
    )


def _build_graphrag_hybrid_retriever(config: AppConfig) -> Retriever:
    mode = config.neo4j_graphrag_retriever_mode.strip().lower()
    if mode not in {"hybrid", "hybrid_cypher"}:
        LOGGER.warning(
            "Unsupported GraphRAG retriever mode; falling back to cypher retriever",
            extra={"retriever_mode": mode},
        )
        return _build_default_cypher_retriever(config)

    if (
        not config.neo4j_graphrag_vector_index
        or not config.neo4j_graphrag_fulltext_index
    ):
        LOGGER.warning(
            "GraphRAG hybrid prerequisites missing; falling back to cypher retriever"
        )
        return _build_default_cypher_retriever(config)

    if mode == "hybrid_cypher" and not config.neo4j_graphrag_hybrid_cypher_query:
        LOGGER.warning(
            "HybridCypherRetriever query missing; falling back to cypher retriever"
        )
        return _build_default_cypher_retriever(config)

    embedder = build_graphrag_embedder(
        provider=config.neo4j_graphrag_embedder_provider,
        gemini_api_key=config.gemini_api_key,
        google_model=config.neo4j_graphrag_google_model,
        openai_model=config.neo4j_graphrag_openai_model,
    )
    if embedder is None:
        LOGGER.warning(
            "GraphRAG embedder unavailable; falling back to cypher retriever",
            extra={"provider": config.neo4j_graphrag_embedder_provider},
        )
        return _build_default_cypher_retriever(config)

    try:
        return Neo4jGraphRagRetriever(
            uri=config.neo4j_uri or "",
            username=config.neo4j_username or "",
            password=config.neo4j_password or "",
            database=config.neo4j_database,
            vector_index_name=config.neo4j_graphrag_vector_index,
            fulltext_index_name=config.neo4j_graphrag_fulltext_index,
            retriever_mode=mode,
            embedder=embedder,
            hybrid_cypher_query=config.neo4j_graphrag_hybrid_cypher_query,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "GraphRAG retriever initialization failed; falling back to cypher retriever",
            exc_info=exc,
            extra={"retriever_mode": mode},
        )
        return _build_default_cypher_retriever(config)


def _build_default_cypher_retriever(config: AppConfig) -> Retriever:
    return Neo4jGraphRetriever(
        uri=config.neo4j_uri or "",
        username=config.neo4j_username or "",
        password=config.neo4j_password or "",
        database=config.neo4j_database,
        scan_limit=config.neo4j_scan_limit,
    )
