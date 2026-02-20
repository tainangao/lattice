from __future__ import annotations

import os
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AppConfig:
    gemini_api_key: str | None
    supabase_url: str | None
    supabase_key: str | None
    supabase_service_role_key: str | None
    use_real_supabase: bool
    use_real_neo4j: bool
    use_neo4j_graphrag_hybrid: bool
    allow_seeded_fallback: bool
    allow_service_role_for_retrieval: bool
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    neo4j_database: str
    neo4j_graphrag_vector_index: str | None
    neo4j_graphrag_fulltext_index: str | None
    neo4j_graphrag_retriever_mode: str
    neo4j_graphrag_embedder_provider: str
    neo4j_graphrag_google_model: str
    neo4j_graphrag_openai_model: str
    neo4j_graphrag_hybrid_cypher_query: str | None
    supabase_documents_table: str
    neo4j_scan_limit: int
    phase4_enable_critic: bool
    phase4_confidence_threshold: float
    phase4_min_snippets: int
    phase4_max_refinement_rounds: int
    phase4_initial_retrieval_limit: int
    phase4_refinement_retrieval_limit: int
    prototype_docs_path: str
    prototype_graph_path: str


def _read_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if not value:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _read_bool_env(name: str, default: bool) -> bool:
    value = _read_optional_env(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _read_int_env(name: str, default: int) -> int:
    value = _read_optional_env(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _read_float_env(name: str, default: float) -> float:
    value = _read_optional_env(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    if parsed < 0:
        return default
    if parsed > 1:
        return 1.0
    return parsed


def load_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=_read_optional_env("GEMINI_API_KEY")
        or _read_optional_env("GOOGLE_API_KEY"),
        supabase_url=_read_optional_env("SUPABASE_URL"),
        supabase_key=_read_optional_env("SUPABASE_KEY"),
        supabase_service_role_key=_read_optional_env("SUPABASE_SERVICE_ROLE_KEY"),
        use_real_supabase=_read_bool_env("USE_REAL_SUPABASE", default=False),
        use_real_neo4j=_read_bool_env("USE_REAL_NEO4J", default=False),
        use_neo4j_graphrag_hybrid=_read_bool_env(
            "USE_NEO4J_GRAPHRAG_HYBRID", default=False
        ),
        allow_seeded_fallback=_read_bool_env("ALLOW_SEEDED_FALLBACK", default=True),
        allow_service_role_for_retrieval=_read_bool_env(
            "ALLOW_SERVICE_ROLE_FOR_RETRIEVAL", default=False
        ),
        neo4j_uri=_read_optional_env("NEO4J_URI"),
        neo4j_username=_read_optional_env("NEO4J_USERNAME"),
        neo4j_password=_read_optional_env("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        neo4j_graphrag_vector_index=_read_optional_env("NEO4J_GRAPHRAG_VECTOR_INDEX"),
        neo4j_graphrag_fulltext_index=_read_optional_env(
            "NEO4J_GRAPHRAG_FULLTEXT_INDEX"
        ),
        neo4j_graphrag_retriever_mode=os.getenv(
            "NEO4J_GRAPHRAG_RETRIEVER_MODE", "hybrid"
        ).strip()
        or "hybrid",
        neo4j_graphrag_embedder_provider=os.getenv(
            "NEO4J_GRAPHRAG_EMBEDDER_PROVIDER", "google"
        ).strip()
        or "google",
        neo4j_graphrag_google_model=os.getenv(
            "NEO4J_GRAPHRAG_GOOGLE_MODEL", "text-embedding-004"
        ).strip()
        or "text-embedding-004",
        neo4j_graphrag_openai_model=os.getenv(
            "NEO4J_GRAPHRAG_OPENAI_MODEL", "text-embedding-3-small"
        ).strip()
        or "text-embedding-3-small",
        neo4j_graphrag_hybrid_cypher_query=_read_optional_env(
            "NEO4J_GRAPHRAG_HYBRID_CYPHER_QUERY"
        ),
        supabase_documents_table=os.getenv("SUPABASE_DOCUMENTS_TABLE", "embeddings"),
        neo4j_scan_limit=_read_int_env("NEO4J_SCAN_LIMIT", default=200),
        phase4_enable_critic=_read_bool_env("PHASE4_ENABLE_CRITIC", default=True),
        phase4_confidence_threshold=_read_float_env(
            "PHASE4_CONFIDENCE_THRESHOLD", default=0.62
        ),
        phase4_min_snippets=_read_int_env("PHASE4_MIN_SNIPPETS", default=2),
        phase4_max_refinement_rounds=_read_int_env(
            "PHASE4_MAX_REFINEMENT_ROUNDS", default=1
        ),
        phase4_initial_retrieval_limit=_read_int_env(
            "PHASE4_INITIAL_RETRIEVAL_LIMIT", default=3
        ),
        phase4_refinement_retrieval_limit=_read_int_env(
            "PHASE4_REFINEMENT_RETRIEVAL_LIMIT", default=5
        ),
        prototype_docs_path=os.getenv(
            "PROTOTYPE_DOCS_PATH", "data/prototype/private_documents.json"
        ),
        prototype_graph_path=os.getenv(
            "PROTOTYPE_GRAPH_PATH", "data/prototype/graph_edges.json"
        ),
    )


def select_supabase_retrieval_key(config: AppConfig) -> tuple[str | None, str | None]:
    if config.supabase_key:
        return config.supabase_key, "SUPABASE_KEY"
    if config.allow_service_role_for_retrieval and config.supabase_service_role_key:
        return config.supabase_service_role_key, "SUPABASE_SERVICE_ROLE_KEY"
    return None, None


def select_supabase_user_retrieval_key(
    config: AppConfig,
) -> tuple[str | None, str | None]:
    if config.supabase_key:
        return config.supabase_key, "SUPABASE_KEY"
    return None, None


def with_runtime_gemini_key(
    config: AppConfig,
    runtime_gemini_api_key: str | None,
) -> AppConfig:
    if runtime_gemini_api_key is None:
        return config
    key = runtime_gemini_api_key.strip()
    if not key:
        return config
    return replace(config, gemini_api_key=key)


def normalize_runtime_user_id(runtime_user_id: object) -> str | None:
    if not isinstance(runtime_user_id, str):
        return None
    normalized = runtime_user_id.strip()
    return normalized if normalized else None


def extract_bearer_token(authorization_header: str | None) -> str | None:
    if not isinstance(authorization_header, str):
        return None
    prefix = "Bearer "
    if not authorization_header.startswith(prefix):
        return None
    token = authorization_header[len(prefix) :].strip()
    return token if token else None
