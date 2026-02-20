from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from supabase import Client, create_client

from lattice.prototype.models import SourceSnippet
from lattice.prototype.retrievers.scoring import overlap_score, tokenize

DOCUMENT_QUERY_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "document",
    "documents",
    "does",
    "file",
    "files",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "please",
    "tell",
    "that",
    "the",
    "this",
    "what",
    "which",
    "with",
}


class SeedDocumentRetriever:
    def __init__(self, docs_path: str) -> None:
        self._docs_path = docs_path

    async def retrieve(
        self,
        question: str,
        limit: int = 3,
        runtime_user_id: str | None = None,
    ) -> list[SourceSnippet]:
        _ = runtime_user_id
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

    async def retrieve(
        self,
        question: str,
        limit: int = 3,
        runtime_user_id: str | None = None,
    ) -> list[SourceSnippet]:
        return await asyncio.to_thread(
            self._retrieve_sync,
            question,
            limit,
            runtime_user_id,
        )

    async def upsert_private_document(
        self,
        user_id: str,
        source: str,
        content: str,
        chunk_size: int = 800,
        overlap: int = 120,
    ) -> int:
        return await asyncio.to_thread(
            self._upsert_private_document_sync,
            user_id,
            source,
            content,
            chunk_size,
            overlap,
        )

    def _retrieve_sync(
        self,
        question: str,
        limit: int,
        runtime_user_id: str | None,
    ) -> list[SourceSnippet]:
        query_tokens = _document_query_tokens(question)
        rows = self._fetch_candidate_rows(
            question,
            max(limit * 20, 100),
            runtime_user_id,
        )
        ranked = sorted(
            rows,
            key=lambda item: _document_overlap_score(
                question, _row_content(item), query_tokens
            ),
            reverse=True,
        )
        top_rows = [
            item
            for item in ranked
            if _document_overlap_score(question, _row_content(item), query_tokens)
            >= 0.12
        ][:limit]
        return [
            SourceSnippet(
                source_type="document",
                source_id=_row_source_id(item),
                text=_row_content(item),
                score=_document_overlap_score(
                    question, _row_content(item), query_tokens
                ),
            )
            for item in top_rows
        ]

    def _fetch_candidate_rows(
        self,
        question: str,
        fetch_limit: int,
        runtime_user_id: str | None,
    ) -> list[dict[str, Any]]:
        response = self._query_candidate_rows(question, fetch_limit, runtime_user_id)
        rows = response.data
        if not isinstance(rows, list):
            return []
        return [item for item in rows if isinstance(item, dict)]

    def _query_candidate_rows(
        self,
        question: str,
        fetch_limit: int,
        runtime_user_id: str | None,
    ) -> Any:
        tokens = _document_query_tokens(question)[:6]
        query = self._client.table(self._table_name).select("*")
        if runtime_user_id:
            query = query.eq("user_id", runtime_user_id)
        if tokens:
            clauses = [f"content.ilike.%{token}%" for token in tokens]
            query = query.or_(",".join(clauses))
        return query.limit(fetch_limit).execute()

    def _upsert_private_document_sync(
        self,
        user_id: str,
        source: str,
        content: str,
        chunk_size: int,
        overlap: int,
    ) -> int:
        normalized_source = source.strip()
        normalized_content = content.strip()
        normalized_user_id = user_id.strip()
        if not normalized_source or not normalized_content or not normalized_user_id:
            return 0

        chunks = _chunk_text(normalized_content, chunk_size=chunk_size, overlap=overlap)
        rows = [
            {
                "id": _deterministic_id(normalized_user_id, normalized_source, index),
                "user_id": normalized_user_id,
                "source": normalized_source,
                "chunk_id": f"chunk-{index}",
                "content": chunk_text,
                "metadata": {
                    "source": normalized_source,
                    "chunk_id": f"chunk-{index}",
                    "ingested_at": int(time.time()),
                },
            }
            for index, chunk_text in enumerate(chunks)
        ]
        if not rows:
            return 0

        self._client.table(self._table_name).upsert(rows, on_conflict="id").execute()
        return len(rows)


def _document_query_tokens(question: str) -> list[str]:
    return [
        token
        for token in tokenize(question)
        if len(token) >= 4 and token not in DOCUMENT_QUERY_STOP_WORDS
    ]


def _document_overlap_score(
    question: str,
    content: str,
    query_tokens: list[str] | None = None,
) -> float:
    tokens = (
        query_tokens if query_tokens is not None else _document_query_tokens(question)
    )
    if not tokens:
        return overlap_score(question, content)

    content_tokens = tokenize(content)
    hits = sum(1 for token in tokens if token in content_tokens)
    return hits / len(tokens)


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


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    if chunk_size <= overlap:
        return []

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(words):
        chunk_words = words[start : start + chunk_size]
        chunks.append(" ".join(chunk_words))
        start += step
    return chunks


def _deterministic_id(user_id: str, source: str, chunk_index: int) -> str:
    raw = f"{user_id}:{source}:{chunk_index}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]
