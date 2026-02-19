from __future__ import annotations

from dataclasses import dataclass

from lattice.prototype.models import RetrievalMode, SourceSnippet


@dataclass(frozen=True)
class CriticAssessment:
    confidence: float
    needs_refinement: bool
    reason_codes: list[str]


def assess_retrieval_quality(
    route_mode: RetrievalMode | None,
    snippets: list[SourceSnippet],
    answer: str,
    confidence_threshold: float,
    min_snippets: int,
    refinement_attempt: int,
    max_refinement_rounds: int,
) -> CriticAssessment:
    if route_mode == RetrievalMode.DIRECT:
        return CriticAssessment(
            confidence=1.0,
            needs_refinement=False,
            reason_codes=["direct_route"],
        )

    reason_codes: list[str] = []
    if not snippets:
        reason_codes.append("no_snippets")

    snippet_count = len(snippets)
    if snippet_count < min_snippets:
        reason_codes.append("low_snippet_count")

    avg_score = _average_score(snippets)
    if avg_score < confidence_threshold:
        reason_codes.append("low_avg_score")

    if route_mode == RetrievalMode.BOTH and _source_diversity(snippets) < 2:
        reason_codes.append("low_source_diversity")

    if snippets and not _has_citation_signal(answer):
        reason_codes.append("missing_citation_signal")

    confidence = _compute_confidence(
        snippet_count, min_snippets, avg_score, reason_codes
    )
    below_threshold = confidence < confidence_threshold
    attempts_remaining = refinement_attempt < max_refinement_rounds
    needs_refinement = below_threshold and attempts_remaining
    return CriticAssessment(
        confidence=confidence,
        needs_refinement=needs_refinement,
        reason_codes=reason_codes,
    )


def _average_score(snippets: list[SourceSnippet]) -> float:
    if not snippets:
        return 0.0
    return sum(item.score for item in snippets) / len(snippets)


def _source_diversity(snippets: list[SourceSnippet]) -> int:
    return len({item.source_type for item in snippets})


def _has_citation_signal(answer: str) -> bool:
    text = answer.strip().lower()
    return "sources:" in text or "[" in text


def _compute_confidence(
    snippet_count: int,
    min_snippets: int,
    avg_score: float,
    reason_codes: list[str],
) -> float:
    coverage = min(snippet_count / max(min_snippets, 1), 1.0)
    confidence = (avg_score * 0.65) + (coverage * 0.35)
    if "low_source_diversity" in reason_codes:
        confidence -= 0.08
    if "missing_citation_signal" in reason_codes:
        confidence -= 0.04
    bounded = max(0.0, min(confidence, 1.0))
    return round(bounded, 4)
