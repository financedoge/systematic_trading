# Market Data Golden Source

## Correction

The market-data audit page must not be limited to freshly recorded raw IB data. The platform needs a unified local market-data source in the columnar store.

## Storage Layers

1. Raw immutable evidence:
   - Raw JSONL/parquet-style partitions under the market-data hot/archive roots.
   - Keeps capture provenance: source, capture environment, request id, raw ref, byte offset, payload hash, and quality flags.
   - Used for replay, forensic audit, and source debugging.

2. Source observations:
   - Future ClickHouse tables should keep all source observations from IB, Yahoo, Tushare, Wind, and other vendors.
   - Used for gap filling, cross-source validation, and source-quality scoring.

3. Golden market data:
   - ClickHouse tables used by the UI, research, backtests, feature jobs, and operating checks.
   - A historical bar is not keyed by paper/live environment.
   - Identity keys are symbol/instrument id, timestamp/date, bar size, data kind, adjustment policy, source/version, and availability time.

## Current First Slice

Table: `market_data.daily_bars`

Purpose:

- Local golden daily OHLCV table.
- Initial source is the existing SQLite `price_bars` table, which has data from Yahoo/Tushare/IB fallback workflows.
- Query serving should use ClickHouse `FINAL` semantics because the local table uses `ReplacingMergeTree` for idempotent refresh.

Initial sync command:

```powershell
.\.venv\Scripts\python.exe .\scripts\sync_sqlite_daily_bars_to_clickhouse.py --batch-size 1000
```

Current local smoke on 2026-07-11 loaded 140,920 daily rows covering 39 symbols from 2012-01-03 through 2026-07-10 after the recorder startup backfill filled recent stale symbols.

The operator page `/platform/market-data-audit` now uses this table as the primary market-data workstation. It provides:

- Searchable symbol selector sourced from ClickHouse.
- Full-history daily bars by default, with date range, quick range, pan, and zoom controls.
- OHLCV chart with volume pane.
- Daily-bar table with source, adjustment, availability, quality flags, and payload hash.
- Secondary raw-evidence section backed by the raw recorder audit API.

Direct daily backfill command:

```powershell
.\.venv\Scripts\python.exe .\scripts\backfill_clickhouse_daily_bars.py `
  --symbols SPY `
  --start-date 2012-01-01 `
  --end-date 2026-07-10 `
  --provider yahoo `
  --fallback-provider ib
```

The always-on market-data recorder service now runs this ClickHouse daily backfill child job on startup and then on a configured interval, including weekends and after-hours. The default provider is Yahoo adjusted daily data, with IB historical daily bars as fallback if Yahoo fails or returns no bars. Tushare is available as an explicit provider when the local token and SDK are configured.

Backfill repair semantics:

- Missing provider dates are inserted into ClickHouse.
- Existing flat zero-volume carry-forward rows are treated as stale and replaced when the provider has a real bar for that date.
- Existing flat zero-volume carry-forward rows are deleted when the provider does not return that date, which usually means the stored row was a holiday artifact.

## Current Unified State

This is not fully unified yet.

Unified now:

- Daily historical bars have been migrated into ClickHouse `market_data.daily_bars`.
- The operator market-data page and daily API read this ClickHouse table as the preferred serving source.
- Daily backfill now writes directly to ClickHouse instead of requiring a SQLite-to-ClickHouse sync first.
- Runtime `store.list_price_bars` and `store.list_fx_rates` can be routed to ClickHouse with `ST_MARKET_DATA_STORE_BACKEND=clickhouse`.
- The recommended local operator startup path uses Postgres for transactional state and ClickHouse for market data.

Still transitional:

- SQLite `price_bars` still exists because some legacy research scripts instantiate `SQLiteStore` directly.
- Raw live/historical recorder JSONL remains an immutable evidence archive outside ClickHouse.
- Intraday recorder bars are not yet normalized into a ClickHouse serving table.
- Source-observation tables are not yet implemented, so source disagreement is not fully audited.
- SQLite still exists as a legacy fallback and migration source, but the recommended local platform startup now uses Postgres for proposals, approvals, broker order records, event outbox, and PnL snapshots.

## Required Next Slice

The next implementation slice should fill the missing data-engineering pieces behind the workstation:

- Source-observation ClickHouse tables for Yahoo, Tushare, Wind, IB historical, and IB live recorder inputs.
- Explicit source precedence and cross-source disagreement checks before writing golden rows.
- Intraday golden bar tables with bar-size identity and quality flags.
- Audit drilldown from a golden bar to source observations and raw refs.
- Gap, duplicate, stale, and source-disagreement panels.

## Source Policy

- Yahoo, Tushare, Wind, IB historical, and IB live recorder should feed the columnar source-observation layer.
- Golden tables should resolve source observations according to explicit source priority and quality checks.
- Raw recorder data remains evidence, not the primary UI table.
