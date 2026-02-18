from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    gemini_api_key: str | None
    supabase_url: str | None
    supabase_key: str | None
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    prototype_docs_path: str
    prototype_graph_path: str


def _read_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if not value:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def load_config() -> AppConfig:
    return AppConfig(
        gemini_api_key=_read_optional_env("GEMINI_API_KEY")
        or _read_optional_env("GOOGLE_API_KEY"),
        supabase_url=_read_optional_env("SUPABASE_URL"),
        supabase_key=_read_optional_env("SUPABASE_KEY"),
        neo4j_uri=_read_optional_env("NEO4J_URI"),
        neo4j_username=_read_optional_env("NEO4J_USERNAME"),
        neo4j_password=_read_optional_env("NEO4J_PASSWORD"),
        prototype_docs_path=os.getenv(
            "PROTOTYPE_DOCS_PATH", "data/prototype/private_documents.json"
        ),
        prototype_graph_path=os.getenv(
            "PROTOTYPE_GRAPH_PATH", "data/prototype/graph_edges.json"
        ),
    )
