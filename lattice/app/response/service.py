from __future__ import annotations

from lattice.app.response.contracts import AnswerEnvelope, Citation
from lattice.app.retrieval.contracts import RetrievalBundle


def _confidence_for_score(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


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

    answer = (
        f"{prefix}Route `{retrieval.route}` used for: {query}\n"
        f"Rerank: `{retrieval.rerank_strategy}`\n" + "\n".join(top_lines)
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
