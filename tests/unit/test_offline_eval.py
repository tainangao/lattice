from __future__ import annotations

from lattice.app.evaluation.suite import run_offline_eval
from main import app


def test_offline_eval_suite_is_green() -> None:
    report = run_offline_eval(app)
    assert report["passed"] is True
