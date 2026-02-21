from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from lattice.app.graph.contracts import GraphEdge
from lattice.app.ingestion.contracts import DocumentChunk, IngestionJob
from lattice.app.memory.contracts import ConversationTurn


@dataclass
class RuntimeStore:
    ingestion_jobs: dict[str, IngestionJob] = field(default_factory=dict)
    private_chunks_by_user: dict[str, list[DocumentChunk]] = field(default_factory=dict)
    conversation_turns_by_thread: dict[str, list[ConversationTurn]] = field(
        default_factory=dict
    )
    demo_usage_by_session: dict[str, int] = field(default_factory=dict)
    runtime_keys_by_session: dict[str, str] = field(default_factory=dict)
    shared_demo_documents: list[dict[str, str]] = field(default_factory=list)
    shared_graph_edges: list[GraphEdge] = field(default_factory=list)


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_store() -> RuntimeStore:
    repo_root = Path(__file__).resolve().parents[3]
    demo_docs_path = repo_root / "data" / "prototype" / "private_documents.json"
    graph_path = repo_root / "data" / "prototype" / "graph_edges.json"

    demo_docs_raw = _load_json(demo_docs_path)
    graph_raw = _load_json(graph_path)

    demo_docs: list[dict[str, str]] = []
    if isinstance(demo_docs_raw, list):
        for item in demo_docs_raw:
            if isinstance(item, dict):
                source = item.get("source")
                chunk_id = item.get("chunk_id")
                content = item.get("content")
                if (
                    isinstance(source, str)
                    and isinstance(chunk_id, str)
                    and isinstance(content, str)
                ):
                    demo_docs.append(
                        {
                            "source": source,
                            "chunk_id": chunk_id,
                            "content": content,
                        }
                    )

    graph_edges: list[GraphEdge] = []
    if isinstance(graph_raw, dict) and isinstance(graph_raw.get("edges"), list):
        for edge in graph_raw["edges"]:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source")
            relationship = edge.get("relationship")
            target = edge.get("target")
            evidence = edge.get("evidence")
            if all(
                isinstance(value, str)
                for value in (source, relationship, target, evidence)
            ):
                graph_edges.append(
                    GraphEdge(
                        source=source,
                        relationship=relationship,
                        target=target,
                        evidence=evidence,
                    )
                )

    return RuntimeStore(shared_demo_documents=demo_docs, shared_graph_edges=graph_edges)


runtime_store = _build_store()
