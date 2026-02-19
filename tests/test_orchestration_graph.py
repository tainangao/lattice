import pytest

from lattice.prototype.orchestration import (
    build_orchestration_graph,
    create_initial_state,
)
from lattice.prototype.models import SourceSnippet


class _FakeRetriever:
    def __init__(self, snippets: list[SourceSnippet]) -> None:
        self._snippets = snippets

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        _ = question
        _ = limit
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
