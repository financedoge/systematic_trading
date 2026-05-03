from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.backtest.comparison import (
    build_signal_diagnostics,
    compare_backtests,
    write_comparison_artifacts,
)
from systematic_trading.backtest.reporting import write_backtest_report
from systematic_trading.backtest.stored import StoredRiskParityBacktestConfig, run_stored_risk_parity_backtest
from systematic_trading.config import AppSettings
from systematic_trading.research import GLOBAL_ETF_UNIVERSE
from systematic_trading.signals import TimeSeriesMomentumOverlay
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare baseline stored risk parity with a 12-month trend-filter overlay."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--split-date", default="2023-01-01")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests/trend_signal")
    parser.add_argument("--trend-lookback-bars", type=int, default=252)
    parser.add_argument("--trend-threshold", default="0")
    parser.add_argument(
        "--reallocate-survivors",
        action="store_true",
        help="If set, inactive assets are reallocated across positive-trend assets instead of left in cash.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    store = SQLiteStore(database_path)
    store.initialize()

    start_date, end_date = _date_range_from_store(store, args.start_date, args.end_date)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_config = StoredRiskParityBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=Decimal(args.initial_cash_cnh),
        sleeve_name="baseline-risk-parity",
    )
    overlay = TimeSeriesMomentumOverlay(
        lookback_bars=args.trend_lookback_bars,
        threshold=Decimal(args.trend_threshold),
        reallocate_survivors=args.reallocate_survivors,
    )
    candidate_config = baseline_config.model_copy(
        update={"sleeve_name": f"risk-parity+{overlay.name}"}
    )

    baseline = run_stored_risk_parity_backtest(
        store=store,
        instruments=GLOBAL_ETF_UNIVERSE,
        config=baseline_config,
    )
    candidate = run_stored_risk_parity_backtest(
        store=store,
        instruments=GLOBAL_ETF_UNIVERSE,
        config=candidate_config,
        target_overlays=[overlay],
    )

    baseline_path = output_dir / "baseline_risk_parity.json"
    candidate_path = output_dir / f"{overlay.name}.json"
    baseline_payload = baseline.model_dump(mode="json")
    candidate_payload = candidate.model_dump(mode="json")
    baseline_path.write_text(json.dumps(baseline_payload, indent=2), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate_payload, indent=2), encoding="utf-8")

    comparison = compare_backtests(
        baseline=baseline_payload,
        candidate=candidate_payload,
        split_date=date.fromisoformat(args.split_date),
        baseline_name="Baseline risk parity",
        candidate_name=f"Risk parity + {overlay.name}",
    )
    signal_diagnostics = build_signal_diagnostics(
        baseline=baseline_payload,
        candidate=candidate_payload,
        prices_by_symbol=_prices_by_symbol(store),
        split_date=date.fromisoformat(args.split_date),
        signal_name=overlay.name,
    )
    artifacts = write_comparison_artifacts(
        comparison=comparison,
        output_dir=output_dir,
        stem="comparison",
        signal_diagnostics=signal_diagnostics,
    )
    report = write_backtest_report(
        result_path=candidate_path,
        output_path=output_dir / f"{overlay.name}.html",
        database_path=database_path,
        benchmark_nav_series=baseline_payload["nav_series"],
        benchmark_name="Baseline risk parity",
        signal_diagnostics=signal_diagnostics,
    )

    print(baseline_path)
    print(candidate_path)
    print(artifacts.markdown_path)
    print(artifacts.json_path)
    print(report.output_path)


def _date_range_from_store(
    store: SQLiteStore,
    start_date_arg: str | None,
    end_date_arg: str | None,
) -> tuple[date, date]:
    first_dates: list[date] = []
    last_dates: list[date] = []
    for symbol in GLOBAL_ETF_UNIVERSE:
        bars = store.list_price_bars(symbol)
        if not bars:
            raise ValueError(f"No stored bars found for {symbol}. Run scripts/run_first_backtest.py first.")
        first_dates.append(bars[0].trade_date)
        last_dates.append(bars[-1].trade_date)

    start_date = date.fromisoformat(start_date_arg) if start_date_arg else max(first_dates)
    end_date = date.fromisoformat(end_date_arg) if end_date_arg else min(last_dates)
    if end_date <= start_date:
        raise ValueError(f"Invalid backtest range: {start_date} to {end_date}.")
    return start_date, end_date


def _prices_by_symbol(store: SQLiteStore) -> dict[str, dict[date, float]]:
    return {
        symbol: {bar.trade_date: float(bar.close) for bar in store.list_price_bars(symbol)}
        for symbol in GLOBAL_ETF_UNIVERSE
    }


if __name__ == "__main__":
    main()
