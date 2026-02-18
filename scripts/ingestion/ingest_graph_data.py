from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _load_edges(graph_path: Path) -> list[dict[str, str]]:
    raw = json.loads(graph_path.read_text(encoding="utf-8"))
    edges = raw.get("edges", []) if isinstance(raw, dict) else raw
    if not isinstance(edges, list):
        return []

    output: list[dict[str, str]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        if not {"source", "relationship", "target"}.issubset(edge):
            continue
        output.append(
            {
                "source": str(edge.get("source", "")),
                "relationship": str(edge.get("relationship", "RELATED_TO")),
                "target": str(edge.get("target", "")),
                "evidence": str(edge.get("evidence", "")),
            }
        )
    return output


def _retry_write(session: Any, query: str, payload: list[dict[str, str]]) -> None:
    attempts = 3
    delay_seconds = 1.0
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            session.run(query, rows=payload)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_seconds)
            delay_seconds *= 2
    if last_error is not None:
        raise last_error


def _sanitize_relationship_type(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char == "_" else "_" for char in value)
    if not cleaned:
        return "RELATED_TO"
    if cleaned[0].isdigit():
        return f"R_{cleaned}"
    return cleaned.upper()


def main() -> int:
    neo4j_uri = _env("NEO4J_URI")
    neo4j_username = _env("NEO4J_USERNAME")
    neo4j_password = _env("NEO4J_PASSWORD")
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
    graph_path = Path(
        os.getenv("PROTOTYPE_GRAPH_PATH", "data/prototype/graph_edges.json")
    )

    if not graph_path.exists():
        raise FileNotFoundError(f"Graph seed file not found: {graph_path}")

    edges = _load_edges(graph_path)
    if not edges:
        print("No graph edges to ingest.")
        return 0

    grouped_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for edge in edges:
        grouped_rows[_sanitize_relationship_type(edge["relationship"])].append(edge)

    with GraphDatabase.driver(
        neo4j_uri, auth=(neo4j_username, neo4j_password)
    ) as driver:
        with driver.session(database=neo4j_database) as session:
            session.run(
                "CREATE CONSTRAINT entity_name IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE n.name IS UNIQUE"
            )
            for relationship_type, payload in grouped_rows.items():
                query = (
                    "UNWIND $rows AS row "
                    "MERGE (source:Entity {name: row.source}) "
                    "MERGE (target:Entity {name: row.target}) "
                    f"MERGE (source)-[rel:`{relationship_type}`]->(target) "
                    "SET rel.evidence = row.evidence"
                )
                _retry_write(session=session, query=query, payload=payload)

    print(f"Ingested {len(edges)} graph edges into Neo4j database '{neo4j_database}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
