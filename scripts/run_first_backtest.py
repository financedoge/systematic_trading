from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from systematic_trading.backtest.stored import StoredRiskParityBacktestConfig, run_stored_risk_parity_backtest
from systematic_trading.backtest.reporting import write_backtest_report
from systematic_trading.config import AppSettings
from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate
from systematic_trading.research import GLOBAL_ETF_UNIVERSE
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default="2026-04-30")
    parser.add_argument("--initial-cash-cnh", default="1000000")
    parser.add_argument("--output-dir", default="var/backtests")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    settings = AppSettings()
    store = SQLiteStore(settings.database_path)
    store.initialize()
    provider = YahooChartProvider()

    for instrument in GLOBAL_ETF_UNIVERSE.values():
        store.upsert_instrument(instrument)
        for bar in provider.fetch_daily_bars(instrument.symbol, start_date, end_date):
            store.upsert_price_bar(instrument.symbol, bar)

    for bar in provider.fetch_daily_bars("CNY=X", start_date, end_date):
        store.upsert_fx_rate(
            FXRate(
                rate_date=bar.trade_date,
                base_currency=Currency.USD,
                quote_currency=Currency.CNH,
                rate=bar.close,
            )
        )

    config = StoredRiskParityBacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_cash_cnh=Decimal(args.initial_cash_cnh),
    )
    result = run_stored_risk_parity_backtest(store=store, instruments=GLOBAL_ETF_UNIVERSE, config=config)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "first_real_backtest.json"
    summary_path = output_dir / "first_real_backtest.md"
    report_path = output_dir / "first_real_backtest.html"

    result_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
    summary_path.write_text(_markdown_summary(result, config), encoding="utf-8")
    write_backtest_report(result_path=result_path, output_path=report_path, database_path=settings.database_path)
    print(summary_path)
    print(result_path)
    print(report_path)


def _markdown_summary(result, config: StoredRiskParityBacktestConfig) -> str:
    first = result.nav_series[0]
    last = result.nav_series[-1]
    total_return = (last.nav_cnh / first.nav_cnh) - Decimal("1")
    years = Decimal((last.trade_date - first.trade_date).days) / Decimal("365.25")
    annualized = (last.nav_cnh / first.nav_cnh) ** (Decimal("1") / years) - Decimal("1")
    max_drawdown = _max_drawdown([point.nav_cnh for point in result.nav_series])

    lines = [
        "# First Real Backtest",
        "",
        "Source: Yahoo Finance chart API. ETF prices are unadjusted daily OHLC closes; USD/CNH reporting uses Yahoo `CNY=X` as the available USD/CNY proxy.",
        "",
        f"- Period: {first.trade_date} to {last.trade_date}",
        f"- Initial NAV: CNH {first.nav_cnh:,.2f}",
        f"- Final NAV: CNH {last.nav_cnh:,.2f}",
        f"- Total return: {total_return:.2%}",
        f"- Annualized return: {annualized:.2%}",
        f"- Max drawdown: {max_drawdown:.2%}",
        f"- Rebalance count: {len(result.proposals)}",
        f"- Lookback bars: {config.lookback_bars}",
        "",
        "## Final Exposures",
        "",
    ]
    for country, value in result.final_snapshot.country_exposure_cnh.items():
        lines.append(f"- {country}: CNH {value:,.2f}")
    lines.extend(["", "## Last Rebalance", ""])
    last_proposal = result.proposals[-1]
    lines.append(f"- Date: {last_proposal.as_of}")
    lines.append(f"- Summary: {last_proposal.summary}")
    for target in last_proposal.targets:
        lines.append(f"- {target.symbol}: {target.target_weight:.2%}")
    lines.append("")
    return "\n".join(lines)


def _max_drawdown(nav_values: list[Decimal]) -> Decimal:
    peak = nav_values[0]
    worst = Decimal("0")
    for nav in nav_values:
        peak = max(peak, nav)
        drawdown = (nav / peak) - Decimal("1")
        worst = min(worst, drawdown)
    return worst


if __name__ == "__main__":
    main()
