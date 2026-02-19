from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from lattice.prototype.config import AppConfig, select_supabase_retrieval_key
from lattice.prototype.models import QueryResponse, RetrievalMode, SourceSnippet
from lattice.prototype.retrievers.document_retriever import (
    SeedDocumentRetriever,
    SupabaseDocumentRetriever,
)
from lattice.prototype.retrievers.graph_retriever import (
    Neo4jGraphRetriever,
    SeedGraphRetriever,
)
from lattice.prototype.router_agent import route_question
from lattice.prototype.synthesizer import synthesize_answer

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

    async def run_query(self, question: str) -> QueryResponse:
        route = route_question(question)
        if route.mode == RetrievalMode.DIRECT:
            return QueryResponse(
                question=question,
                route=route,
                answer="Hello! Ask me about project timelines, dependencies, or document context.",
                snippets=[],
            )

        snippets = await _retrieve_snippets(
            mode=route.mode,
            question=question,
            document_retriever=self._document_retriever,
            graph_retriever=self._graph_retriever,
            seed_document_retriever=self._seed_document_retriever,
            seed_graph_retriever=self._seed_graph_retriever,
            allow_seeded_fallback=self._config.allow_seeded_fallback,
        )
        answer = await synthesize_answer(
            question, snippets, self._config.gemini_api_key
        )
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
    return _rank_and_trim_snippets([*document_results, *graph_results])


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


def _rank_and_trim_snippets(
    snippets: list[SourceSnippet],
    max_results: int = 5,
) -> list[SourceSnippet]:
    if not snippets:
        return []

    retrieval_snippets = [
        snippet for snippet in snippets if snippet.source_type != "system"
    ]
    if not retrieval_snippets:
        return snippets[:max_results]

    top_score = max(snippet.score for snippet in retrieval_snippets)
    min_score = max(0.12, top_score * 0.4)
    filtered = [snippet for snippet in retrieval_snippets if snippet.score >= min_score]
    ranked = filtered if filtered else retrieval_snippets[:1]
    ranked = sorted(ranked, key=lambda snippet: snippet.score, reverse=True)
    return _dedupe_snippets(ranked)[:max_results]


def _dedupe_snippets(snippets: list[SourceSnippet]) -> list[SourceSnippet]:
    seen: set[str] = set()
    unique_snippets: list[SourceSnippet] = []
    for snippet in snippets:
        dedupe_key = f"{snippet.source_type}:{snippet.source_id}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique_snippets.append(snippet)
    return unique_snippets


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
    return Neo4jGraphRetriever(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database,
        scan_limit=config.neo4j_scan_limit,
    )
