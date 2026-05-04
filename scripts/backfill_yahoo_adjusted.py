from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate
from systematic_trading.research import BENCHMARK_INSTRUMENTS, GLOBAL_ETF_UNIVERSE
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill adjusted Yahoo daily bars and USD/CNH FX into SQLite.")
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--include-benchmarks", action="store_true")
    parser.add_argument("--skip-fx", action="store_true")
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    store = SQLiteStore(database_path)
    store.initialize()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else _default_end_date(store)
    instruments = dict(GLOBAL_ETF_UNIVERSE)
    if args.include_benchmarks:
        instruments.update(BENCHMARK_INSTRUMENTS)
    symbols = _symbols(args.symbols, instruments)

    provider = YahooChartProvider(adjust_prices=True)
    print(f"database={database_path}")
    print(f"source=yahoo adjusted chart bars")
    print(f"range={start_date} to {end_date}")

    for symbol in symbols:
        instrument = instruments.get(symbol)
        if instrument is not None:
            store.upsert_instrument(instrument)
        bars = provider.fetch_daily_bars(symbol, start_date, end_date)
        if not bars:
            raise ValueError(f"Yahoo returned no adjusted bars for {symbol}.")
        for bar in bars:
            store.upsert_price_bar(symbol, bar)
        print(f"{symbol}: upserted {len(bars)} adjusted bars, {bars[0].trade_date} to {bars[-1].trade_date}")

    if not args.skip_fx:
        fx_provider = YahooChartProvider()
        fx_bars = fx_provider.fetch_daily_bars("CNY=X", start_date, end_date)
        for bar in fx_bars:
            store.upsert_fx_rate(
                FXRate(
                    rate_date=bar.trade_date,
                    base_currency=Currency.USD,
                    quote_currency=Currency.CNH,
                    rate=bar.close,
                )
            )
        print(f"USD/CNH proxy CNY=X: upserted {len(fx_bars)} rates")


def _default_end_date(store: SQLiteStore) -> date:
    last_dates: list[date] = []
    for symbol in GLOBAL_ETF_UNIVERSE:
        bars = store.list_price_bars(symbol)
        if bars:
            last_dates.append(bars[-1].trade_date)
    if last_dates:
        return min(last_dates)
    return date.today()


def _symbols(value: str | None, instruments: dict[str, object]) -> list[str]:
    if value is None:
        return sorted(instruments)
    symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    if not symbols:
        raise ValueError("--symbols did not contain any symbols.")
    return symbols


if __name__ == "__main__":
    main()
