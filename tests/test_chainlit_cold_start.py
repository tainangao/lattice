from lattice.chainlit_app import (
    DEFAULT_PUBLIC_DEMO_QUERY_LIMIT,
    _is_demo_quota_exhausted,
    _remaining_demo_queries,
    _resolve_demo_queries_used,
    _resolve_demo_query_limit,
)


def test_resolve_demo_query_limit_defaults_for_missing_or_invalid_values() -> None:
    assert _resolve_demo_query_limit(None) == DEFAULT_PUBLIC_DEMO_QUERY_LIMIT
    assert _resolve_demo_query_limit("invalid") == DEFAULT_PUBLIC_DEMO_QUERY_LIMIT


def test_resolve_demo_query_limit_never_returns_negative_values() -> None:
    assert _resolve_demo_query_limit("-5") == 0
    assert _resolve_demo_query_limit("4") == 4


def test_resolve_demo_queries_used_accepts_only_non_negative_int() -> None:
    assert _resolve_demo_queries_used(2) == 2
    assert _resolve_demo_queries_used(-1) == 0
    assert _resolve_demo_queries_used("2") == 0


def test_is_demo_quota_exhausted_only_for_anonymous_sessions() -> None:
    assert _is_demo_quota_exhausted(
        has_session_key=False,
        used_count=3,
        demo_limit=3,
    )
    assert not _is_demo_quota_exhausted(
        has_session_key=True,
        used_count=3,
        demo_limit=3,
    )


def test_remaining_demo_queries_is_bounded_at_zero() -> None:
    assert _remaining_demo_queries(demo_limit=3, used_count=1) == 2
    assert _remaining_demo_queries(demo_limit=3, used_count=5) == 0
