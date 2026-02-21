from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from lattice.app.ingestion.contracts import DocumentChunk
from lattice.app.retrieval.contracts import RetrievalHit


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


@dataclass(frozen=True)
class SupabaseVectorStore:
    url: str
    anon_key: str

    @property
    def _rpc_url(self) -> str:
        return f"{self.url.rstrip('/')}/rest/v1/rpc"

    def _headers(self, user_jwt: str) -> dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {user_jwt}",
            "Content-Type": "application/json",
        }

    def upsert_chunk(self, *, user_jwt: str, chunk: DocumentChunk) -> None:
        payload = {
            "p_id": chunk.chunk_id,
            "p_user_id": chunk.metadata.user_id,
            "p_source": chunk.metadata.source,
            "p_chunk_id": chunk.chunk_id,
            "p_content": chunk.content,
            "p_metadata": {
                "page": chunk.metadata.page,
                "offset_start": chunk.metadata.offset_start,
                "offset_end": chunk.metadata.offset_end,
                "user_id": chunk.metadata.user_id,
                "source": chunk.metadata.source,
            },
            "p_embedding": _vector_literal(list(chunk.embedding)),
        }

        endpoint = f"{self._rpc_url}/upsert_embedding_chunk"
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                endpoint,
                headers=self._headers(user_jwt),
                content=json.dumps(payload),
            )
        response.raise_for_status()

    def match_chunks(
        self,
        *,
        user_jwt: str,
        query_embedding: list[float],
        match_count: int,
        match_threshold: float,
    ) -> list[RetrievalHit]:
        payload = {
            "query_embedding": _vector_literal(query_embedding),
            "match_count": match_count,
            "match_threshold": match_threshold,
        }
        endpoint = f"{self._rpc_url}/match_embeddings"
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                endpoint,
                headers=self._headers(user_jwt),
                content=json.dumps(payload),
            )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            return []

        hits: list[RetrievalHit] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            chunk_id = row.get("chunk_id")
            content = row.get("content")
            source = row.get("source")
            similarity = row.get("similarity")
            metadata = row.get("metadata")
            if not isinstance(chunk_id, str) or not isinstance(content, str):
                continue
            if not isinstance(source, str) or not isinstance(similarity, (int, float)):
                continue
            location = source
            if isinstance(metadata, dict):
                page = metadata.get("page")
                offset_start = metadata.get("offset_start")
                offset_end = metadata.get("offset_end")
                if (
                    isinstance(page, int)
                    and isinstance(offset_start, int)
                    and isinstance(offset_end, int)
                ):
                    location = f"{source}:page={page}:{offset_start}-{offset_end}"
            hits.append(
                RetrievalHit(
                    source_id=chunk_id,
                    score=float(similarity),
                    content=content,
                    source_type="private_document",
                    location=location,
                )
            )
        return hits
