from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.data.tushare import TushareUsDailyProvider
from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate
from systematic_trading.research import BENCHMARK_INSTRUMENTS, GLOBAL_ETF_UNIVERSE
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill US adjusted daily bars from Tushare and USD/CNH FX from Yahoo CNY=X."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to the global ETF universe.")
    parser.add_argument("--token-path", default=None)
    parser.add_argument("--include-benchmarks", action="store_true")
    parser.add_argument("--skip-fx", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=65)
    parser.add_argument("--retry-sleep-seconds", type=float, default=65)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--force", action="store_true", help="Fetch symbols even when the requested date range is already covered.")
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    token_path = Path(args.token_path) if args.token_path else settings.tushare_token_path
    store = SQLiteStore(database_path)
    store.initialize()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else _default_end_date(store)
    instruments = dict(GLOBAL_ETF_UNIVERSE)
    if args.include_benchmarks:
        instruments.update(BENCHMARK_INSTRUMENTS)
    symbols = _symbols(args.symbols, instruments)

    provider = TushareUsDailyProvider(token_path=token_path, adjusted=True)
    if not provider.manifest.configured:
        raise ValueError(f"Tushare token was not found at {token_path}.")

    print(f"database={database_path}")
    print(f"source=tushare us_daily_adj")
    print(f"range={start_date} to {end_date}")

    for symbol in symbols:
        instrument = instruments.get(symbol)
        if instrument is not None:
            store.upsert_instrument(instrument)
        if not args.force and _range_is_covered(store, symbol, start_date, end_date):
            print(f"{symbol}: skipped; requested range is already covered")
            continue
        bars = _fetch_with_retries(
            provider=provider,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            max_retries=args.max_retries,
            retry_sleep_seconds=args.retry_sleep_seconds,
        )
        if not bars:
            raise ValueError(f"Tushare returned no adjusted US daily bars for {symbol}.")
        for bar in bars:
            store.upsert_price_bar(symbol, bar)
        print(f"{symbol}: upserted {len(bars)} adjusted bars, {bars[0].trade_date} to {bars[-1].trade_date}")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

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


def _range_is_covered(store: SQLiteStore, symbol: str, start_date: date, end_date: date) -> bool:
    bars = store.list_price_bars(symbol, start_date=start_date, end_date=end_date)
    if not bars:
        return False
    return 0 <= (bars[0].trade_date - start_date).days <= 7 and bars[-1].trade_date >= end_date


def _fetch_with_retries(
    *,
    provider: TushareUsDailyProvider,
    symbol: str,
    start_date: date,
    end_date: date,
    max_retries: int,
    retry_sleep_seconds: float,
):
    attempts = 0
    while True:
        try:
            return provider.fetch_daily_bars([symbol], start_date, end_date).get(symbol, [])
        except Exception as exc:
            attempts += 1
            if attempts > max_retries or not _looks_like_rate_limit(exc):
                raise
            print(f"{symbol}: rate-limited; sleeping {retry_sleep_seconds:.0f}s before retry {attempts}/{max_retries}")
            time.sleep(retry_sleep_seconds)


def _looks_like_rate_limit(exc: Exception) -> bool:
    message = str(exc).lower()
    return "频率" in message or "rate" in message or "frequency" in message


if __name__ == "__main__":
    main()
