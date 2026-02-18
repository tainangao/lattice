from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from supabase import Client, create_client

from lattice.prototype.models import SourceSnippet
from lattice.prototype.retrievers.scoring import overlap_score, tokenize


class SeedDocumentRetriever:
    def __init__(self, docs_path: str) -> None:
        self._docs_path = docs_path

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        docs = _load_seed_documents(self._docs_path)
        ranked = sorted(
            docs,
            key=lambda item: overlap_score(question, item["content"]),
            reverse=True,
        )
        top_docs = [
            item for item in ranked if overlap_score(question, item["content"]) > 0
        ][:limit]
        return [
            SourceSnippet(
                source_type="document",
                source_id=f"{item['source']}#{item['chunk_id']}",
                text=item["content"],
                score=overlap_score(question, item["content"]),
            )
            for item in top_docs
        ]


class SupabaseDocumentRetriever:
    def __init__(self, supabase_url: str, supabase_key: str, table_name: str) -> None:
        self._table_name = table_name
        self._client: Client = create_client(supabase_url, supabase_key)

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        return await asyncio.to_thread(self._retrieve_sync, question, limit)

    def _retrieve_sync(self, question: str, limit: int) -> list[SourceSnippet]:
        rows = self._fetch_candidate_rows(question, max(limit * 20, 100))
        ranked = sorted(
            rows,
            key=lambda item: overlap_score(question, _row_content(item)),
            reverse=True,
        )
        top_rows = [
            item for item in ranked if overlap_score(question, _row_content(item)) > 0
        ][:limit]
        return [
            SourceSnippet(
                source_type="document",
                source_id=_row_source_id(item),
                text=_row_content(item),
                score=overlap_score(question, _row_content(item)),
            )
            for item in top_rows
        ]

    def _fetch_candidate_rows(
        self,
        question: str,
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        response = self._query_candidate_rows(question, fetch_limit)
        rows = response.data
        if not isinstance(rows, list):
            return []
        return [item for item in rows if isinstance(item, dict)]

    def _query_candidate_rows(self, question: str, fetch_limit: int) -> Any:
        tokens = [token for token in tokenize(question) if len(token) >= 4][:6]
        query = self._client.table(self._table_name).select("*")
        if tokens:
            clauses = [f"content.ilike.%{token}%" for token in tokens]
            query = query.or_(",".join(clauses))
        return query.limit(fetch_limit).execute()


def _load_seed_documents(path: str) -> list[dict[str, str]]:
    doc_file = Path(path)
    if not doc_file.exists():
        return []
    raw = json.loads(doc_file.read_text(encoding="utf-8"))
    return [item for item in raw if {"source", "chunk_id", "content"}.issubset(item)]


def _row_content(row: dict[str, Any]) -> str:
    content = row.get("content")
    if isinstance(content, str) and content.strip():
        return content
    text = row.get("text")
    if isinstance(text, str) and text.strip():
        return text
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        metadata_content = metadata.get("content") or metadata.get("text")
        if isinstance(metadata_content, str):
            return metadata_content
    return ""


def _row_source_id(row: dict[str, Any]) -> str:
    source = row.get("source")
    chunk_id = row.get("chunk_id")
    if isinstance(source, str) and isinstance(chunk_id, str):
        return f"{source}#{chunk_id}"

    row_id = row.get("id")
    if isinstance(row_id, str):
        return row_id
    if isinstance(row_id, int):
        return str(row_id)

    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        m_source = metadata.get("source")
        m_chunk_id = metadata.get("chunk_id")
        if isinstance(m_source, str) and isinstance(m_chunk_id, str):
            return f"{m_source}#{m_chunk_id}"

    return "supabase-document"
