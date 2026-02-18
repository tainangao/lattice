from lattice.prototype.retrievers.graph_retriever import (
    _query_tokens,
    _result_to_snippet,
)


def test_query_tokens_filters_common_words() -> None:
    tokens = _query_tokens("What TV show is about mystery and squid game?")

    assert "what" not in tokens
    assert "show" not in tokens
    assert "squid" in tokens
    assert "game" in tokens


def test_result_to_snippet_builds_graph_source_snippet() -> None:
    snippet = _result_to_snippet(
        {
            "show_id": "s34",
            "title": "Squid Game",
            "title_type": "TV Show",
            "release_year": 2021,
            "people": ["Lee Jung-jae"],
            "genres": ["TV Thrillers"],
            "title_hits": ["squid", "game"],
            "person_hits": ["lee"],
            "genre_hits": ["thrillers"],
            "score": 0.9,
        }
    )

    assert snippet.source_type == "graph"
    assert snippet.source_id == "Title:s34"
    assert "Squid Game" in snippet.text
    assert snippet.score == 0.9
