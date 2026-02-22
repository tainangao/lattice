from __future__ import annotations

from lattice.app.response.service import build_answer
from lattice.app.retrieval.contracts import RetrievalBundle, RetrievalHit


def test_direct_route_requires_context_policy() -> None:
    answer = build_answer(
        "hello",
        RetrievalBundle(route="direct", hits=tuple()),
    )
    assert answer.policy == "needs_context"
    assert answer.confidence == "low"


def test_infra_degraded_policy_when_no_hits_with_failures() -> None:
    answer = build_answer(
        "question",
        RetrievalBundle(
            route="document",
            hits=tuple(),
            degraded=True,
            backend_failures=("supabase:ConnectError",),
        ),
    )
    assert answer.policy == "infra_degraded"
    assert answer.confidence == "low"


def test_low_evidence_policy_when_no_hits_without_failures() -> None:
    answer = build_answer(
        "question",
        RetrievalBundle(route="document", hits=tuple(), degraded=False),
    )
    assert answer.policy == "low_evidence"


def test_degraded_answer_policy_with_citations() -> None:
    answer = build_answer(
        "question",
        RetrievalBundle(
            route="graph",
            hits=(
                RetrievalHit(
                    source_id="edge-1",
                    score=0.99,
                    content="Kirsten Johnson DIRECTED Dick Johnson Is Dead",
                    source_type="shared_graph",
                    location="Kirsten Johnson-DIRECTED-Dick Johnson Is Dead",
                ),
            ),
            degraded=True,
            backend_failures=("neo4j:ServiceUnavailable",),
        ),
    )
    assert answer.policy == "degraded_answer"
    assert answer.confidence in {"medium", "low"}
    assert len(answer.citations) == 1
