from pathlib import Path

import pytest

from systematic_trading.backtest.reporting import build_backtest_report_data


def test_backtest_report_keeps_extra_benchmark_choices() -> None:
    result = {
        "nav_series": [
            {"trade_date": "2023-01-03", "nav_cnh": "100", "cash_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "110", "cash_cnh": "110"},
        ],
        "proposals": [],
        "final_snapshot": {"positions": []},
    }

    report, warnings = build_backtest_report_data(
        result=result,
        result_path=Path("candidate.json"),
        benchmark_nav_series=[
            {"trade_date": "2023-01-03", "nav_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "105"},
        ],
        benchmark_name="Baseline",
        extra_benchmarks=[
            {
                "id": "msci_world",
                "name": "MSCI World proxy",
                "nav_series": [
                    {"trade_date": "2023-01-03", "nav_cnh": "100"},
                    {"trade_date": "2023-01-04", "nav_cnh": "102"},
                ],
            }
        ],
    )

    assert warnings == []
    assert report["benchmarkOptions"] == [
        {"id": "primary", "name": "Baseline"},
        {"id": "msci_world", "name": "MSCI World proxy"},
    ]
    assert report["summariesByBenchmark"]["primary"]["alpha"] == pytest.approx(0.05)
    assert report["summariesByBenchmark"]["msci_world"]["alpha"] == pytest.approx(0.08)
