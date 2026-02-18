from __future__ import annotations

import asyncio

from lattice.prototype.config import AppConfig
from lattice.prototype.models import QueryResponse, RetrievalMode
from lattice.prototype.retrievers.document_retriever import SeedDocumentRetriever
from lattice.prototype.retrievers.graph_retriever import SeedGraphRetriever
from lattice.prototype.router_agent import route_question
from lattice.prototype.synthesizer import synthesize_answer


class PrototypeService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._document_retriever = SeedDocumentRetriever(config.prototype_docs_path)
        self._graph_retriever = SeedGraphRetriever(config.prototype_graph_path)

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
    document_retriever: SeedDocumentRetriever,
    graph_retriever: SeedGraphRetriever,
) -> list:
    if mode == RetrievalMode.DOCUMENT:
        return await document_retriever.retrieve(question)
    if mode == RetrievalMode.GRAPH:
        return await graph_retriever.retrieve(question)

    document_task = document_retriever.retrieve(question)
    graph_task = graph_retriever.retrieve(question)
    document_results, graph_results = await asyncio.gather(document_task, graph_task)
    return [*document_results, *graph_results]
