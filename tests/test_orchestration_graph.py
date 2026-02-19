from lattice.prototype.orchestration import (
    build_orchestration_graph,
    create_initial_state,
)


def test_orchestration_graph_direct_path_sets_direct_mode() -> None:
    graph = build_orchestration_graph()

    result = graph.invoke(create_initial_state("hello"))

    assert result["route_mode"].value == "direct"
    assert isinstance(result["answer"], str)
    assert result["telemetry_events"]


def test_orchestration_graph_both_path_runs_fan_in() -> None:
    graph = build_orchestration_graph()

    result = graph.invoke(
        create_initial_state("How does the timeline compare to graph dependencies?")
    )

    assert result["route_mode"].value == "both"
    assert isinstance(result["snippets"], list)
    assert any(
        event.get("event") == "fan_in_completed"
        for event in result.get("telemetry_events", [])
    )
