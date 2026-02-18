from __future__ import annotations

import json
from pathlib import Path

from lattice.prototype.models import SourceSnippet
from lattice.prototype.retrievers.scoring import overlap_score


class SeedGraphRetriever:
    def __init__(self, graph_path: str) -> None:
        self._graph_path = graph_path

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        edges = _load_graph_edges(self._graph_path)
        ranked = sorted(
            edges,
            key=lambda edge: overlap_score(question, _edge_text(edge)),
            reverse=True,
        )
        top_edges = [
            edge for edge in ranked if overlap_score(question, _edge_text(edge)) > 0
        ][:limit]
        return [
            SourceSnippet(
                source_type="graph",
                source_id=f"{edge['source']}->{edge['target']}",
                text=_edge_summary(edge),
                score=overlap_score(question, _edge_text(edge)),
            )
            for edge in top_edges
        ]


def _edge_text(edge: dict[str, str]) -> str:
    return " ".join(
        [
            edge.get("source", ""),
            edge.get("relationship", ""),
            edge.get("target", ""),
            edge.get("evidence", ""),
        ]
    )


def _edge_summary(edge: dict[str, str]) -> str:
    return (
        f"{edge.get('source', 'Unknown')} {edge.get('relationship', 'RELATED_TO')} "
        f"{edge.get('target', 'Unknown')}. Evidence: {edge.get('evidence', 'n/a')}"
    )


def _load_graph_edges(path: str) -> list[dict[str, str]]:
    graph_file = Path(path)
    if not graph_file.exists():
        return []
    raw = json.loads(graph_file.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        edges = raw.get("edges", [])
    else:
        edges = raw
    return [
        item for item in edges if {"source", "relationship", "target"}.issubset(item)
    ]
