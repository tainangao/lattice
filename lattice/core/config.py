from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_version: str
    environment: str
    embedding_dimensions: int
    embedding_backend: str
    gemini_embedding_model: str
    supabase_url: str | None
    supabase_anon_key: str | None
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    neo4j_database: str
    enable_langgraph: bool
    critic_backend: str
    critic_model: str
    critic_max_refinements: int
    rerank_backend: str
    rerank_model: str
    planner_max_steps: int


def load_app_config() -> AppConfig:
    enable_langgraph_raw = os.getenv("ENABLE_LANGGRAPH", "true").lower().strip()
    return AppConfig(
        app_name=os.getenv("APP_NAME", "Lattice Agentic Graph RAG"),
        app_version=os.getenv("APP_VERSION", "0.2.0"),
        environment=os.getenv("APP_ENV", "development"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
        embedding_backend=os.getenv("EMBEDDING_BACKEND", "deterministic"),
        gemini_embedding_model=os.getenv(
            "GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001"
        ),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY"),
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_username=os.getenv("NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        enable_langgraph=enable_langgraph_raw in {"1", "true", "yes", "on"},
        critic_backend=os.getenv("CRITIC_BACKEND", "deterministic"),
        critic_model=os.getenv("CRITIC_MODEL", "gemini-2.5-flash"),
        critic_max_refinements=int(os.getenv("CRITIC_MAX_REFINEMENTS", "1")),
        rerank_backend=os.getenv("RERANK_BACKEND", "heuristic"),
        rerank_model=os.getenv("RERANK_MODEL", "gemini-2.5-flash"),
        planner_max_steps=int(os.getenv("PLANNER_MAX_STEPS", "6")),
    )
