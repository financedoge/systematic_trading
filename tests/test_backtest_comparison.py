from datetime import date

import pytest

from systematic_trading.backtest.comparison import build_signal_diagnostics, compare_backtests


def test_compare_backtests_splits_candidate_against_baseline() -> None:
    baseline = {
        "nav_series": [
            {"trade_date": "2022-12-30", "nav_cnh": "100"},
            {"trade_date": "2023-01-03", "nav_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "110"},
        ]
    }
    candidate = {
        "nav_series": [
            {"trade_date": "2022-12-30", "nav_cnh": "100"},
            {"trade_date": "2023-01-03", "nav_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "120"},
        ]
    }

    comparison = compare_backtests(
        baseline=baseline,
        candidate=candidate,
        split_date=date(2023, 1, 1),
    )

    assert comparison["observations"]["in_sample"] == 1
    assert comparison["observations"]["out_of_sample"] == 2
    assert comparison["metrics"]["out_of_sample"]["delta"]["return"] == pytest.approx(0.1)


def test_build_signal_diagnostics_attributes_weight_changes() -> None:
    baseline = {
        "nav_series": [
            {"trade_date": "2022-12-30", "nav_cnh": "100"},
            {"trade_date": "2023-01-03", "nav_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "110"},
        ],
        "proposals": [
            {"as_of": "2022-12-30", "targets": [{"symbol": "SPY", "target_weight": "1.0"}]},
        ],
    }
    candidate = {
        "nav_series": [
            {"trade_date": "2022-12-30", "nav_cnh": "100"},
            {"trade_date": "2023-01-03", "nav_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "105"},
        ],
        "proposals": [
            {"as_of": "2022-12-30", "targets": [{"symbol": "SPY", "target_weight": "0.5"}]},
        ],
    }

    diagnostics = build_signal_diagnostics(
        baseline=baseline,
        candidate=candidate,
        prices_by_symbol={
            "SPY": {
                date(2022, 12, 30): 100,
                date(2023, 1, 4): 110,
            }
        },
        split_date=date(2023, 1, 1),
        signal_name="test-signal",
    )

    period = diagnostics["periods"][0]
    signal = period["signals"][0]
    assert signal["realizedDelta"] == pytest.approx(-0.05)
    assert signal["estimatedContribution"] == pytest.approx(-0.05)
    assert signal["topNegative"][0]["symbol"] == "SPY"
