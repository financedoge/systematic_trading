import json
from datetime import date

import pytest

from systematic_trading.backtest.comparison import (
    build_decision_diagnostics,
    build_market_data_audit,
    build_signal_diagnostics,
    build_signal_forecast_diagnostics,
    compare_backtests,
    write_comparison_artifacts,
)
from systematic_trading.research import (
    build_model_structure_comparison,
    current_sota_definition,
    strategy_definition_from_overlay,
)
from systematic_trading.signals import TimeSeriesMomentumOverlay


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


def test_comparison_artifacts_include_model_structure_diagrams(tmp_path) -> None:
    comparison = compare_backtests(
        baseline={
            "nav_series": [
                {"trade_date": "2023-01-03", "nav_cnh": "100"},
                {"trade_date": "2023-01-04", "nav_cnh": "105"},
            ]
        },
        candidate={
            "nav_series": [
                {"trade_date": "2023-01-03", "nav_cnh": "100"},
                {"trade_date": "2023-01-04", "nav_cnh": "106"},
            ]
        },
        split_date=date(2023, 1, 1),
        baseline_name=current_sota_definition().name,
        candidate_name="Research candidate",
    )
    model_structure = build_model_structure_comparison(
        baseline=current_sota_definition(),
        candidate=strategy_definition_from_overlay(TimeSeriesMomentumOverlay(lookback_bars=126)),
    )

    artifacts = write_comparison_artifacts(
        comparison=comparison,
        output_dir=tmp_path,
        stem="comparison",
        model_structure=model_structure,
    )

    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    markdown = artifacts.markdown_path.read_text(encoding="utf-8")
    assert payload["modelStructure"]["baseline"]["definition"]["state"] == "sota"
    assert "## Model Structure" in markdown
    assert "```mermaid" in markdown
    assert "SOTA: risk parity + relative momentum 20/60d 20% tilt" in markdown


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
    assert signal["decisions"][0]["outcome"] == "false_exit"


def test_build_decision_diagnostics_counts_false_exits_and_keeps() -> None:
    diagnostics = {
        "periods": [
            {
                "period": "2023-01-03 to 2023-02-01",
                "start": "2023-01-03",
                "end": "2023-02-01",
                "sample": "out_of_sample",
                "signals": [
                    {
                        "decisions": [
                            {
                                "symbol": "SPY",
                                "action": "cut",
                                "baselineWeight": 0.5,
                                "candidateWeight": 0.0,
                                "weightDelta": -0.5,
                                "active": True,
                                "assetReturn": 0.1,
                                "estimatedContribution": -0.05,
                                "outcome": "false_exit",
                            },
                            {
                                "symbol": "VGK",
                                "action": "keep",
                                "baselineWeight": 0.5,
                                "candidateWeight": 0.5,
                                "weightDelta": 0.0,
                                "active": False,
                                "assetReturn": -0.05,
                                "estimatedContribution": 0.0,
                                "outcome": "false_keep",
                            },
                        ]
                    }
                ],
            }
        ]
    }

    report = build_decision_diagnostics(diagnostics)

    assert report["summary"]["out_of_sample"]["falseExits"] == 1
    assert report["summary"]["out_of_sample"]["falseKeeps"] == 1
    assert report["summary"]["out_of_sample"]["activeHitRate"] == pytest.approx(0)
    assert report["bySymbol"][0]["symbol"] == "SPY"


def test_build_market_data_audit_flags_missing_dates_and_unadjusted_prices() -> None:
    audit = build_market_data_audit(
        prices_by_symbol={
            "SPY": {
                date(2023, 1, 3): 100,
                date(2023, 1, 4): 100,
                date(2023, 1, 5): 100,
            },
            "VGK": {date(2023, 1, 3): 50},
        },
        required_dates=[date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)],
        source_name="test-store",
        adjusted_prices=False,
    )

    by_symbol = {item["symbol"]: item for item in audit["symbols"]}
    assert by_symbol["SPY"]["stalePriceRuns"][0]["observations"] == 3
    assert by_symbol["VGK"]["missingRequiredDates"] == 2
    assert any("not validated adjusted" in warning for warning in audit["warnings"])


def test_build_signal_forecast_diagnostics_scores_forward_returns() -> None:
    prices = {
        "SPY": {
            date(2023, 1, 2): 90,
            date(2023, 1, 3): 100,
            date(2023, 2, 1): 110,
            date(2023, 3, 1): 120,
        },
        "VGK": {
            date(2023, 1, 2): 100,
            date(2023, 1, 3): 90,
            date(2023, 2, 1): 80,
            date(2023, 3, 1): 70,
        },
    }

    diagnostics = build_signal_forecast_diagnostics(
        prices_by_symbol=prices,
        rebalance_dates=[date(2023, 1, 3), date(2023, 2, 1), date(2023, 3, 1)],
        split_date=date(2023, 2, 1),
        lookback_bars=1,
        threshold=0,
    )

    assert diagnostics["summary"]["full"]["observations"] == 2
    assert diagnostics["summary"]["full"]["positiveSignals"] == 1
    assert diagnostics["summary"]["full"]["negativeSignals"] == 1
    assert diagnostics["summary"]["full"]["directionalAccuracy"] == pytest.approx(1)
