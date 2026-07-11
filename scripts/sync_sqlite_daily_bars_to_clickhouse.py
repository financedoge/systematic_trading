from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.market import PriceBar
from systematic_trading.market_data import ClickHouseMarketDataClient, daily_bar_row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync SQLite daily price_bars into ClickHouse golden daily_bars.")
    parser.add_argument("--database", default=None)
    parser.add_argument("--clickhouse-url", default="http://127.0.0.1:8123")
    parser.add_argument("--clickhouse-database", default=os.getenv("ST_CLICKHOUSE_DATABASE", "systematic_trading"))
    parser.add_argument("--clickhouse-user", default=os.getenv("ST_CLICKHOUSE_USER", "st_app"))
    parser.add_argument("--clickhouse-password", default=os.getenv("ST_CLICKHOUSE_PASSWORD", "local-dev-change-me"))
    parser.add_argument("--source-name", default="sqlite_price_bars")
    parser.add_argument("--source-priority", type=int, default=100)
    parser.add_argument("--adjustment", default="provider_default")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    client = ClickHouseMarketDataClient(
        args.clickhouse_url,
        database=args.clickhouse_database,
        user=args.clickhouse_user,
        password=args.clickhouse_password,
    )
    if not args.dry_run:
        client.ensure_daily_bars_table()

    total = 0
    batch: list[dict] = []
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        query = "SELECT symbol, payload FROM price_bars"
        params: list[str] = []
        if args.symbol:
            query += " WHERE symbol = ?"
            params.append(args.symbol.upper())
        query += " ORDER BY symbol, trade_date"
        for row in connection.execute(query, tuple(params)):
            bar = PriceBar.model_validate_json(row["payload"])
            batch.append(
                daily_bar_row(
                    symbol=row["symbol"],
                    bar=bar,
                    source_name=args.source_name,
                    source_priority=args.source_priority,
                    adjustment=args.adjustment,
                )
            )
            if len(batch) >= args.batch_size:
                total += _flush(client, batch, dry_run=args.dry_run)
                batch = []
        total += _flush(client, batch, dry_run=args.dry_run)
    print(f"synced_daily_bars={total}")
    return 0


def _flush(client: ClickHouseMarketDataClient, rows: list[dict], *, dry_run: bool) -> int:
    if not rows:
        return 0
    if dry_run:
        return len(rows)
    return client.insert_daily_bar_rows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
