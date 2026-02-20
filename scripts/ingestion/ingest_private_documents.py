from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from supabase import create_client


def _env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    if chunk_size <= overlap:
        raise ValueError("INGEST_CHUNK_SIZE must be greater than INGEST_CHUNK_OVERLAP")

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(words):
        chunk_words = words[start : start + chunk_size]
        chunks.append(" ".join(chunk_words))
        start += step
    return chunks


def _deterministic_id(source: str, chunk_id: str) -> str:
    raw = f"{source}:{chunk_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _retry_upsert(client: Any, table: str, payload: list[dict[str, Any]]) -> None:
    attempts = 3
    delay_seconds = 1.0
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            client.table(table).upsert(payload, on_conflict="id").execute()
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_seconds)
            delay_seconds *= 2
    if last_error is not None:
        raise last_error


def _rows_from_seed_documents(
    docs_path: Path,
    chunk_size: int,
    overlap: int,
    user_id: str,
) -> list[dict[str, Any]]:
    raw = json.loads(docs_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []

    output_rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "unknown-source"))
        seed_chunk_id = str(item.get("chunk_id", "chunk-0"))
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        split_chunks = _chunk_text(content, chunk_size=chunk_size, overlap=overlap)
        for index, chunk_text in enumerate(split_chunks):
            derived_chunk_id = f"{seed_chunk_id}-{index}"
            output_rows.append(
                {
                    "id": _deterministic_id(source, derived_chunk_id),
                    "user_id": user_id,
                    "source": source,
                    "chunk_id": derived_chunk_id,
                    "content": chunk_text,
                    "metadata": {
                        "seed_chunk_id": seed_chunk_id,
                        "user_id": user_id,
                        "ingested_at": int(time.time()),
                    },
                }
            )
    return output_rows


def main() -> int:
    supabase_url = _env("SUPABASE_URL")
    supabase_key = _env("SUPABASE_SERVICE_ROLE_KEY")
    table = os.getenv("SUPABASE_DOCUMENTS_TABLE", "embeddings")
    ingest_user_id = _env("INGEST_USER_ID")
    docs_path = Path(
        os.getenv("PROTOTYPE_DOCS_PATH", "data/prototype/private_documents.json")
    )
    chunk_size = int(os.getenv("INGEST_CHUNK_SIZE", "800"))
    overlap = int(os.getenv("INGEST_CHUNK_OVERLAP", "120"))

    if not docs_path.exists():
        raise FileNotFoundError(f"Document seed file not found: {docs_path}")

    rows = _rows_from_seed_documents(
        docs_path,
        chunk_size=chunk_size,
        overlap=overlap,
        user_id=ingest_user_id,
    )
    if not rows:
        print("No document rows to ingest.")
        return 0

    client = create_client(supabase_url, supabase_key)
    _retry_upsert(client=client, table=table, payload=rows)
    print(f"Ingested {len(rows)} document rows into table '{table}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
