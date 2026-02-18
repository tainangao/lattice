from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from supabase import create_client

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from lattice.prototype.config import load_config
from lattice.prototype.data_health import build_data_health_report


def _fetch_supabase_rows(report: dict[str, Any], config: Any) -> list[dict[str, Any]]:
    supabase_status = report.get("supabase", {})
    if supabase_status.get("status") != "ok":
        return []

    key = config.supabase_service_role_key or config.supabase_key
    if not config.supabase_url or not key:
        return []

    client = create_client(config.supabase_url, key)
    rows: list[dict[str, Any]] = []
    page_size = 1000
    start = 0
    while True:
        response = (
            client.table(config.supabase_documents_table)
            .select("id,source,chunk_id,content")
            .range(start, start + page_size - 1)
            .execute()
        )
        page = response.data if isinstance(response.data, list) else []
        if not page:
            break
        rows.extend(item for item in page if isinstance(item, dict))
        if len(page) < page_size:
            break
        start += page_size
    return rows


def _supabase_quality_checks(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "skipped", "reason": "No rows available"}

    missing_content = sum(
        1
        for row in rows
        if not isinstance(row.get("content"), str) or not row["content"].strip()
    )
    key_pairs = [
        (str(row.get("source", "")), str(row.get("chunk_id", ""))) for row in rows
    ]
    duplicates = sum(count - 1 for count in Counter(key_pairs).values() if count > 1)

    return {
        "status": "ok" if missing_content == 0 and duplicates == 0 else "warning",
        "row_count": len(rows),
        "missing_content_rows": missing_content,
        "duplicate_source_chunk_pairs": duplicates,
    }


def main() -> int:
    config = load_config()
    report = build_data_health_report(config)

    supabase_rows = _fetch_supabase_rows(report=report, config=config)
    report["supabase_quality"] = _supabase_quality_checks(supabase_rows)

    print(json.dumps(report, indent=2))

    required_failures = []
    if report.get("supabase", {}).get("status") == "error":
        required_failures.append("supabase")
    if report.get("neo4j", {}).get("status") == "error":
        required_failures.append("neo4j")

    if required_failures:
        print(f"Validation failed for: {', '.join(required_failures)}")
        return 1

    print("Phase 2 data validation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
