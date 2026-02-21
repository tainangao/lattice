from __future__ import annotations

from collections import OrderedDict

from lattice.app.retrieval.contracts import RetrievalBundle, RetrievalHit
from lattice.app.runtime.store import RuntimeStore


def _token_overlap_score(query: str, content: str) -> float:
    query_tokens = {token for token in query.lower().split() if token}
    content_tokens = {token for token in content.lower().split() if token}
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / len(query_tokens)


def _document_hits(
    store: RuntimeStore, user_id: str | None, query: str
) -> list[RetrievalHit]:
    hits: list[RetrievalHit] = []
    if user_id:
        for chunk in store.private_chunks_by_user.get(user_id, []):
            score = _token_overlap_score(query, chunk.content)
            if score <= 0:
                continue
            hits.append(
                RetrievalHit(
                    source_id=chunk.chunk_id,
                    score=score,
                    content=chunk.content,
                    source_type="private_document",
                    location=(
                        f"{chunk.metadata.source}:page={chunk.metadata.page}:"
                        f"{chunk.metadata.offset_start}-{chunk.metadata.offset_end}"
                    ),
                )
            )
    else:
        for chunk in store.shared_demo_documents:
            content = chunk["content"]
            score = _token_overlap_score(query, content)
            if score <= 0:
                continue
            hits.append(
                RetrievalHit(
                    source_id=chunk["chunk_id"],
                    score=score,
                    content=content,
                    source_type="demo_document",
                    location=chunk["source"],
                )
            )
    return sorted(hits, key=lambda hit: hit.score, reverse=True)


def _graph_hits(store: RuntimeStore, query: str) -> list[RetrievalHit]:
    hits: list[RetrievalHit] = []
    for index, edge in enumerate(store.shared_graph_edges, start=1):
        content = (
            f"{edge.source} {edge.relationship} {edge.target}. "
            f"Evidence: {edge.evidence}"
        )
        score = _token_overlap_score(query, content)
        if score <= 0:
            continue
        hits.append(
            RetrievalHit(
                source_id=f"graph-edge-{index}",
                score=score,
                content=content,
                source_type="shared_graph",
                location=f"{edge.source}-{edge.relationship}-{edge.target}",
            )
        )
    return sorted(hits, key=lambda hit: hit.score, reverse=True)


def retrieve(
    *,
    store: RuntimeStore,
    route: str,
    query: str,
    user_id: str | None,
) -> RetrievalBundle:
    if route == "graph":
        return RetrievalBundle(route=route, hits=tuple(_graph_hits(store, query)[:5]))
    if route == "document":
        return RetrievalBundle(
            route=route,
            hits=tuple(_document_hits(store, user_id, query)[:5]),
        )
    if route == "hybrid":
        combined = _document_hits(store, user_id, query) + _graph_hits(store, query)
        deduped: OrderedDict[str, RetrievalHit] = OrderedDict()
        for hit in sorted(combined, key=lambda row: row.score, reverse=True):
            deduped.setdefault(hit.source_id, hit)
        return RetrievalBundle(route=route, hits=tuple(list(deduped.values())[:6]))
    if route == "aggregate":
        doc_hits = _document_hits(store, user_id, query)
        graph_hits = _graph_hits(store, query)
        count_content = (
            f"Aggregate count: documents={len(doc_hits)}, graph_edges={len(graph_hits)}, "
            f"total={len(doc_hits) + len(graph_hits)}"
        )
        aggregate = RetrievalHit(
            source_id="aggregate-count",
            score=1.0,
            content=count_content,
            source_type="aggregate",
            location="aggregate://counts",
        )
        return RetrievalBundle(route=route, hits=(aggregate,))
    return RetrievalBundle(route=route, hits=tuple())
