import pytest

from lattice.prototype.orchestration import (
    build_orchestration_graph,
    create_initial_state,
)
from lattice.prototype.models import SourceSnippet


class _FakeRetriever:
    def __init__(
        self,
        snippets: list[SourceSnippet],
        should_raise: bool = False,
    ) -> None:
        self._snippets = snippets
        self._should_raise = should_raise

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        _ = question
        _ = limit
        if self._should_raise:
            raise RuntimeError("retriever failed")
        return self._snippets


@pytest.mark.asyncio
async def test_orchestration_graph_direct_path_sets_direct_mode() -> None:
    empty = _FakeRetriever([])
    graph = build_orchestration_graph(
        document_retriever=empty,
        graph_retriever=empty,
        seed_document_retriever=empty,
        seed_graph_retriever=empty,
        allow_seeded_fallback=True,
        gemini_api_key=None,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_refinement_retrieval_limit=5,
    )

    result = await graph.ainvoke(create_initial_state("hello"))

    assert result["route_mode"].value == "direct"
    assert isinstance(result["answer"], str)
    assert result["telemetry_events"]


@pytest.mark.asyncio
async def test_orchestration_graph_both_path_runs_fan_in() -> None:
    document = _FakeRetriever(
        [
            SourceSnippet(
                source_type="document",
                source_id="doc#1",
                text="Project Alpha timeline targets Q2 launch.",
                score=0.8,
            )
        ]
    )
    graph = _FakeRetriever(
        [
            SourceSnippet(
                source_type="graph",
                source_id="Project Alpha->Data Platform Upgrade",
                text="Project Alpha depends on Data Platform Upgrade.",
                score=0.7,
            )
        ]
    )
    orchestration = build_orchestration_graph(
        document_retriever=document,
        graph_retriever=graph,
        seed_document_retriever=document,
        seed_graph_retriever=graph,
        allow_seeded_fallback=True,
        gemini_api_key=None,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_refinement_retrieval_limit=5,
    )

    result = await orchestration.ainvoke(
        create_initial_state("How does the timeline compare to graph dependencies?")
    )

    assert result["route_mode"].value == "both"
    assert isinstance(result["snippets"], list)
    assert any(
        event.get("event") == "fan_in_completed"
        for event in result.get("telemetry_events", [])
    )
    document_event = _event(result, "document_branch_completed")
    graph_event = _event(result, "graph_branch_completed")
    assert document_event.get("retriever_mode") == "real"
    assert graph_event.get("retriever_mode") == "real"
    assert document_event.get("fallback_used") is False
    assert graph_event.get("fallback_used") is False


@pytest.mark.asyncio
async def test_orchestration_graph_branch_failure_uses_seeded_fallback() -> None:
    document = _FakeRetriever(
        [
            SourceSnippet(
                source_type="document",
                source_id="doc#1",
                text="Project Alpha timeline targets Q2 launch.",
                score=0.8,
            )
        ]
    )
    graph_primary = _FakeRetriever([], should_raise=True)
    graph_seed = _FakeRetriever(
        [
            SourceSnippet(
                source_type="graph",
                source_id="fallback-graph#1",
                text="Fallback graph snippet.",
                score=0.6,
            )
        ]
    )
    orchestration = build_orchestration_graph(
        document_retriever=document,
        graph_retriever=graph_primary,
        seed_document_retriever=document,
        seed_graph_retriever=graph_seed,
        allow_seeded_fallback=True,
        gemini_api_key=None,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_refinement_retrieval_limit=5,
    )

    result = await orchestration.ainvoke(
        create_initial_state("Compare timeline dependencies in graph")
    )

    source_ids = {_source_id(snippet) for snippet in result["snippets"]}
    assert "doc#1" in source_ids
    assert "fallback-graph#1" in source_ids
    graph_event = _event(result, "graph_branch_completed")
    assert graph_event.get("retriever_mode") == "seeded_fallback"
    assert graph_event.get("fallback_used") is True
    assert graph_event.get("error_class") == "RuntimeError"


@pytest.mark.asyncio
async def test_orchestration_graph_branch_failure_without_fallback_keeps_other_branch() -> (
    None
):
    document = _FakeRetriever(
        [
            SourceSnippet(
                source_type="document",
                source_id="doc#1",
                text="Project Alpha timeline targets Q2 launch.",
                score=0.8,
            )
        ]
    )
    graph_primary = _FakeRetriever([], should_raise=True)
    empty_graph_seed = _FakeRetriever([])
    orchestration = build_orchestration_graph(
        document_retriever=document,
        graph_retriever=graph_primary,
        seed_document_retriever=document,
        seed_graph_retriever=empty_graph_seed,
        allow_seeded_fallback=False,
        gemini_api_key=None,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_refinement_retrieval_limit=5,
    )

    result = await orchestration.ainvoke(
        create_initial_state("Compare timeline dependencies in graph")
    )

    assert len(result["snippets"]) == 1
    assert _source_id(result["snippets"][0]) == "doc#1"
    graph_event = _event(result, "graph_branch_completed")
    assert graph_event.get("retriever_mode") == "error_no_fallback"
    assert graph_event.get("fallback_used") is False
    assert graph_event.get("error_class") == "RuntimeError"


def _source_id(snippet: object) -> str:
    if isinstance(snippet, dict):
        source_id = snippet.get("source_id")
        if isinstance(source_id, str):
            return source_id
        return ""
    source_id = getattr(snippet, "source_id", "")
    if isinstance(source_id, str):
        return source_id
    return ""


def _event(result: dict[str, object], event_name: str) -> dict[str, object]:
    events = result.get("telemetry_events")
    if not isinstance(events, list):
        return {}
    for event in events:
        if isinstance(event, dict) and event.get("event") == event_name:
            return event
    return {}


class _AdaptiveRetriever:
    def __init__(self) -> None:
        self.limits: list[int] = []

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        _ = question
        self.limits.append(limit)
        if limit <= 3:
            return [
                SourceSnippet(
                    source_type="document",
                    source_id="doc#low",
                    text="Low confidence snippet.",
                    score=0.2,
                )
            ]
        return [
            SourceSnippet(
                source_type="document",
                source_id="doc#high-1",
                text="High confidence snippet one.",
                score=0.95,
            ),
            SourceSnippet(
                source_type="document",
                source_id="doc#high-2",
                text="High confidence snippet two.",
                score=0.92,
            ),
        ]


@pytest.mark.asyncio
async def test_orchestration_graph_critic_refines_once_then_finalizes() -> None:
    adaptive = _AdaptiveRetriever()
    empty_graph = _FakeRetriever([])
    orchestration = build_orchestration_graph(
        document_retriever=adaptive,
        graph_retriever=empty_graph,
        seed_document_retriever=adaptive,
        seed_graph_retriever=empty_graph,
        allow_seeded_fallback=True,
        gemini_api_key=None,
        phase4_enable_critic=True,
        phase4_confidence_threshold=0.62,
        phase4_min_snippets=2,
        phase4_max_refinement_rounds=1,
        phase4_refinement_retrieval_limit=5,
    )

    result = await orchestration.ainvoke(
        create_initial_state("Provide schedule evidence from documents.")
    )

    assert adaptive.limits == [3, 5]
    assert result.get("critic_needs_refinement") is False
    assert result.get("refinement_attempt") == 1
    assert _event(result, "refinement_started")
