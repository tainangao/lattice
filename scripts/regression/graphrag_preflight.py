from __future__ import annotations

import argparse
import importlib
import json
import os
from dataclasses import asdict, dataclass

from neo4j import GraphDatabase

from scripts.regression._env import load_dotenv_file

from lattice.prototype.config import AppConfig, load_config
from lattice.prototype.retrievers.graph_retriever import (
    Neo4jGraphRagRetriever,
    Neo4jGraphRetriever,
    build_graphrag_embedder,
)
from lattice.prototype.service import _build_graph_retriever


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def _validate_config(config: AppConfig) -> list[CheckResult]:
    results = [
        CheckResult(
            name="use_real_neo4j",
            status="ok" if config.use_real_neo4j else "warning",
            detail=(
                "USE_REAL_NEO4J is enabled"
                if config.use_real_neo4j
                else "USE_REAL_NEO4J is disabled"
            ),
        ),
        CheckResult(
            name="use_neo4j_graphrag_hybrid",
            status="ok" if config.use_neo4j_graphrag_hybrid else "warning",
            detail=(
                "USE_NEO4J_GRAPHRAG_HYBRID is enabled"
                if config.use_neo4j_graphrag_hybrid
                else "USE_NEO4J_GRAPHRAG_HYBRID is disabled"
            ),
        ),
    ]

    neo4j_ready = bool(
        config.neo4j_uri and config.neo4j_username and config.neo4j_password
    )
    results.append(
        CheckResult(
            name="neo4j_connection_env",
            status="ok" if neo4j_ready else "error",
            detail=(
                "NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD are set"
                if neo4j_ready
                else "Missing one or more: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD"
            ),
        )
    )

    mode = config.neo4j_graphrag_retriever_mode.strip().lower()
    mode_ok = mode in {"hybrid", "hybrid_cypher"}
    results.append(
        CheckResult(
            name="retriever_mode",
            status="ok" if mode_ok else "error",
            detail=(
                f"NEO4J_GRAPHRAG_RETRIEVER_MODE={mode}"
                if mode_ok
                else f"Unsupported NEO4J_GRAPHRAG_RETRIEVER_MODE={mode}"
            ),
        )
    )

    has_vector = bool(config.neo4j_graphrag_vector_index)
    has_fulltext = bool(config.neo4j_graphrag_fulltext_index)
    results.append(
        CheckResult(
            name="hybrid_index_config",
            status="ok" if has_vector and has_fulltext else "error",
            detail=(
                "NEO4J_GRAPHRAG_VECTOR_INDEX and NEO4J_GRAPHRAG_FULLTEXT_INDEX are set"
                if has_vector and has_fulltext
                else "Missing NEO4J_GRAPHRAG_VECTOR_INDEX or NEO4J_GRAPHRAG_FULLTEXT_INDEX"
            ),
        )
    )

    if mode == "hybrid_cypher":
        has_query = bool(config.neo4j_graphrag_hybrid_cypher_query)
        results.append(
            CheckResult(
                name="hybrid_cypher_query",
                status="ok" if has_query else "error",
                detail=(
                    "NEO4J_GRAPHRAG_HYBRID_CYPHER_QUERY is set"
                    if has_query
                    else "Missing NEO4J_GRAPHRAG_HYBRID_CYPHER_QUERY for hybrid_cypher"
                ),
            )
        )

    provider = config.neo4j_graphrag_embedder_provider.strip().lower()
    if provider == "google":
        has_google_key = bool(config.gemini_api_key or os.getenv("GOOGLE_API_KEY"))
        results.append(
            CheckResult(
                name="google_api_key",
                status="ok" if has_google_key else "error",
                detail=(
                    "Gemini/Google API key is available"
                    if has_google_key
                    else "Missing GEMINI_API_KEY (or GOOGLE_API_KEY) for provider=google"
                ),
            )
        )
    elif provider == "openai":
        has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
        results.append(
            CheckResult(
                name="openai_api_key",
                status="ok" if has_openai_key else "error",
                detail=(
                    "OPENAI_API_KEY is available"
                    if has_openai_key
                    else "Missing OPENAI_API_KEY for provider=openai"
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="embedder_provider",
                status="error",
                detail=(
                    f"Unsupported NEO4J_GRAPHRAG_EMBEDDER_PROVIDER={provider}; use google or openai"
                ),
            )
        )

    return results


def _validate_dependencies(config: AppConfig) -> list[CheckResult]:
    results: list[CheckResult] = []

    for module_name in ["neo4j_graphrag.embeddings", "neo4j_graphrag.retrievers"]:
        try:
            importlib.import_module(module_name)
            results.append(
                CheckResult(
                    name=f"module:{module_name}",
                    status="ok",
                    detail=f"Imported {module_name}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                CheckResult(
                    name=f"module:{module_name}",
                    status="error",
                    detail=f"Failed to import {module_name}: {exc.__class__.__name__}",
                )
            )

    embedder = build_graphrag_embedder(
        provider=config.neo4j_graphrag_embedder_provider,
        gemini_api_key=config.gemini_api_key,
        google_model=config.neo4j_graphrag_google_model,
        openai_model=config.neo4j_graphrag_openai_model,
    )
    results.append(
        CheckResult(
            name="embedder_build",
            status="ok" if embedder is not None else "error",
            detail=(
                f"Constructed embedder {embedder.__class__.__name__}"
                if embedder is not None
                else "Could not construct GraphRAG embedder from current config"
            ),
        )
    )
    return results


def _validate_index_presence(config: AppConfig) -> list[CheckResult]:
    if not (config.neo4j_uri and config.neo4j_username and config.neo4j_password):
        return [
            CheckResult(
                name="neo4j_index_lookup",
                status="warning",
                detail="Skipped index lookup because Neo4j credentials are incomplete",
            )
        ]

    try:
        with GraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_username, config.neo4j_password),
        ) as driver:
            with driver.session(database=config.neo4j_database) as session:
                records = list(
                    session.run(
                        "SHOW INDEXES "
                        "YIELD name, type, state "
                        "WHERE name IN [$vector_name, $fulltext_name] "
                        "RETURN name, type, state",
                        vector_name=config.neo4j_graphrag_vector_index,
                        fulltext_name=config.neo4j_graphrag_fulltext_index,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        return [
            CheckResult(
                name="neo4j_index_lookup",
                status="error",
                detail=f"Failed to query Neo4j indexes: {exc.__class__.__name__}",
            )
        ]

    index_map = {
        record.get("name"): {
            "type": record.get("type"),
            "state": record.get("state"),
        }
        for record in records
    }
    vector_name = config.neo4j_graphrag_vector_index
    fulltext_name = config.neo4j_graphrag_fulltext_index

    results: list[CheckResult] = []
    if vector_name:
        vector = index_map.get(vector_name)
        results.append(
            CheckResult(
                name="vector_index",
                status="ok"
                if vector
                and vector.get("type") == "VECTOR"
                and vector.get("state") == "ONLINE"
                else "error",
                detail=(
                    f"Vector index {vector_name} is ONLINE"
                    if vector
                    and vector.get("type") == "VECTOR"
                    and vector.get("state") == "ONLINE"
                    else f"Vector index {vector_name} missing or not ONLINE"
                ),
            )
        )
    if fulltext_name:
        fulltext = index_map.get(fulltext_name)
        results.append(
            CheckResult(
                name="fulltext_index",
                status="ok"
                if fulltext
                and fulltext.get("type") == "FULLTEXT"
                and fulltext.get("state") == "ONLINE"
                else "error",
                detail=(
                    f"Fulltext index {fulltext_name} is ONLINE"
                    if fulltext
                    and fulltext.get("type") == "FULLTEXT"
                    and fulltext.get("state") == "ONLINE"
                    else f"Fulltext index {fulltext_name} missing or not ONLINE"
                ),
            )
        )
    return results


def _resolve_active_backend(config: AppConfig) -> str:
    retriever = _build_graph_retriever(config)
    if isinstance(retriever, Neo4jGraphRagRetriever):
        mode = config.neo4j_graphrag_retriever_mode.strip().lower()
        return (
            "graphrag_hybrid_cypher" if mode == "hybrid_cypher" else "graphrag_hybrid"
        )
    if isinstance(retriever, Neo4jGraphRetriever):
        if config.use_neo4j_graphrag_hybrid:
            return "cypher_fallback_from_graphrag"
        return "cypher"
    if retriever is None:
        return "none"
    return f"unknown:{retriever.__class__.__name__}"


def _build_report(config: AppConfig) -> dict[str, object]:
    checks = [
        *_validate_config(config),
        *_validate_dependencies(config),
        *_validate_index_presence(config),
    ]
    has_errors = any(item.status == "error" for item in checks)
    return {
        "active_graph_backend": _resolve_active_backend(config),
        "ready_for_graphrag": not has_errors,
        "checks": [asdict(item) for item in checks],
    }


def _print_human_report(report: dict[str, object]) -> None:
    print(f"active_graph_backend: {report['active_graph_backend']}")
    print(f"ready_for_graphrag: {report['ready_for_graphrag']}")
    print("checks:")
    for item in report["checks"]:
        print(f"- [{item['status']}] {item['name']}: {item['detail']}")


def main() -> None:
    load_dotenv_file()
    parser = argparse.ArgumentParser(description="Diagnose GraphRAG fallback causes")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output instead of human-readable summary",
    )
    args = parser.parse_args()

    report = _build_report(load_config())
    if args.json:
        print(json.dumps(report, indent=2))
        return
    _print_human_report(report)


if __name__ == "__main__":
    main()
