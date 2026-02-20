from dataclasses import replace

import pytest

from lattice.prototype.config import AppConfig
from lattice.prototype.models import RetrievalMode, SourceSnippet
from lattice.prototype.retrievers.document_retriever import SupabaseDocumentRetriever
from lattice.prototype.retrievers.merge import rank_and_trim_snippets
from lattice.prototype.service import (
    PrototypeService,
    _build_graph_retriever,
    _run_retriever_with_fallback,
)


def _test_config(**overrides: object) -> AppConfig:
    base = AppConfig(
        gemini_api_key=None,
        supabase_url=None,
        supabase_key=None,
        supabase_service_role_key=None,
        use_real_supabase=False,
        use_real_neo4j=False,
        use_neo4j_graphrag_hybrid=False,
        allow_seeded_fallback=True,
        allow_service_role_for_retrieval=False,
        neo4j_uri=None,
        neo4j_username=None,
        neo4j_password=None,
        neo4j_database="neo4j",
        neo4j_graphrag_vector_index=None,
        neo4j_graphrag_fulltext_index=None,
        neo4j_graphrag_retriever_mode="hybrid",
        neo4j_graphrag_embedder_provider="google",
        neo4j_graphrag_google_model="text-embedding-004",
        neo4j_graphrag_openai_model="text-embedding-3-small",
        neo4j_graphrag_hybrid_cypher_query=None,
        supabase_documents_table="embeddings",
        neo4j_scan_limit=200,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_initial_retrieval_limit=3,
        phase4_refinement_retrieval_limit=5,
        prototype_docs_path="data/prototype/private_documents.json",
        prototype_graph_path="data/prototype/graph_edges.json",
    )
    return replace(base, **overrides)


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

    ranked = rank_and_trim_snippets(snippets)

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

    ranked = rank_and_trim_snippets(snippets)

    assert len(ranked) == 1
    assert ranked[0].source_id == "doc#1"


class _SentinelRetriever:
    def __init__(self, label: str) -> None:
        self.label = label

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        _ = question
        _ = limit
        return []


def test_build_graph_retriever_uses_google_provider_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, str] = {}

    def _fake_embedder_builder(
        provider: str,
        gemini_api_key: str | None,
        google_model: str,
        openai_model: str,
    ) -> object:
        calls["provider"] = provider
        calls["gemini_api_key"] = gemini_api_key or ""
        calls["google_model"] = google_model
        calls["openai_model"] = openai_model
        return object()

    def _fake_graphrag_retriever(**kwargs: object) -> _SentinelRetriever:
        calls["mode"] = str(kwargs.get("retriever_mode"))
        return _SentinelRetriever("graphrag")

    monkeypatch.setattr(
        "lattice.prototype.service.build_graphrag_embedder",
        _fake_embedder_builder,
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRagRetriever",
        _fake_graphrag_retriever,
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRetriever",
        lambda **kwargs: _SentinelRetriever("cypher"),
    )

    retriever = _build_graph_retriever(
        _test_config(
            gemini_api_key="gemini-key",
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=True,
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_graphrag_vector_index="vector-index",
            neo4j_graphrag_fulltext_index="fulltext-index",
        )
    )

    assert isinstance(retriever, _SentinelRetriever)
    assert retriever.label == "graphrag"
    assert calls["provider"] == "google"
    assert calls["gemini_api_key"] == "gemini-key"
    assert calls["mode"] == "hybrid"


def test_build_graph_retriever_falls_back_when_embedder_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lattice.prototype.service.build_graphrag_embedder",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRagRetriever",
        lambda **kwargs: _SentinelRetriever("graphrag"),
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRetriever",
        lambda **kwargs: _SentinelRetriever("cypher"),
    )

    retriever = _build_graph_retriever(
        _test_config(
            gemini_api_key="gemini-key",
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=True,
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_graphrag_vector_index="vector-index",
            neo4j_graphrag_fulltext_index="fulltext-index",
        )
    )

    assert isinstance(retriever, _SentinelRetriever)
    assert retriever.label == "cypher"


def test_build_graph_retriever_hybrid_cypher_requires_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lattice.prototype.service.build_graphrag_embedder",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRagRetriever",
        lambda **kwargs: _SentinelRetriever("graphrag"),
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRetriever",
        lambda **kwargs: _SentinelRetriever("cypher"),
    )

    retriever = _build_graph_retriever(
        _test_config(
            gemini_api_key="gemini-key",
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=True,
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_graphrag_vector_index="vector-index",
            neo4j_graphrag_fulltext_index="fulltext-index",
            neo4j_graphrag_retriever_mode="hybrid_cypher",
            neo4j_graphrag_hybrid_cypher_query=None,
        )
    )

    assert isinstance(retriever, _SentinelRetriever)
    assert retriever.label == "cypher"


def test_build_graph_retriever_uses_hybrid_cypher_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, str] = {}

    def _fake_graphrag_retriever(**kwargs: object) -> _SentinelRetriever:
        calls["mode"] = str(kwargs.get("retriever_mode"))
        calls["query"] = str(kwargs.get("hybrid_cypher_query"))
        return _SentinelRetriever("graphrag")

    monkeypatch.setattr(
        "lattice.prototype.service.build_graphrag_embedder",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRagRetriever",
        _fake_graphrag_retriever,
    )
    monkeypatch.setattr(
        "lattice.prototype.service.Neo4jGraphRetriever",
        lambda **kwargs: _SentinelRetriever("cypher"),
    )

    retriever = _build_graph_retriever(
        _test_config(
            gemini_api_key="gemini-key",
            use_real_neo4j=True,
            use_neo4j_graphrag_hybrid=True,
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="password",
            neo4j_graphrag_vector_index="vector-index",
            neo4j_graphrag_fulltext_index="fulltext-index",
            neo4j_graphrag_retriever_mode="hybrid_cypher",
            neo4j_graphrag_hybrid_cypher_query="RETURN node",
        )
    )

    assert isinstance(retriever, _SentinelRetriever)
    assert retriever.label == "graphrag"
    assert calls["mode"] == "hybrid_cypher"
    assert calls["query"] == "RETURN node"


@pytest.mark.asyncio
async def test_private_ingestion_requires_authenticated_user() -> None:
    service = PrototypeService(_test_config())

    with pytest.raises(ValueError):
        await service.ingest_private_document(
            source="notes.txt",
            content="private content",
            runtime_user_id=None,
        )


@pytest.mark.asyncio
async def test_private_ingestion_uses_user_scoped_retriever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, str] = {}

    class _FakeSupabaseRetriever(SupabaseDocumentRetriever):
        def __init__(self) -> None:
            return None

        async def upsert_private_document(
            self,
            user_id: str,
            source: str,
            content: str,
            chunk_size: int = 800,
            overlap: int = 120,
        ) -> int:
            calls["user_id"] = user_id
            calls["source"] = source
            calls["content"] = content
            return 3

    monkeypatch.setattr(
        "lattice.prototype.service._build_document_retriever",
        lambda config: _FakeSupabaseRetriever(),
    )

    service = PrototypeService(
        _test_config(
            use_real_supabase=True,
            supabase_url="https://example.supabase.co",
            supabase_key="anon-key",
        )
    )

    result = await service.ingest_private_document(
        source="notes.txt",
        content="private content",
        runtime_user_id="user-123",
    )

    assert result == 3
    assert calls["user_id"] == "user-123"
    assert calls["source"] == "notes.txt"


def test_query_candidate_rows_applies_runtime_user_filter() -> None:
    class _FakeQuery:
        def __init__(self) -> None:
            self.eq_calls: list[tuple[str, str]] = []

        def select(self, _: str) -> "_FakeQuery":
            return self

        def eq(self, field: str, value: str) -> "_FakeQuery":
            self.eq_calls.append((field, value))
            return self

        def or_(self, _: str) -> "_FakeQuery":
            return self

        def limit(self, _: int) -> "_FakeQuery":
            return self

        def execute(self) -> object:
            return object()

    class _FakeClient:
        def __init__(self, query: _FakeQuery) -> None:
            self._query = query

        def table(self, _: str) -> _FakeQuery:
            return self._query

    fake_query = _FakeQuery()
    retriever = object.__new__(SupabaseDocumentRetriever)
    retriever._table_name = "embeddings"
    retriever._client = _FakeClient(fake_query)

    _ = retriever._query_candidate_rows(
        question="Show my private project timeline",
        fetch_limit=10,
        runtime_user_id="user-abc",
    )

    assert fake_query.eq_calls == [("user_id", "user-abc")]
