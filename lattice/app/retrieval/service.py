from __future__ import annotations

import json
import re
from collections import OrderedDict

from lattice.app.graph.neo4j_store import Neo4jGraphStore
from lattice.app.retrieval.contracts import RetrievalBundle, RetrievalHit
from lattice.app.retrieval.embeddings import EmbeddingProvider
from lattice.app.retrieval.supabase_store import SupabaseVectorStore
from lattice.app.runtime.store import RuntimeStore

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def _stable_edge_source_id(source: str, relationship: str, target: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9]+",
        "-",
        f"{source.lower()}-{relationship.lower()}-{target.lower()}",
    ).strip("-")
    return f"graph-edge:{normalized or 'unknown'}"


def _token_overlap_score(query: str, content: str) -> float:
    query_tokens = {token for token in query.lower().split() if token}
    content_tokens = {token for token in content.lower().split() if token}
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens.intersection(content_tokens))
    return overlap / len(query_tokens)


def _semantic_query_key(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]", " ", query.lower())
    tokens = [
        token for token in normalized.split() if token and token not in STOP_WORDS
    ]
    if not tokens:
        return normalized.strip()
    return " ".join(sorted(tokens))


def _normalize_scores(values: list[float]) -> dict[float, float]:
    if not values:
        return {}
    minimum = min(values)
    maximum = max(values)
    if maximum <= minimum:
        return {value: 1.0 for value in values}
    return {value: (value - minimum) / (maximum - minimum) for value in values}


def _heuristic_rerank_hits(
    query: str, hits: list[RetrievalHit], limit: int
) -> list[RetrievalHit]:
    if not hits:
        return []

    score_map_by_source_type: dict[str, dict[float, float]] = {}
    grouped_scores: dict[str, list[float]] = {}
    for hit in hits:
        grouped_scores.setdefault(hit.source_type, []).append(hit.score)
    for source_type, scores in grouped_scores.items():
        score_map_by_source_type[source_type] = _normalize_scores(scores)

    reranked: list[RetrievalHit] = []
    for hit in hits:
        semantic_score = score_map_by_source_type.get(hit.source_type, {}).get(
            hit.score, 0.0
        )
        lexical_score = _token_overlap_score(query, hit.content)
        final_score = (0.7 * semantic_score) + (0.3 * lexical_score)
        reranked.append(
            RetrievalHit(
                source_id=hit.source_id,
                score=round(final_score, 6),
                content=hit.content,
                source_type=hit.source_type,
                location=hit.location,
            )
        )

    deduped: OrderedDict[str, RetrievalHit] = OrderedDict()
    for hit in sorted(reranked, key=lambda row: row.score, reverse=True):
        deduped.setdefault(hit.source_id, hit)
    return list(deduped.values())[:limit]


def _extract_json_payload(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    return stripped


def _llm_rerank_hits(
    *,
    query: str,
    hits: list[RetrievalHit],
    limit: int,
    runtime_key: str,
    model: str,
) -> list[RetrievalHit]:
    if not hits:
        return []

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except Exception:
        return []

    client = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=runtime_key,
        temperature=0.0,
        max_retries=1,
    )
    candidates = [
        {
            "source_id": hit.source_id,
            "source_type": hit.source_type,
            "location": hit.location,
            "content": hit.content[:900],
        }
        for hit in hits[:12]
    ]
    prompt = (
        "You are a retrieval reranker. Return strict JSON array rows with keys "
        "source_id and score (0-1). Keep only provided source_ids. "
        "Rank by usefulness for answering the query with grounded evidence. "
        f"Query: {query}\n"
        f"Candidates: {json.dumps(candidates)}"
    )

    try:
        response = client.invoke(prompt)
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            text = str(response.content)
        payload = json.loads(_extract_json_payload(text))
        if not isinstance(payload, list):
            return []
    except Exception:
        return []

    score_by_id: dict[str, float] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        source_id = row.get("source_id")
        score = row.get("score")
        if isinstance(source_id, str) and isinstance(score, (int, float)):
            bounded = max(0.0, min(1.0, float(score)))
            score_by_id[source_id] = bounded

    reranked = [
        RetrievalHit(
            source_id=hit.source_id,
            score=round(score_by_id.get(hit.source_id, 0.0), 6),
            content=hit.content,
            source_type=hit.source_type,
            location=hit.location,
        )
        for hit in hits
        if hit.source_id in score_by_id
    ]
    if not reranked:
        return []

    deduped: OrderedDict[str, RetrievalHit] = OrderedDict()
    for hit in sorted(reranked, key=lambda row: row.score, reverse=True):
        deduped.setdefault(hit.source_id, hit)
    return list(deduped.values())[:limit]


def _rerank_hits(
    *,
    query: str,
    hits: list[RetrievalHit],
    limit: int,
    backend: str,
    runtime_key: str | None,
    model: str,
) -> tuple[list[RetrievalHit], str]:
    if backend == "llm" and runtime_key:
        reranked = _llm_rerank_hits(
            query=query,
            hits=hits,
            limit=limit,
            runtime_key=runtime_key,
            model=model,
        )
        if reranked:
            return reranked, "llm_rerank_v1"
    return _heuristic_rerank_hits(query, hits, limit), "score_normalization_v2"


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
    for edge in store.shared_graph_edges:
        content = (
            f"{edge.source} {edge.relationship} {edge.target}. "
            f"Evidence: {edge.evidence}"
        )
        score = _token_overlap_score(query, content)
        if score <= 0:
            continue
        hits.append(
            RetrievalHit(
                source_id=_stable_edge_source_id(
                    edge.source,
                    edge.relationship,
                    edge.target,
                ),
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
    semantic_key = _semantic_query_key(query)
    cached = store.query_embedding_cache.get(semantic_key)
    if cached is not None:
        return list(cached)
    vector = embedding_provider.embed_query(query)
    store.query_embedding_cache[semantic_key] = tuple(vector)
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
) -> tuple[list[RetrievalHit], list[str]]:
    backend_failures: list[str] = []

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
                return hits[:limit], backend_failures
        except Exception as exc:
            backend_failures.append(f"supabase:{exc.__class__.__name__}")

    fallback_hits = _fallback_document_hits(store=store, user_id=user_id, query=query)
    return fallback_hits[:limit], backend_failures


def _graph_hits(
    *,
    store: RuntimeStore,
    query: str,
    neo4j_store: Neo4jGraphStore | None,
    limit: int,
) -> tuple[list[RetrievalHit], list[str]]:
    backend_failures: list[str] = []

    if neo4j_store:
        try:
            hits = neo4j_store.search(query=query, limit=limit)
            if hits:
                return hits[:limit], backend_failures
        except Exception as exc:
            backend_failures.append(f"neo4j:{exc.__class__.__name__}")

    fallback_hits = _fallback_graph_hits(store=store, query=query)
    return fallback_hits[:limit], backend_failures


def _count_documents(
    *,
    store: RuntimeStore,
    user_id: str | None,
    user_access_token: str | None,
    supabase_store: SupabaseVectorStore | None,
) -> tuple[int, list[str]]:
    backend_failures: list[str] = []
    if user_id and user_access_token and supabase_store:
        try:
            return supabase_store.count_chunks(
                user_jwt=user_access_token
            ), backend_failures
        except Exception as exc:
            backend_failures.append(f"supabase:{exc.__class__.__name__}")

    if user_id:
        return len(store.private_chunks_by_user.get(user_id, [])), backend_failures
    return len(store.shared_demo_documents), backend_failures


def _count_graph_edges(
    *,
    store: RuntimeStore,
    neo4j_store: Neo4jGraphStore | None,
) -> tuple[int, list[str]]:
    backend_failures: list[str] = []
    if neo4j_store:
        try:
            return neo4j_store.count_edges(), backend_failures
        except Exception as exc:
            backend_failures.append(f"neo4j:{exc.__class__.__name__}")
    return len(store.shared_graph_edges), backend_failures


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
    rerank_backend: str,
    rerank_model: str,
    runtime_key: str | None,
) -> RetrievalBundle:
    semantic_key = _semantic_query_key(query)
    cache_key = f"{route}:{user_id}:{semantic_key}:{rerank_backend}:{rerank_model}"
    cached = store.retrieval_cache.get(cache_key)
    if cached is not None:
        return cached

    backend_failures: list[str] = []

    if route == "graph":
        graph_hits, graph_failures = _graph_hits(
            store=store,
            query=query,
            neo4j_store=neo4j_store,
            limit=8,
        )
        backend_failures.extend(graph_failures)
        reranked, rerank_strategy = _rerank_hits(
            query=query,
            hits=graph_hits,
            limit=5,
            backend=rerank_backend,
            runtime_key=runtime_key,
            model=rerank_model,
        )
        result = RetrievalBundle(
            route=route,
            hits=tuple(reranked),
            degraded=bool(backend_failures),
            backend_failures=tuple(backend_failures),
            rerank_strategy=rerank_strategy,
        )
    elif route == "document":
        doc_hits, doc_failures = _document_hits(
            store=store,
            query=query,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            limit=8,
        )
        backend_failures.extend(doc_failures)
        reranked, rerank_strategy = _rerank_hits(
            query=query,
            hits=doc_hits,
            limit=5,
            backend=rerank_backend,
            runtime_key=runtime_key,
            model=rerank_model,
        )
        result = RetrievalBundle(
            route=route,
            hits=tuple(reranked),
            degraded=bool(backend_failures),
            backend_failures=tuple(backend_failures),
            rerank_strategy=rerank_strategy,
        )
    elif route == "hybrid":
        doc_hits, doc_failures = _document_hits(
            store=store,
            query=query,
            user_id=user_id,
            user_access_token=user_access_token,
            embedding_provider=embedding_provider,
            supabase_store=supabase_store,
            limit=10,
        )
        graph_hits, graph_failures = _graph_hits(
            store=store,
            query=query,
            neo4j_store=neo4j_store,
            limit=10,
        )
        backend_failures.extend(doc_failures)
        backend_failures.extend(graph_failures)
        combined = doc_hits + graph_hits
        reranked, rerank_strategy = _rerank_hits(
            query=query,
            hits=combined,
            limit=6,
            backend=rerank_backend,
            runtime_key=runtime_key,
            model=rerank_model,
        )
        result = RetrievalBundle(
            route=route,
            hits=tuple(reranked),
            degraded=bool(backend_failures),
            backend_failures=tuple(backend_failures),
            rerank_strategy=rerank_strategy,
        )
    elif route == "aggregate":
        document_count, doc_failures = _count_documents(
            store=store,
            user_id=user_id,
            user_access_token=user_access_token,
            supabase_store=supabase_store,
        )
        graph_edge_count, graph_failures = _count_graph_edges(
            store=store,
            neo4j_store=neo4j_store,
        )
        backend_failures.extend(doc_failures)
        backend_failures.extend(graph_failures)
        aggregate = RetrievalHit(
            source_id="aggregate-count",
            score=1.0,
            content=(
                f"Aggregate count: documents={document_count}, graph_edges={graph_edge_count}, "
                f"total={document_count + graph_edge_count}"
            ),
            source_type="aggregate",
            location="aggregate://counts",
        )
        result = RetrievalBundle(
            route=route,
            hits=(aggregate,),
            degraded=bool(backend_failures),
            backend_failures=tuple(backend_failures),
            rerank_strategy="aggregate_count",
        )
    else:
        result = RetrievalBundle(
            route=route,
            hits=tuple(),
            degraded=False,
            backend_failures=tuple(),
            rerank_strategy="none",
        )

    store.retrieval_cache[cache_key] = result
    return result
