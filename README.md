# Systematic Trading

Industrial systematic trading platform in progress.

The project goal is to evolve this repository from a Python-first research and paper-execution toolkit into a 24x7 systematic trading platform with service boundaries, message queues, columnar storage, LEAN-compatible backtesting, Interactive Brokers execution, Grafana-class monitoring, post-trade analysis, and explicit research-to-live promotion controls.

The durable target-state plan is in `docs/industrial-platform-plan.md`.
The active execution tracker is in `docs/execution-kanban.md`.

## Scope

- Long-only global stock and ETF portfolios across the US, Europe, HK, Japan, and Korea.
- CNH-denominated reporting and risk.
- Watchlist-first research workflow with explicit thesis and invalidation rules.
- ETF and index risk parity as the beta bedrock.
- Manual approval by default; an audited, opt-in paper policy can approve and route new strategy TWAP proposals automatically. Live routing remains disabled. See [Trading operations](docs/trading-operations.md).
- Long-term target: micro-services, event bus, columnar research store, transactional order state, live market-data recorder, strong rebalance blotter, and continuous operating loops.

## Current implementation slice

- Project scaffolding and environment-driven settings.
- Core domain models for instruments, research memos, portfolio state, proposals, and orders.
- CNH-aware FX conversion and multi-currency cash ledger.
- Initial inverse-volatility risk-parity sleeve and proposal preview builder.
- Minimal daily backtest engine for deterministic portfolio simulations.
- Offline LEAN research worker with frozen inputs, shared SOTA signals, native simulated fills, Python parity and immutable PostgreSQL research evidence. See [local LEAN backtesting](docs/lean-backtesting.md).
- Read-only IB account/position PnL stream with explicit currencies, freshness and unavailable states, separate from stored daily accounting.
- Thin FastAPI operator API for health, manifest, and risk-parity proposal previews.
- Postgres transactional persistence for watchlists, theses, proposal queues, approval decisions, broker order records, PnL snapshots, and the event outbox on the recommended local platform path.
- ClickHouse serving storage for normalized daily bars and FX rates.
- Provider and broker manifests so the operator API can expose data-source coverage and paper-vs-live execution boundaries.
- Research state tracking with a current SOTA registry and comparison artifacts that include model layer and decision-tree diagrams.

## Target operating model

- Research produces versioned strategy candidates.
- Backtesting validates candidates using point-in-time data, benchmark comparisons, stability checks, and execution assumptions aligned with live routing.
- Paper trading uses the same strategy and portfolio construction contracts as live trading.
- Live trading remains disabled until paper execution, reconciliation, monitoring, alerts, and rollback procedures are proven.
- Daily loops cover post-trade analysis, continuous research, strategy updates, and system robustness review.

## Quick start

1. Create or activate the workspace virtual environment.
2. Install dependencies from `pyproject.toml`.
3. Copy `.env.example` to `.env` and fill in broker and API credentials later.
   For IB Gateway, install the supported official SDK with `.venv/Scripts/python.exe scripts/install_ib_api.py`; the old PyPI SDK cannot fetch the required FX history.
4. Run the API:

```bash
uvicorn systematic_trading.app:app --reload
```

5. Run tests:

```bash
pytest
```

## Local Platform Startup

The [trading operations guide](docs/trading-operations.md) covers Gateway order status, audited cancel/amend/resubmit controls and portfolio synchronization.

For one broker session shared by trading, reconciliation and recording, see the
[IB Gateway operation guide](docs/ib-gateway-operation.md). The receiving PC uses
paper Gateway on port 4002 with separate API client IDs and local raw storage.
The [LEAN and NautilusTrader assessment](docs/trading-engine-assessment.md) describes
the proposed backtest validation pilot and boundaries for any future engine migration.
The [LEAN integration plan](docs/lean-backtest-integration-plan.md) specifies the worker boundaries and acceptance gates. The [platform audit](docs/platform-audit-2026-09-26.md) records timing/data fixes and remaining research and feed limitations.
See [database consolidation](docs/database-consolidation.md) for SQLite retirement, verified archive evidence, D: storage, and the remaining administrator-only PostgreSQL directory move.

Recommended local foundation startup:

For switching PCs, the startup/stop scripts now coordinate PostgreSQL and SQLite
snapshots through `\\192.168.1.32\Public\systematic-trading`. Read the
[NAS database handoff guide](docs/database-sync.md) for first-time setup. Stop the
old PC cleanly before starting the other. A new PC still needs local infrastructure
and credentials; ClickHouse and raw market-data files require separate migration.

```powershell
.\scripts\start_local_platform.ps1
```

This starts NATS JetStream, verifies Postgres, starts ClickHouse, starts the operator dashboard plus event dispatcher, and starts the always-on market-data recorder service. The recorder idles outside regular US equity market hours and only records during the configured session. Open `http://127.0.0.1:8000/platform` for service health and `http://127.0.0.1:8000/operator` for the trading operator UI.

Structured operational logs are written to `var/log/platform_operations.jsonl`.

Check and optionally repair the required local services after Docker, VPN, Wi-Fi, or TWS disruptions:

```powershell
.\scripts\watch_local_platform.ps1
.\scripts\watch_local_platform.ps1 -Repair
```

If Docker Desktop is installed but not running, NATS/ClickHouse startup now tries to start Docker Desktop and waits for the daemon before Docker Compose. If the engine still is not reachable, startup fails with an explicit Docker daemon message. Use `-SkipNats -SkipClickHouse` for a partial non-Docker startup.

The platform health view includes `ib_tws_api`, populated by:

```powershell
.\.venv\Scripts\python.exe .\scripts\probe_ib_tws_health.py
```

This checks the paper TWS API path by waiting for `nextValidId`; it does not attempt to automate TWS login or 2FA recovery.

The trading-management loop and Trading page refresh IB positions, cash, and executions and persist a reconciliation report. An unresolved mismatch raises an alert, blocks EOD PnL/rebalance staging and IB routing, and appears in `IB Portfolio Reconciliation` on `/operator`. The trader can explicitly reset active portfolio/PnL state to the fresh IB snapshot; historical orders and fills remain immutable audit history.

The [dashboard performance guide](docs/dashboard-performance.md) explains chart selection, account reset boundaries, fixed strategy/account alignment and data-gap diagnostics.

After an IB paper-account reset, the same report can be generated from the CLI:

```powershell
.\.venv\Scripts\python.exe .\scripts\reconcile_ib_paper_account.py
```

If the report confirms the broker paper account is reset, the operator can use `Reset local to IB` on the Trading page or explicitly create the baseline from the CLI:

```powershell
.\.venv\Scripts\python.exe .\scripts\reconcile_ib_paper_account.py `
  --record-pnl-reset-baseline `
  --confirm-paper-reset
```

Skip the market-data recorder service for maintenance:

```powershell
.\scripts\start_local_platform.ps1 -SkipMarketDataRecorder
```

The recorder service starts with the five-symbol `SPY/QQQ/TLT/GLD/IWM` pilot and `-RecorderIntradayFeed delayed-trades`. It aggregates timestamped IB delayed trade callbacks into raw 5-second bars, tags them as delayed, and never exposes them as trading-decision data. The paid `reqRealTimeBars` path remains available with `-RecorderIntradayFeed realtime` after API market-data subscriptions are verified. The service stays idle after hours and on weekends; synchronous historical gap-fill runs only after a failed stream chunk so it cannot block a healthy prospective feed.

The recorder service also runs ClickHouse daily-bar backfill on startup and then on an interval, including after-hours/weekends. The default path repairs `market_data.daily_bars` directly from Yahoo adjusted daily bars, with IB historical daily bars as fallback.

The local operator startup path now defaults to `ST_TRANSACTIONAL_STORE_BACKEND=postgres` and `ST_MARKET_DATA_STORE_BACKEND=clickhouse`. Active dashboard, proposal, broker-record, PnL, and event-outbox state use Postgres, while daily bars and FX reads use ClickHouse. SQLite remains an explicit offline test backend and retained recovery artifact; research scripts and reports now use the configured server stores.

Rebalance proposals are time-bound to preserve next-open parity with the backtest. The default execution deadline is 30 minutes after the configured TWAP start on the intended trade date. Change it with `ST_EXECUTION_REBALANCE_TIMEOUT_MINUTES`; expired pending or retryable proposals become `missed`, cannot be approved or resubmitted, and are retained in execution-quality analysis.

The strategy workspace at `/strategies` separates Monitored and Archived artifacts. Membership is configured in `config/strategy-monitoring.json`; current SOTA is always monitored. Monitored results are extended daily through the latest golden market data using the last audited holdings, with artifact end and monitoring method shown explicitly. Click any strategy for performance, benchmark metrics, holdings, leverage, exposure/attribution, and its generated full report when available.

## Optional Tushare data

Put a Tushare token in `./tushare_token.txt` or set `ST_TUSHARE_TOKEN_PATH`. The token file is ignored by git. The optional SDK adapter uses Tushare Pro US adjusted daily bars when `tushare` is installed:

```bash
pip install -e ".[data]"
```

## Repository layout

- `docs/` architecture and operating notes.
- `docs/industrial-platform-plan.md` target architecture, system chart, service boundaries, promotion gates, and execution schedule.
- `docs/execution-kanban.md` Kanban-style execution tracker with status, acceptance criteria, dependencies, and next work order.
- `docs/service-supervisor.md` local service supervision plan.
- `docs/queue-adapter-selection.md` queue adapter decision and future migration triggers.
- `docs/market-data-recorder-contract.md` raw-before-publish recorder contract and replay rules.
- `docs/market-data-recorder-source-plan.md` two-lane recorder source plan, IBKR capacity limits, and ETF universe seed.
- `docs/market-data-golden-source.md` corrected columnar golden-source model for local market data.
- `docs/postgres-transactional-store-design.md` Postgres schema, migration tooling, and SQLite migration plan.
- `docs/columnar-store-target-design.md` ClickHouse, Parquet, and DuckDB target for columnar analytics.
- `docs/schema-registry-convention.md` code-based event/data schema registry and compatibility rules.
- `config/service-manifest.json` machine-readable service manifest for the local operator stack.
- `config/market-data-storage.json` tiered hot/archive/backup storage policy for recorded market data.
- `config/market-data-recorder-sources.json` machine-readable recorder lane, capacity, and source policy.
- `config/columnar-store.json` machine-readable columnar store deployment and storage policy metadata.
- `deploy/nats/` Docker Compose path for the NATS JetStream event bus.
- `deploy/clickhouse/` Docker Compose path for the local ClickHouse columnar store.
- `docs/research-state.md` current research hurdle and SOTA promotion notes.
- `log.md` project decision and operating log.
- `AGENTS.md` repository-level working rules for agents.
- `.agents/skills/` project playbooks for recurring operating loops.
- `src/systematic_trading/` application package.
- `src/systematic_trading/schemas/` code-based schema registry for platform contracts.
- `tests/` deterministic tests for accounting, sleeves, API, and backtests.

## Local state

The recommended local platform startup uses Postgres for transactional state and ClickHouse for market data. `var/systematic_trading.db` is retained only for recovery and existing NAS snapshot-layout compatibility. All source rows are verified in the PostgreSQL legacy archive; default research/reporting paths no longer open it. See [migration evidence and storage locations](docs/database-consolidation.md).
