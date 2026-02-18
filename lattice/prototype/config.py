from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    gemini_api_key: str | None
    supabase_url: str | None
    supabase_key: str | None
    supabase_service_role_key: str | None
    use_real_supabase: bool
    use_real_neo4j: bool
    allow_seeded_fallback: bool
    allow_service_role_for_retrieval: bool
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    neo4j_database: str
    supabase_documents_table: str
    neo4j_scan_limit: int
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


def load_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=_read_optional_env("GEMINI_API_KEY")
        or _read_optional_env("GOOGLE_API_KEY"),
        supabase_url=_read_optional_env("SUPABASE_URL"),
        supabase_key=_read_optional_env("SUPABASE_KEY"),
        supabase_service_role_key=_read_optional_env("SUPABASE_SERVICE_ROLE_KEY"),
        use_real_supabase=_read_bool_env("USE_REAL_SUPABASE", default=False),
        use_real_neo4j=_read_bool_env("USE_REAL_NEO4J", default=False),
        allow_seeded_fallback=_read_bool_env("ALLOW_SEEDED_FALLBACK", default=True),
        allow_service_role_for_retrieval=_read_bool_env(
            "ALLOW_SERVICE_ROLE_FOR_RETRIEVAL", default=False
        ),
        neo4j_uri=_read_optional_env("NEO4J_URI"),
        neo4j_username=_read_optional_env("NEO4J_USERNAME"),
        neo4j_password=_read_optional_env("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        supabase_documents_table=os.getenv("SUPABASE_DOCUMENTS_TABLE", "embeddings"),
        neo4j_scan_limit=_read_int_env("NEO4J_SCAN_LIMIT", default=200),
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
