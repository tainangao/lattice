from __future__ import annotations

import csv
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from neo4j import Driver, GraphDatabase


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _split_csv_field(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_title_row(row: dict[str, str]) -> dict[str, Any] | None:
    show_id = row.get("show_id", "").strip()
    if not show_id:
        return None
    release_year_raw = row.get("release_year", "").strip()
    release_year = int(release_year_raw) if release_year_raw.isdigit() else None
    return {
        "show_id": show_id,
        "title": row.get("title", "").strip(),
        "type": row.get("type", "").strip(),
        "release_year": release_year,
        "date_added_raw": row.get("date_added", "").strip(),
        "duration_raw": row.get("duration", "").strip(),
        "description": row.get("description", "").strip(),
        "rating": row.get("rating", "").strip(),
        "directors": _split_csv_field(row.get("director", "")),
        "actors": _split_csv_field(row.get("cast", "")),
        "countries": _split_csv_field(row.get("country", "")),
        "genres": _split_csv_field(row.get("listed_in", "")),
    }


def _chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _retry_write(session: Any, query: str, rows: list[dict[str, Any]]) -> None:
    attempts = 3
    backoff = 1.0
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            session.run(query, rows=rows).consume()
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(backoff)
            backoff *= 2
    if last_error is not None:
        raise last_error


def _create_schema(driver: Driver, database: str) -> None:
    schema_queries = [
        "CREATE CONSTRAINT title_show_id_unique IF NOT EXISTS FOR (t:Title) REQUIRE t.show_id IS UNIQUE",
        "CREATE CONSTRAINT person_name_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT country_name_unique IF NOT EXISTS FOR (c:Country) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT genre_name_unique IF NOT EXISTS FOR (g:Genre) REQUIRE g.name IS UNIQUE",
        "CREATE CONSTRAINT rating_code_unique IF NOT EXISTS FOR (r:Rating) REQUIRE r.code IS UNIQUE",
        "CREATE INDEX title_name_idx IF NOT EXISTS FOR (t:Title) ON (t.title)",
        "CREATE INDEX title_type_idx IF NOT EXISTS FOR (t:Title) ON (t.type)",
        "CREATE INDEX title_release_year_idx IF NOT EXISTS FOR (t:Title) ON (t.release_year)",
    ]
    with driver.session(database=database) as session:
        for query in schema_queries:
            session.run(query)


def _ingest_batch(driver: Driver, database: str, rows: list[dict[str, Any]]) -> None:
    title_query = (
        "UNWIND $rows AS row "
        "MERGE (t:Title {show_id: row.show_id}) "
        "SET t.title = row.title, "
        "t.type = row.type, "
        "t.release_year = row.release_year, "
        "t.date_added_raw = row.date_added_raw, "
        "t.duration_raw = row.duration_raw, "
        "t.description = row.description"
    )
    rating_query = (
        "UNWIND $rows AS row "
        "WITH row WHERE row.rating <> '' "
        "MATCH (t:Title {show_id: row.show_id}) "
        "MERGE (r:Rating {code: row.rating}) "
        "MERGE (t)-[:HAS_RATING]->(r)"
    )
    director_query = (
        "UNWIND $rows AS row "
        "MATCH (t:Title {show_id: row.show_id}) "
        "UNWIND row.directors AS directorName "
        "MERGE (p:Person {name: directorName}) "
        "MERGE (p)-[:DIRECTED]->(t)"
    )
    actor_query = (
        "UNWIND $rows AS row "
        "MATCH (t:Title {show_id: row.show_id}) "
        "UNWIND row.actors AS actorName "
        "MERGE (p:Person {name: actorName}) "
        "MERGE (p)-[:ACTED_IN]->(t)"
    )
    country_query = (
        "UNWIND $rows AS row "
        "MATCH (t:Title {show_id: row.show_id}) "
        "UNWIND row.countries AS countryName "
        "MERGE (c:Country {name: countryName}) "
        "MERGE (t)-[:IN_COUNTRY]->(c)"
    )
    genre_query = (
        "UNWIND $rows AS row "
        "MATCH (t:Title {show_id: row.show_id}) "
        "UNWIND row.genres AS genreName "
        "MERGE (g:Genre {name: genreName}) "
        "MERGE (t)-[:IN_GENRE]->(g)"
    )

    with driver.session(database=database) as session:
        _retry_write(session, title_query, rows)
        _retry_write(session, rating_query, rows)
        _retry_write(session, director_query, rows)
        _retry_write(session, actor_query, rows)
        _retry_write(session, country_query, rows)
        _retry_write(session, genre_query, rows)


def _load_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        parsed = [_parse_title_row(row) for row in reader]
    return [row for row in parsed if row is not None]


def main() -> int:
    neo4j_uri = _env("NEO4J_URI")
    neo4j_username = _env("NEO4J_USERNAME")
    neo4j_password = _env("NEO4J_PASSWORD")
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
    csv_path = Path(os.getenv("NETFLIX_CSV_PATH", "data/netflix_titles.csv"))
    batch_size = int(os.getenv("NEO4J_INGEST_BATCH_SIZE", "500"))

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows = _load_rows(csv_path)
    if not rows:
        print("No valid rows found in CSV.")
        return 0

    with GraphDatabase.driver(
        neo4j_uri, auth=(neo4j_username, neo4j_password)
    ) as driver:
        _create_schema(driver=driver, database=neo4j_database)
        for batch in _chunks(rows, batch_size):
            _ingest_batch(driver=driver, database=neo4j_database, rows=batch)

    print(f"Ingested {len(rows)} Netflix rows into Neo4j database '{neo4j_database}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
