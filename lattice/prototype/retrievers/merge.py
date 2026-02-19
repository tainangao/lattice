from __future__ import annotations

from lattice.prototype.models import SourceSnippet


def rank_and_trim_snippets(
    snippets: list[SourceSnippet],
    max_results: int = 5,
) -> list[SourceSnippet]:
    if not snippets:
        return []

    retrieval_snippets = [
        snippet for snippet in snippets if snippet.source_type != "system"
    ]
    if not retrieval_snippets:
        return snippets[:max_results]

    top_score = max(snippet.score for snippet in retrieval_snippets)
    min_score = max(0.12, top_score * 0.4)
    filtered = [snippet for snippet in retrieval_snippets if snippet.score >= min_score]
    ranked = filtered if filtered else retrieval_snippets[:1]
    ranked = sorted(ranked, key=lambda snippet: snippet.score, reverse=True)
    return dedupe_snippets(ranked)[:max_results]


def dedupe_snippets(snippets: list[SourceSnippet]) -> list[SourceSnippet]:
    seen: set[str] = set()
    unique_snippets: list[SourceSnippet] = []
    for snippet in snippets:
        dedupe_key = f"{snippet.source_type}:{snippet.source_id}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique_snippets.append(snippet)
    return unique_snippets
