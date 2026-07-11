from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.data.ib import IbHistoricalDailyBarProvider
from systematic_trading.data.tushare import TushareUsDailyProvider
from systematic_trading.data.yahoo import YahooChartProvider
from systematic_trading.domain.market import PriceBar
from systematic_trading.market_data import ClickHouseMarketDataClient, backfill_clickhouse_daily_bars
from systematic_trading.research import BENCHMARK_INSTRUMENTS, MULTI_ASSET_ETF_UNIVERSE


class TushareSingleSymbolProvider:
    def __init__(self, provider: TushareUsDailyProvider) -> None:
        self.provider = provider

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        return self.provider.fetch_daily_bars([symbol], start_date, end_date).get(symbol, [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill ClickHouse daily market-data bars directly from provider data.")
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols. Defaults to symbols already present in ClickHouse.")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--lookback-days", type=int, default=10)
    parser.add_argument("--provider", choices=["yahoo", "ib", "tushare"], default="yahoo")
    parser.add_argument("--fallback-provider", choices=["none", "yahoo", "ib", "tushare"], default="ib")
    parser.add_argument("--clickhouse-url", default=None)
    parser.add_argument("--clickhouse-database", default=None)
    parser.add_argument("--clickhouse-user", default=None)
    parser.add_argument("--clickhouse-password", default=None)
    parser.add_argument("--source-priority", type=int, default=None)
    parser.add_argument("--fallback-source-priority", type=int, default=None)
    parser.add_argument("--adjustment", default="provider_default")
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args(argv)

    if args.lookback_days < 0:
        raise SystemExit("--lookback-days must be non-negative")
    if args.max_symbols is not None and args.max_symbols < 1:
        raise SystemExit("--max-symbols must be positive")

    settings = AppSettings()
    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else end_date - timedelta(days=args.lookback_days)
    client = ClickHouseMarketDataClient(
        args.clickhouse_url or settings.clickhouse_http_url,
        database=args.clickhouse_database or settings.clickhouse_database,
        user=args.clickhouse_user or settings.clickhouse_user,
        password=args.clickhouse_password or os.getenv("ST_CLICKHOUSE_PASSWORD", settings.clickhouse_password),
    )
    client.ensure_daily_bars_table()
    symbols = _resolve_symbols(args.symbols, client)
    if args.max_symbols is not None:
        symbols = symbols[: args.max_symbols]

    provider, source_name, source_priority = _provider(
        args.provider,
        settings,
        source_priority=args.source_priority,
    )
    fallback_provider = None
    fallback_source_name = None
    fallback_source_priority = None
    if args.fallback_provider != "none" and args.fallback_provider != args.provider:
        fallback_provider, fallback_source_name, fallback_source_priority = _provider(
            args.fallback_provider,
            settings,
            source_priority=args.fallback_source_priority,
        )

    result = backfill_clickhouse_daily_bars(
        client=client,
        provider=provider,
        fallback_provider=fallback_provider,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        source_name=source_name,
        source_priority=source_priority,
        fallback_source_name=fallback_source_name,
        fallback_source_priority=fallback_source_priority,
        adjustment=args.adjustment,
        refresh_existing=args.refresh_existing,
    )
    print(result.model_dump_json(indent=2))
    if args.sleep_seconds > 0:
        time.sleep(args.sleep_seconds)
    if args.fail_on_warning and result.warnings:
        return 2
    return 0


def _resolve_symbols(value: str | None, client: ClickHouseMarketDataClient) -> list[str]:
    if value:
        symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
        if not symbols:
            raise SystemExit("--symbols did not contain any symbols.")
        return sorted(set(symbols))
    try:
        symbols = [row["symbol"] for row in client.query_daily_bar_symbols()]
    except RuntimeError:
        symbols = []
    if symbols:
        return sorted(set(symbols))
    return sorted({*MULTI_ASSET_ETF_UNIVERSE, *BENCHMARK_INSTRUMENTS})


def _provider(name: str, settings: AppSettings, *, source_priority: int | None):
    if name == "yahoo":
        return YahooChartProvider(adjust_prices=True), "yahoo_adjusted", source_priority if source_priority is not None else 80
    if name == "ib":
        return (
            IbHistoricalDailyBarProvider(settings),
            "interactive_brokers_adjusted_last",
            source_priority if source_priority is not None else 90,
        )
    if name == "tushare":
        return (
            TushareSingleSymbolProvider(TushareUsDailyProvider(token_path=settings.tushare_token_path, adjusted=True)),
            "tushare_us_daily_adj",
            source_priority if source_priority is not None else 70,
        )
    raise ValueError(f"Unsupported provider {name}.")


if __name__ == "__main__":
    raise SystemExit(main())
