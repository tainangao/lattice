from lattice.prototype.models import RetrievalMode
from lattice.prototype.router_agent import route_question


def test_orchestration_routing_prefers_both_for_mixed_intent_query() -> None:
    decision = route_question("Compare timeline document dependencies in graph")

    assert decision.mode == RetrievalMode.BOTH


def test_orchestration_routing_returns_document_for_document_only_query() -> None:
    decision = route_question("Summarize the uploaded policy document")

    assert decision.mode == RetrievalMode.DOCUMENT


def test_orchestration_routing_returns_graph_for_graph_only_query() -> None:
    decision = route_question("Show dependency relationships by owner")

    assert decision.mode == RetrievalMode.GRAPH


def test_orchestration_routing_defaults_to_both_when_unclear() -> None:
    decision = route_question("Help me understand this")

    assert decision.mode == RetrievalMode.BOTH


def test_orchestration_routing_compare_graph_only_stays_graph() -> None:
    decision = route_question("Compare dependency and owner relationships")

    assert decision.mode == RetrievalMode.GRAPH


def test_orchestration_routing_compare_document_only_stays_document() -> None:
    decision = route_question("Compare sections in this policy document")

    assert decision.mode == RetrievalMode.DOCUMENT
