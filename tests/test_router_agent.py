from lattice.prototype.models import RetrievalMode
from lattice.prototype.router_agent import route_question


def test_route_question_returns_direct_for_greeting() -> None:
    decision = route_question("Hello there")
    assert decision.mode == RetrievalMode.DIRECT


def test_route_question_returns_both_for_multi_source_query() -> None:
    decision = route_question("Compare timeline.pdf dependencies in the graph")
    assert decision.mode == RetrievalMode.BOTH


def test_route_question_returns_graph_for_netflix_graph_query() -> None:
    decision = route_question("Which titles involve Lee Jung-jae and TV Thrillers?")
    assert decision.mode == RetrievalMode.GRAPH
