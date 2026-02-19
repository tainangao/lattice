from dataclasses import replace

from lattice.prototype.config import AppConfig, with_runtime_gemini_key


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


def test_with_runtime_gemini_key_applies_non_empty_runtime_key() -> None:
    config = _base_config()

    resolved = with_runtime_gemini_key(config, "runtime-key")

    assert resolved.gemini_api_key == "runtime-key"


def test_with_runtime_gemini_key_ignores_blank_runtime_key() -> None:
    config = replace(_base_config(), gemini_api_key="existing")

    resolved = with_runtime_gemini_key(config, "   ")

    assert resolved.gemini_api_key == "existing"
