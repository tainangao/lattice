from __future__ import annotations

from lattice.app.response.contracts import AnswerEnvelope, Citation
from lattice.app.retrieval.contracts import RetrievalBundle


def build_answer(query: str, retrieval: RetrievalBundle) -> AnswerEnvelope:
    if retrieval.route == "direct":
        return AnswerEnvelope(
            answer=(
                "I need retrieval evidence for that request. "
                "Try asking with document or graph context."
            ),
            confidence="low",
            citations=tuple(),
        )

    if not retrieval.hits:
        return AnswerEnvelope(
            answer=(
                "I could not find enough evidence in the selected sources. "
                "Upload a relevant file or refine the query terms."
            ),
            confidence="low",
            citations=tuple(),
        )

    top_lines = [hit.content for hit in retrieval.hits[:3]]
    citations = tuple(
        Citation(source_id=hit.source_id, location=hit.location)
        for hit in retrieval.hits[:5]
    )
    answer = f"Route `{retrieval.route}` used for: {query}\n" + "\n".join(top_lines)
    confidence = "high" if retrieval.hits[0].score >= 0.4 else "medium"
    return AnswerEnvelope(answer=answer, confidence=confidence, citations=citations)
