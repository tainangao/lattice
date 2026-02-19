from dataclasses import replace

from lattice.prototype.config import AppConfig
from lattice.prototype.readiness import build_readiness_report


def _base_config() -> AppConfig:
    return AppConfig(
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


def test_readiness_passes_in_seeded_mode() -> None:
    config = _base_config()

    report = build_readiness_report(config)

    assert report["ready"] is True
    assert report["connectors"]["supabase"]["mode"] == "seeded_only"
    assert report["connectors"]["neo4j"]["mode"] == "seeded_only"


def test_readiness_reports_misconfigured_real_mode_without_fallback() -> None:
    config = replace(
        _base_config(),
        use_real_supabase=True,
        use_real_neo4j=True,
        allow_seeded_fallback=False,
    )

    report = build_readiness_report(config)

    assert report["ready"] is False
    assert report["connectors"]["supabase"]["mode"] == "misconfigured"
    assert report["connectors"]["neo4j"]["mode"] == "misconfigured"


def test_readiness_reports_real_mode_when_all_required_config_present() -> None:
    config = replace(
        _base_config(),
        use_real_supabase=True,
        supabase_url="https://example.supabase.co",
        supabase_key="key",
        use_real_neo4j=True,
        neo4j_uri="neo4j+s://example.databases.neo4j.io",
        neo4j_username="neo4j",
        neo4j_password="password",
    )

    report = build_readiness_report(config)

    assert report["ready"] is True
    assert report["connectors"]["supabase"]["mode"] == "real"
    assert report["connectors"]["neo4j"]["mode"] == "real"
