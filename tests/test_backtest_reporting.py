from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from systematic_trading.backtest.reporting import build_backtest_report_data
from systematic_trading.domain import Currency, FXRate, PriceBar
from systematic_trading.storage.sqlite import SQLiteStore


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
        split_date=date(2023, 1, 4),
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
    assert report["splitDate"] == "2023-01-04"
    assert report["benchmarkOptions"] == [
        {"id": "primary", "name": "Baseline"},
        {"id": "msci_world", "name": "MSCI World proxy"},
    ]
    assert report["summariesByBenchmark"]["primary"]["alpha"] == pytest.approx(0.05)
    assert report["summariesByBenchmark"]["msci_world"]["alpha"] == pytest.approx(0.08)


def test_report_starts_symbol_benchmark_on_first_available_price(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "market.db")
    store.initialize()
    for trade_date, close in [
        (date(2023, 1, 4), Decimal("100")),
        (date(2023, 1, 5), Decimal("105")),
    ]:
        store.upsert_price_bar(
            "URTH",
            PriceBar(
                trade_date=trade_date,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=100,
            ),
        )
    for rate_date in [date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)]:
        store.upsert_fx_rate(
            FXRate(
                rate_date=rate_date,
                base_currency=Currency.USD,
                quote_currency=Currency.CNH,
                rate=Decimal("1"),
            )
        )

    result = {
        "nav_series": [
            {"trade_date": "2023-01-03", "nav_cnh": "100", "cash_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "105", "cash_cnh": "105"},
            {"trade_date": "2023-01-05", "nav_cnh": "110", "cash_cnh": "110"},
        ],
        "proposals": [],
        "final_snapshot": {"positions": []},
    }

    report, warnings = build_backtest_report_data(
        result=result,
        result_path=Path("candidate.json"),
        database_path=store.database_path,
        benchmark_nav_series=[
            {"trade_date": "2023-01-03", "nav_cnh": "100"},
            {"trade_date": "2023-01-04", "nav_cnh": "105"},
            {"trade_date": "2023-01-05", "nav_cnh": "110"},
        ],
        benchmark_name="Baseline",
        extra_benchmarks=[
            {
                "id": "msci_world",
                "name": "MSCI World proxy",
                "symbol": "URTH",
            }
        ],
    )

    assert warnings == ["MSCI World proxy starts on 2023-01-04 because no earlier benchmark prices were found."]
    msci_chart = [point["benchmarks"]["msci_world"] for point in report["chart"]]
    assert msci_chart[0]["nav"] is None
    assert msci_chart[0]["index"] is None
    assert msci_chart[1]["index"] == pytest.approx(100)
    assert msci_chart[2]["index"] == pytest.approx(105)

    summary = report["summariesByBenchmark"]["msci_world"]
    assert summary["benchmarkStart"] == "2023-01-04"
    assert summary["benchmarkReturn"] == pytest.approx(0.05)
    assert summary["strategyComparisonReturn"] == pytest.approx((110 / 105) - 1)
    assert summary["alpha"] == pytest.approx(((110 / 105) - 1) - 0.05)

    yearly = report["metricsByBenchmark"]["msci_world"]["yearly"][0]
    assert yearly["benchmarkReturn"] == pytest.approx(0.05)
    assert yearly["alpha"] == pytest.approx(((110 / 105) - 1) - 0.05)
