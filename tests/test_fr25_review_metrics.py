import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "fr25_review", Path(__file__).resolve().parents[1] / "scripts/retest_fr25_lifecycle_review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_research_metric_includes_first_loss_and_actual_fill_cost():
    # Dropping the initial cash anchor would falsely turn this loss into +10%.
    result = review.metrics([100, 90, 99], ["2022-12-30", "2023-01-03", "2023-01-04"],
                            [dict(date="2023-01-03", quantity=2, price="10", fee="1")])
    assert result["cagr"] < 0
    assert result["max_drawdown"] == pytest.approx(-.1)
    assert result["annual_turnover"] == pytest.approx(.2 / (2 / 252))
    assert result["annual_cost_bps"] == pytest.approx(.01 / (2 / 252) * 10000)


def test_sortino_uses_downside_moment_over_all_sessions():
    result = review.metrics([100, 110, 99, 100.98],
                            ["anchor", "one", "two", "three"], [])
    expected = (.02 / 3 * 252) / (np.sqrt(.01 / 3) * np.sqrt(252))
    assert result["sortino"] == pytest.approx(expected)
