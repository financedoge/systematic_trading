from __future__ import annotations

import pytest

from systematic_trading.backtest.stability import (
    percentile_scores,
    retention_band_distance,
    retention_band_pass,
    retention_closeness_scores,
    sharpe_retention_ratio,
)


def test_sharpe_retention_ratio_requires_positive_in_sample_sharpe() -> None:
    assert sharpe_retention_ratio(1.0, 0.85) == pytest.approx(0.85)
    assert sharpe_retention_ratio(0.0, 1.0) is None
    assert sharpe_retention_ratio(-0.5, -0.4) is None
    assert sharpe_retention_ratio(None, 1.0) is None


def test_retention_band_distance_scores_target_band_as_best() -> None:
    assert retention_band_pass(0.85)
    assert retention_band_distance(0.85) == pytest.approx(0.0)
    assert retention_band_distance(0.70) == pytest.approx(0.10)
    assert retention_band_distance(1.10) == pytest.approx(0.20)


def test_retention_closeness_percentile_rewards_smaller_distance() -> None:
    rows = [
        {"key": "too_high", "distance": 1.0, "sharpe": 3.0},
        {"key": "target", "distance": 0.0, "sharpe": 1.0},
        {"key": "near", "distance": 0.1, "sharpe": 2.0},
    ]

    assert retention_closeness_scores(rows, distance_key="distance")["target"] == pytest.approx(1.0)
    assert retention_closeness_scores(rows, distance_key="distance")["too_high"] == pytest.approx(0.0)
    assert percentile_scores(rows, "sharpe")["too_high"] == pytest.approx(1.0)
