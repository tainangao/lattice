import pytest

from lattice.prototype.config import AppConfig
from lattice.prototype.models import RetrievalMode, SourceSnippet
from lattice.prototype.service import PrototypeService, _run_retriever_with_fallback


def _test_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=None,
        supabase_url=None,
        supabase_key=None,
        supabase_service_role_key=None,
        use_real_supabase=False,
        use_real_neo4j=False,
        allow_seeded_fallback=True,
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
    )

    assert result == []
