from __future__ import annotations

from collections import OrderedDict

from lattice.app.graph.neo4j_store import Neo4jGraphStore
from lattice.app.retrieval.contracts import RetrievalBundle, RetrievalHit
from lattice.app.retrieval.embeddings import EmbeddingProvider
from lattice.app.retrieval.supabase_store import SupabaseVectorStore
from lattice.app.runtime.store import RuntimeStore


def _token_overlap_score(query: str, content: str) -> float:
    query_tokens = {token for token in query.lower().split() if token}
    content_tokens = {token for token in content.lower().split() if token}
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / len(query_tokens)


def _fallback_document_hits(
    store: RuntimeStore,
    user_id: str | None,
    query: str,
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
            score = _token_overlap_score(query, chunk["content"])
            if score <= 0:
                continue
            hits.append(
                RetrievalHit(
                    source_id=chunk["chunk_id"],
                    score=score,
                    content=chunk["content"],
                    source_type="demo_document",
                    location=chunk["source"],
                )
            )
    return sorted(hits, key=lambda row: row.score, reverse=True)


def _fallback_graph_hits(store: RuntimeStore, query: str) -> list[RetrievalHit]:
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
    return sorted(hits, key=lambda row: row.score, reverse=True)


def _query_embedding(
    *,
    store: RuntimeStore,
    embedding_provider: EmbeddingProvider,
    query: str,
) -> list[float]:
    cached = store.query_embedding_cache.get(query)
    if cached is not None:
        return list(cached)
    vector = embedding_provider.embed_query(query)
    store.query_embedding_cache[query] = tuple(vector)
    return vector


def _document_hits(
    *,
    store: RuntimeStore,
    query: str,
    user_id: str | None,
    user_access_token: str | None,
    embedding_provider: EmbeddingProvider,
    supabase_store: SupabaseVectorStore | None,
    limit: int,
) -> list[RetrievalHit]:
    if user_id and user_access_token and supabase_store:
        try:
            vector = _query_embedding(
                store=store,
                embedding_provider=embedding_provider,
                query=query,
            )
            hits = supabase_store.match_chunks(
                user_jwt=user_access_token,
                query_embedding=vector,
                match_count=limit,
                match_threshold=0.1,
            )
            if hits:
                return hits
        except Exception:
            pass
    return _fallback_document_hits(store=store, user_id=user_id, query=query)[:limit]


def _graph_hits(
    *,
    store: RuntimeStore,
    query: str,
    neo4j_store: Neo4jGraphStore | None,
    limit: int,
) -> list[RetrievalHit]:
    if neo4j_store:
        try:
            hits = neo4j_store.search(query=query, limit=limit)
            if hits:
                return hits
        except Exception:
            pass
    return _fallback_graph_hits(store=store, query=query)[:limit]


def retrieve(
    *,
    store: RuntimeStore,
    route: str,
    query: str,
    user_id: str | None,
    user_access_token: str | None,
    embedding_provider: EmbeddingProvider,
    supabase_store: SupabaseVectorStore | None,
    neo4j_store: Neo4jGraphStore | None,
) -> RetrievalBundle:
    cache_key = f"{route}:{user_id}:{query}"
    cached = store.retrieval_cache.get(cache_key)
    if cached is not None:
        return cached

    if route == "graph":
        result = RetrievalBundle(
            route=route,
            hits=tuple(
                _graph_hits(
                    store=store,
                    query=query,
                    neo4j_store=neo4j_store,
                    limit=5,
                )
            ),
        )
    elif route == "document":
        result = RetrievalBundle(
            route=route,
            hits=tuple(
                _document_hits(
                    store=store,
                    query=query,
                    user_id=user_id,
                    user_access_token=user_access_token,
                    embedding_provider=embedding_provider,
                    supabase_store=supabase_store,
                    limit=5,
                )
            ),
        )
    elif route == "hybrid":
        combined = _document_hits(
            store=store,
            query=query,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            limit=6,
        ) + _graph_hits(
            store=store,
            query=query,
            neo4j_store=neo4j_store,
            limit=6,
        )
        deduped: OrderedDict[str, RetrievalHit] = OrderedDict()
        for hit in sorted(combined, key=lambda row: row.score, reverse=True):
            deduped.setdefault(hit.source_id, hit)
        result = RetrievalBundle(route=route, hits=tuple(list(deduped.values())[:6]))
    elif route == "aggregate":
        doc_hits = _document_hits(
            store=store,
            query=query,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            limit=25,
        )
        graph_hits = _graph_hits(
            store=store,
            query=query,
            neo4j_store=neo4j_store,
            limit=25,
        )
        aggregate = RetrievalHit(
            source_id="aggregate-count",
            score=1.0,
            content=(
                f"Aggregate count: documents={len(doc_hits)}, graph_edges={len(graph_hits)}, "
                f"total={len(doc_hits) + len(graph_hits)}"
            ),
            source_type="aggregate",
            location="aggregate://counts",
        )
        result = RetrievalBundle(route=route, hits=(aggregate,))
    else:
        result = RetrievalBundle(route=route, hits=tuple())

    store.retrieval_cache[cache_key] = result
    return result
