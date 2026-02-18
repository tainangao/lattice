from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from supabase import create_client

from lattice.prototype.config import AppConfig, select_supabase_retrieval_key


def build_data_health_report(config: AppConfig) -> dict[str, Any]:
    supabase_report = _check_supabase(config)
    neo4j_report = _check_neo4j(config)
    overall_ok = _compute_overall_ok(
        checks=[supabase_report, neo4j_report],
        allow_seeded_fallback=config.allow_seeded_fallback,
    )
    return {
        "ok": overall_ok,
        "retriever_mode": {
            "use_real_supabase": config.use_real_supabase,
            "use_real_neo4j": config.use_real_neo4j,
            "allow_seeded_fallback": config.allow_seeded_fallback,
            "allow_service_role_for_retrieval": config.allow_service_role_for_retrieval,
        },
        "supabase": supabase_report,
        "neo4j": neo4j_report,
    }


def _check_supabase(config: AppConfig) -> dict[str, Any]:
    if not config.use_real_supabase:
        return {"status": "skipped", "reason": "USE_REAL_SUPABASE=false"}

    key, key_source = select_supabase_retrieval_key(config)
    if not config.supabase_url or not key:
        return {
            "status": "error",
            "reason": "SUPABASE_URL and retrieval key are required for real mode",
        }

    try:
        client = create_client(config.supabase_url, key)
        response = (
            client.table(config.supabase_documents_table)
            .select("id,source,chunk_id,content", count="exact")
            .limit(1000)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        row_count = response.count if isinstance(response.count, int) else len(rows)
        empty_content_rows = sum(
            1
            for row in rows
            if not isinstance(row.get("content"), str) or not row["content"].strip()
        )
        return {
            "status": "ok",
            "table": config.supabase_documents_table,
            "row_count": row_count,
            "sampled_rows": len(rows),
            "sample_empty_content_rows": empty_content_rows,
            "key_source": key_source,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc)}


def _check_neo4j(config: AppConfig) -> dict[str, Any]:
    if not config.use_real_neo4j:
        return {"status": "skipped", "reason": "USE_REAL_NEO4J=false"}

    if not config.neo4j_uri or not config.neo4j_username or not config.neo4j_password:
        return {
            "status": "error",
            "reason": "NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD are required",
        }

    try:
        with GraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_username, config.neo4j_password),
        ) as driver:
            with driver.session(database=config.neo4j_database) as session:
                record = session.run(
                    "MATCH (t:Title) "
                    "WITH count(t) AS title_count "
                    "MATCH (p:Person) "
                    "WITH title_count, count(p) AS person_count "
                    "MATCH (g:Genre) "
                    "WITH title_count, person_count, count(g) AS genre_count "
                    "MATCH ()-[r]->() "
                    "RETURN title_count, person_count, genre_count, count(r) AS relationship_count"
                ).single()
        if record is None:
            return {"status": "error", "reason": "No Neo4j metrics returned"}
        return {
            "status": "ok",
            "database": config.neo4j_database,
            "title_count": int(record.get("title_count", 0)),
            "person_count": int(record.get("person_count", 0)),
            "genre_count": int(record.get("genre_count", 0)),
            "relationship_count": int(record.get("relationship_count", 0)),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "reason": str(exc)}


def _compute_overall_ok(
    checks: list[dict[str, Any]],
    allow_seeded_fallback: bool,
) -> bool:
    statuses = [check.get("status") for check in checks]
    if any(status == "error" for status in statuses):
        return allow_seeded_fallback
    if any(status == "ok" for status in statuses):
        return True
    return True
