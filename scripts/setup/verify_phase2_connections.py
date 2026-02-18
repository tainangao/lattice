from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path

from neo4j import GraphDatabase


def _print_result(name: str, ok: bool, detail: str) -> bool:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")
    return ok


def _required(name: str) -> str | None:
    value = os.getenv(name)
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


def _verify_seed_paths() -> bool:
    docs_path = Path(
        os.getenv("PROTOTYPE_DOCS_PATH", "data/prototype/private_documents.json")
    )
    graph_path = Path(
        os.getenv("PROTOTYPE_GRAPH_PATH", "data/prototype/graph_edges.json")
    )
    docs_ok = docs_path.exists()
    graph_ok = graph_path.exists()
    _print_result("prototype docs path", docs_ok, str(docs_path))
    _print_result("prototype graph path", graph_ok, str(graph_path))
    return docs_ok and graph_ok


def _verify_supabase() -> bool:
    url = _required("SUPABASE_URL")
    key = _required("SUPABASE_KEY")
    if not url or not key:
        return _print_result(
            "supabase",
            False,
            "SUPABASE_URL and SUPABASE_KEY must both be set",
        )

    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return _print_result(
            "supabase",
            False,
            "SUPABASE_URL must be the HTTP project URL (https://<project-ref>.supabase.co), not a Postgres connection string",
        )

    endpoint = f"{url.rstrip('/')}/rest/v1/"
    request = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return _print_result(
                "supabase",
                True,
                f"reachable at {endpoint} (http {response.status})",
            )
    except urllib.error.HTTPError as exc:
        if exc.code in {200, 401, 404}:
            return _print_result(
                "supabase",
                True,
                f"reachable at {endpoint} (http {exc.code})",
            )
        return _print_result(
            "supabase",
            False,
            f"http error at {endpoint}: {exc.code}",
        )
    except Exception as exc:  # noqa: BLE001
        return _print_result("supabase", False, f"connection failed: {exc}")


def _verify_neo4j() -> bool:
    uri = _required("NEO4J_URI")
    username = _required("NEO4J_USERNAME")
    password = _required("NEO4J_PASSWORD")
    database = _required("NEO4J_DATABASE") or "neo4j"

    if not uri or not username or not password:
        return _print_result(
            "neo4j",
            False,
            "NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD must be set",
        )

    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                result = session.run("RETURN 1 AS ok")
                record = result.single()
                if not record or record.get("ok") != 1:
                    return _print_result(
                        "neo4j",
                        False,
                        f"connected to {uri} but validation query failed for database {database}",
                    )
        return _print_result(
            "neo4j",
            True,
            f"connected to {uri} (database={database})",
        )
    except Exception as exc:  # noqa: BLE001
        return _print_result("neo4j", False, f"connection failed: {exc}")


def main() -> int:
    print("Phase 2 connectivity verification")
    print("-" * 36)

    checks = [
        _verify_seed_paths(),
        _verify_supabase(),
        _verify_neo4j(),
    ]

    if all(checks):
        print("All Phase 2 checks passed.")
        return 0

    print("One or more checks failed. Update .env and rerun.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
