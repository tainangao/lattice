from lattice.prototype.data_health import _compute_overall_ok


def test_compute_overall_ok_returns_true_when_one_source_ok() -> None:
    result = _compute_overall_ok(
        checks=[{"status": "ok"}, {"status": "error"}],
        allow_seeded_fallback=True,
    )
    assert result is True


def test_compute_overall_ok_returns_false_without_fallback_on_error() -> None:
    result = _compute_overall_ok(
        checks=[{"status": "error"}, {"status": "skipped"}],
        allow_seeded_fallback=False,
    )
    assert result is False
