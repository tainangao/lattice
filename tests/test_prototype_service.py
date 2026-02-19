import pytest

from lattice.prototype.config import AppConfig
from lattice.prototype.models import RetrievalMode, SourceSnippet
from lattice.prototype.service import (
    PrototypeService,
    _rank_and_trim_snippets,
    _run_retriever_with_fallback,
)


def _test_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=None,
        supabase_url=None,
        supabase_key=None,
        supabase_service_role_key=None,
        use_real_supabase=False,
        use_real_neo4j=False,
        allow_seeded_fallback=True,
        allow_service_role_for_retrieval=False,
        neo4j_uri=None,
        neo4j_username=None,
        neo4j_password=None,
        neo4j_database="neo4j",
        supabase_documents_table="embeddings",
        neo4j_scan_limit=200,
        prototype_docs_path="data/prototype/private_documents.json",
        prototype_graph_path="data/prototype/graph_edges.json",
    )


@pytest.mark.asyncio
async def test_run_query_returns_sources_for_hybrid_query() -> None:
    service = PrototypeService(_test_config())

    response = await service.run_query(
        "How does the timeline compare to graph dependencies?"
    )

    assert response.route.mode == RetrievalMode.BOTH
    assert response.snippets
    assert "Sources:" in response.answer


@pytest.mark.asyncio
async def test_run_query_direct_path_uses_direct_response_contract() -> None:
    service = PrototypeService(_test_config())

    response = await service.run_query("hello")

    assert response.route.mode == RetrievalMode.DIRECT
    assert response.snippets == []
    assert "Hello!" in response.answer


class _FakeRetriever:
    def __init__(
        self, snippets: list[SourceSnippet], should_raise: bool = False
    ) -> None:
        self._snippets = snippets
        self._should_raise = should_raise

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        _ = question
        _ = limit
        if self._should_raise:
            raise RuntimeError("retriever failed")
        return self._snippets


@pytest.mark.asyncio
async def test_run_retriever_with_fallback_returns_fallback_when_primary_fails() -> (
    None
):
    fallback = _FakeRetriever(
        [
            SourceSnippet(
                source_type="document",
                source_id="fallback#1",
                text="fallback snippet",
                score=1.0,
            )
        ]
    )
    primary = _FakeRetriever([], should_raise=True)

    result = await _run_retriever_with_fallback(
        question="test",
        primary_retriever=primary,
        fallback_retriever=fallback,
        allow_seeded_fallback=True,
        retriever_name="document",
    )

    assert result
    assert result[0].source_id == "fallback#1"


@pytest.mark.asyncio
async def test_run_retriever_with_fallback_returns_empty_when_fallback_disabled() -> (
    None
):
    fallback = _FakeRetriever(
        [
            SourceSnippet(
                source_type="document",
                source_id="fallback#1",
                text="fallback snippet",
                score=1.0,
            )
        ]
    )
    primary = _FakeRetriever([], should_raise=True)

    result = await _run_retriever_with_fallback(
        question="test",
        primary_retriever=primary,
        fallback_retriever=fallback,
        allow_seeded_fallback=False,
        retriever_name="document",
    )

    assert len(result) == 1
    assert result[0].source_type == "system"
    assert result[0].source_id == "retrieval_error:document"


def test_rank_and_trim_snippets_drops_low_relevance_entries() -> None:
    snippets = [
        SourceSnippet(
            source_type="document",
            source_id="doc#1",
            text="high score document",
            score=0.9,
        ),
        SourceSnippet(
            source_type="graph",
            source_id="graph#1",
            text="mid score graph",
            score=0.5,
        ),
        SourceSnippet(
            source_type="document",
            source_id="doc#2",
            text="low score document",
            score=0.1,
        ),
    ]

    ranked = _rank_and_trim_snippets(snippets)

    assert [item.source_id for item in ranked] == ["doc#1", "graph#1"]


def test_rank_and_trim_snippets_keeps_best_when_all_low_scores() -> None:
    snippets = [
        SourceSnippet(
            source_type="document",
            source_id="doc#1",
            text="low score document",
            score=0.05,
        ),
        SourceSnippet(
            source_type="graph",
            source_id="graph#1",
            text="lower score graph",
            score=0.01,
        ),
    ]

    ranked = _rank_and_trim_snippets(snippets)

    assert len(ranked) == 1
    assert ranked[0].source_id == "doc#1"
