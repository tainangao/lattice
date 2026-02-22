from __future__ import annotations

import re

from lattice.app.response.contracts import AnswerEnvelope, Citation
from lattice.app.retrieval.contracts import RetrievalBundle


def _confidence_for_score(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def _dedupe(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _extract_by_pattern(contents: list[str], pattern: str) -> list[str]:
    compiled = re.compile(pattern)
    values: list[str] = []
    for content in contents:
        match = compiled.search(content)
        if match:
            value = match.group(1).strip()
            if value:
                values.append(value)
    return _dedupe(values)


def _graph_summary(query: str, top_lines: list[str]) -> str:
    normalized = query.lower()

    if "director" in normalized or "directed" in normalized:
        directors = _extract_by_pattern(top_lines, r"^([^.;]+?)\s+DIRECTED\s+")
        if not directors:
            directors = _extract_by_pattern(top_lines, r"directors:\s*([^;]+)")
        if directors:
            return f"Director evidence points to: {', '.join(directors)}."

    if "actor" in normalized or "cast" in normalized or "starring" in normalized:
        actors = _extract_by_pattern(top_lines, r"^([^.;]+?)\s+ACTED_IN\s+")
        if not actors:
            actors = _extract_by_pattern(top_lines, r"cast:\s*([^;]+)")
        if actors:
            return f"Cast evidence points to: {', '.join(actors)}."

    if "genre" in normalized or "category" in normalized:
        genres = _extract_by_pattern(top_lines, r"\sIN_GENRE\s+([^.;]+)")
        if not genres:
            genres = _extract_by_pattern(top_lines, r"genres:\s*([^;]+)")
        if genres:
            return f"Genre evidence points to: {', '.join(genres)}."

    if "country" in normalized or "where" in normalized:
        countries = _extract_by_pattern(top_lines, r"\sIN_COUNTRY\s+([^.;]+)")
        if not countries:
            countries = _extract_by_pattern(top_lines, r"countries:\s*([^;]+)")
        if countries:
            return f"Country evidence points to: {', '.join(countries)}."

    if "rating" in normalized:
        ratings = _extract_by_pattern(top_lines, r"\sHAS_RATING\s+([^.;]+)")
        if not ratings:
            ratings = _extract_by_pattern(top_lines, r"rating:\s*([^;]+)")
        if ratings:
            return f"Rating evidence points to: {', '.join(ratings)}."

    return "Top evidence from graph retrieval:"


def build_answer(query: str, retrieval: RetrievalBundle) -> AnswerEnvelope:
    if retrieval.route == "direct":
        return AnswerEnvelope(
            answer=(
                "I need retrieval evidence for that request. "
                "Try asking with document or graph context."
            ),
            confidence="low",
            citations=tuple(),
            policy="needs_context",
            action="Ask a question that references private docs, graph entities, or counts.",
        )

    if not retrieval.hits and retrieval.degraded:
        backend_text = ", ".join(retrieval.backend_failures) or "unknown backend"
        return AnswerEnvelope(
            answer=(
                "I could not retrieve evidence because part of the retrieval infrastructure "
                f"is unavailable ({backend_text})."
            ),
            confidence="low",
            citations=tuple(),
            policy="infra_degraded",
            action="Retry shortly. If it persists, verify Supabase/Neo4j connectivity.",
        )

    if not retrieval.hits:
        return AnswerEnvelope(
            answer=(
                "I could not find enough evidence in the selected sources. "
                "Upload a relevant file or refine the query terms."
            ),
            confidence="low",
            citations=tuple(),
            policy="low_evidence",
            action="Refine keywords, add context, or upload relevant documents.",
        )

    top_lines = [hit.content for hit in retrieval.hits[:3]]
    citations = tuple(
        Citation(source_id=hit.source_id, location=hit.location)
        for hit in retrieval.hits[:5]
    )

    prefix = ""
    policy = "grounded"
    action = "Ask a follow-up question to drill into cited sources."
    if retrieval.degraded:
        backend_text = ", ".join(retrieval.backend_failures)
        prefix = (
            "Warning: one or more retrieval backends failed and fallback data was used "
            f"({backend_text}). Results may be incomplete.\n"
        )
        policy = "degraded_answer"
        action = "Retry after backend recovery for a more complete answer."

    if retrieval.route == "aggregate":
        summary = top_lines[0]
    elif retrieval.route in {"graph", "hybrid"}:
        summary = _graph_summary(query, top_lines)
    else:
        summary = "Top evidence from document retrieval:"

    evidence_lines = "\n".join(f"- {line}" for line in top_lines)
    answer = (
        f"{prefix}{summary}\n"
        f"Rerank: `{retrieval.rerank_strategy}`\n"
        f"Evidence:\n{evidence_lines}"
    )
    confidence = _confidence_for_score(retrieval.hits[0].score)
    if retrieval.degraded and confidence == "high":
        confidence = "medium"
    return AnswerEnvelope(
        answer=answer,
        confidence=confidence,
        citations=citations,
        policy=policy,
        action=action,
    )
