from __future__ import annotations

import re


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def overlap_score(query: str, candidate: str) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    candidate_tokens = tokenize(candidate)
    hits = len(query_tokens.intersection(candidate_tokens))
    return hits / len(query_tokens)
