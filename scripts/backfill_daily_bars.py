"""Backfill the configured native or legacy serving-history store."""
from backfill_clickhouse_daily_bars import main


if __name__ == "__main__":
    raise SystemExit(main())
