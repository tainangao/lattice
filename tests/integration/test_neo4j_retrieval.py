from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from neo4j import GraphDatabase

from lattice.prototype.config import load_config
from lattice.prototype.service import PrototypeService


def _neo4j_integration_ready() -> bool:
    required = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    return all(os.getenv(name) for name in required)


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _neo4j_integration_ready(),
        reason="Neo4j integration env vars are not configured",
    ),
]


@pytest.mark.asyncio
async def test_real_neo4j_retrieval_returns_probe_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_suffix = uuid4().hex[:8]
    probe_show_id = f"integration-show-{probe_suffix}"
    probe_marker = f"zzprobe{probe_suffix}"
    probe_title = f"Integration Title {probe_marker}"
    probe_person = f"Actor {probe_marker}"
    probe_genre = f"Genre {probe_marker}"

    config = load_config()
    assert config.neo4j_uri is not None
    assert config.neo4j_username is not None
    assert config.neo4j_password is not None

    with GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_username, config.neo4j_password),
    ) as driver:
        with driver.session(database=config.neo4j_database) as session:
            session.run(
                "MERGE (t:Title {show_id: $show_id}) "
                "SET t.title = $title, t.type = 'TV Show', t.release_year = 2026 "
                "MERGE (p:Person {name: $person}) "
                "MERGE (g:Genre {name: $genre}) "
                "MERGE (p)-[:ACTED_IN]->(t) "
                "MERGE (t)-[:IN_GENRE]->(g)",
                show_id=probe_show_id,
                title=probe_title,
                person=probe_person,
                genre=probe_genre,
            ).consume()

        try:
            monkeypatch.setenv("USE_REAL_SUPABASE", "false")
            monkeypatch.setenv("USE_REAL_NEO4J", "true")
            monkeypatch.setenv("ALLOW_SEEDED_FALLBACK", "false")

            service = PrototypeService(load_config())
            probe_query = (
                f"Which TV titles involve {probe_person} and {probe_genre} "
                f"and {probe_marker}?"
            )

            response = None
            found = False
            for _ in range(8):
                response = await service.run_query(probe_query)
                if any(
                    snippet.source_id == f"Title:{probe_show_id}"
                    for snippet in response.snippets
                ):
                    found = True
                    break
                await asyncio.sleep(0.5)

            assert response is not None
            assert response.route.mode.value == "graph"
            assert found, [snippet.source_id for snippet in response.snippets]
            assert any(probe_title in snippet.text for snippet in response.snippets)
        finally:
            with driver.session(database=config.neo4j_database) as session:
                session.run(
                    "MATCH (t:Title {show_id: $show_id}) "
                    "OPTIONAL MATCH (p:Person {name: $person})-[r1:ACTED_IN]->(t) "
                    "OPTIONAL MATCH (t)-[r2:IN_GENRE]->(g:Genre {name: $genre}) "
                    "DELETE r1, r2",
                    show_id=probe_show_id,
                    person=probe_person,
                    genre=probe_genre,
                ).consume()
                session.run(
                    "MATCH (t:Title {show_id: $show_id}) DELETE t",
                    show_id=probe_show_id,
                ).consume()
                session.run(
                    "MATCH (p:Person {name: $person}) "
                    "WHERE NOT (p)-[:DIRECTED|ACTED_IN]->(:Title) "
                    "DELETE p",
                    person=probe_person,
                ).consume()
                session.run(
                    "MATCH (g:Genre {name: $genre}) "
                    "WHERE NOT (:Title)-[:IN_GENRE]->(g) "
                    "DELETE g",
                    genre=probe_genre,
                ).consume()
