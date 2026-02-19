from dataclasses import replace

from lattice.prototype.config import AppConfig, select_supabase_retrieval_key
from lattice.prototype.data_health import _compute_overall_ok


def _test_config(**overrides: object) -> AppConfig:
    base = AppConfig(
        gemini_api_key=None,
        supabase_url="https://example.supabase.co",
        supabase_key="anon-key",
        supabase_service_role_key="service-role-key",
        use_real_supabase=True,
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


def test_compute_overall_ok_returns_true_when_one_source_ok() -> None:
    result = _compute_overall_ok(
        checks=[{"status": "ok"}, {"status": "error"}],
        allow_seeded_fallback=True,
    )
    assert result is True


def test_compute_overall_ok_returns_false_without_fallback_on_error() -> None:
    result = _compute_overall_ok(
        checks=[{"status": "error"}, {"status": "skipped"}],
        allow_seeded_fallback=False,
    )
    assert result is False


def test_select_supabase_retrieval_key_prefers_anon_key() -> None:
    key, source = select_supabase_retrieval_key(_test_config())
    assert key == "anon-key"
    assert source == "SUPABASE_KEY"


def test_select_supabase_retrieval_key_uses_service_role_only_when_enabled() -> None:
    config = _test_config(
        supabase_key=None,
        allow_service_role_for_retrieval=True,
    )
    key, source = select_supabase_retrieval_key(config)
    assert key == "service-role-key"
    assert source == "SUPABASE_SERVICE_ROLE_KEY"
