from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.data.sec_edgar import SecEdgarClient, company_facts_to_snapshots
from systematic_trading.research import US_STOCK_REPLACEMENT_UNIVERSE, default_us_stock_symbols
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill point-in-time fundamental snapshots from SEC EDGAR Company Facts."
    )
    parser.add_argument("--database", default="var/stock_replacement.db")
    parser.add_argument("--symbols", default="", help="Comma-separated symbols. Defaults to the stock replacement universe.")
    parser.add_argument("--start-date", default="2012-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--user-agent", default=None, help="SEC requires a declared user agent with contact information.")
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database)
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    user_agent = args.user_agent or settings.sec_user_agent
    symbols = _symbols(args.symbols)

    store = SQLiteStore(database_path)
    store.initialize()
    client = SecEdgarClient(user_agent=user_agent)
    ticker_cik = client.fetch_ticker_cik_map()

    print(f"database={database_path}")
    print("source=sec companyfacts")
    print(f"range={start_date} to {end_date}")
    print(f"user_agent={user_agent}")

    for symbol in symbols:
        cik = ticker_cik.get(symbol)
        if cik is None:
            print(f"{symbol}: skipped; SEC CIK was not found")
            continue
        facts = client.fetch_company_facts(cik)
        snapshots = company_facts_to_snapshots(
            symbol=symbol,
            company_facts=facts,
            price_bars=store.list_price_bars(symbol),
            start_available_date=start_date,
            end_available_date=end_date,
        )
        for snapshot in snapshots:
            store.upsert_fundamental_snapshot(snapshot)
        if snapshots:
            print(
                f"{symbol}: upserted {len(snapshots)} snapshots, "
                f"{snapshots[0].available_date} to {snapshots[-1].available_date}"
            )
        else:
            print(f"{symbol}: no snapshots derived")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)


def _symbols(value: str) -> list[str]:
    if value.strip():
        symbols = [item.strip().upper() for item in value.split(",") if item.strip()]
    else:
        symbols = default_us_stock_symbols()
    unknown = sorted(set(symbols) - set(US_STOCK_REPLACEMENT_UNIVERSE))
    if unknown:
        raise ValueError(f"Unknown stock-universe symbols: {', '.join(unknown)}")
    return symbols


if __name__ == "__main__":
    main()
