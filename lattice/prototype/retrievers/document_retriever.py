from __future__ import annotations

import json
from pathlib import Path

from lattice.prototype.models import SourceSnippet
from lattice.prototype.retrievers.scoring import overlap_score


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


def _load_seed_documents(path: str) -> list[dict[str, str]]:
    doc_file = Path(path)
    if not doc_file.exists():
        return []
    raw = json.loads(doc_file.read_text(encoding="utf-8"))
    return [item for item in raw if {"source", "chunk_id", "content"}.issubset(item)]
