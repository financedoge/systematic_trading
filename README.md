# Systematic Trading

Python systematic trading platform with governed research, reproducible backtests,
application-owned strategy monitoring and Interactive Brokers paper execution.
Native Windows PostgreSQL stores operational state and publication metadata,
Parquet/DuckDB serves analytics, and native NATS carries outbox events. Independent
LEAN validation runs in restricted Windows workers. Live routing remains disabled.

The selected replacement architecture is native Windows PostgreSQL, Parquet/DuckDB
and NATS, with bounded retention of archived research artifacts. See the
[disk cleanup and native migration plan](docs/storage-retention-and-windows-native-plan.md).
See the [native runtime guide](docs/native-windows-runtime.md) for startup, resource
limits and recovery, and the Kanban for migration acceptance status.

Start with the [documentation index](docs/README.md) and
[code and maintenance guide](docs/repository-maintenance.md).

The project goal is to evolve this repository from a Python-first research and paper-execution toolkit into a 24x7 systematic trading platform with service boundaries, message queues, columnar storage, LEAN-compatible backtesting, Interactive Brokers execution, Grafana-class monitoring, post-trade analysis, and explicit research-to-live promotion controls.

The durable target-state plan is in `docs/industrial-platform-plan.md`.
The active execution tracker is in `docs/execution-kanban.md`.

Trading monitoring now shares one portfolio start/episode across holdings, P&L, attribution, misses and EOD processing. See [application connection repairs](docs/app-connection-repairs-2026-09-28.md) for the shared UI/data/accounting contracts, validation and remaining source-evidence requirements.

## Scope

- Long-only global stock and ETF portfolios across the US, Europe, HK, Japan, and Korea.
- CNH-denominated reporting and risk.
- Watchlist-first research workflow with explicit thesis and invalidation rules.
- ETF and index risk parity as the beta bedrock.
- Manual approval by default; an audited, opt-in paper policy can approve and route new strategy TWAP proposals automatically. Live routing remains disabled. See [Trading operations](docs/trading-operations.md).
- Long-term target: micro-services, event bus, columnar research store, transactional order state, live market-data recorder, strong rebalance blotter, and continuous operating loops.

## Current implementation

- Environment-driven settings and guarded, supervised local services.
- Core domain models for instruments, research memos, portfolio state, proposals, and orders.
- CNH-aware FX conversion and multi-currency cash ledger.
- Initial inverse-volatility risk-parity sleeve and proposal preview builder.
- Minimal daily backtest engine for deterministic portfolio simulations.
- Offline LEAN research worker with frozen inputs, shared SOTA signals, native simulated fills, Python parity and immutable PostgreSQL research evidence. See [local LEAN backtesting](docs/lean-backtesting.md).
- Read-only IB account/position PnL stream with explicit currencies, freshness and unavailable states, separate from stored daily accounting.
- FastAPI operator API for strategy tracking, allocation, paper execution, data and health.
  API contracts, pure risk-parity preview construction and packaged presentation assets
  now have separate module boundaries.
- Postgres transactional persistence for watchlists, theses, proposal queues, approval decisions, broker order records, PnL snapshots, and the event outbox on the recommended local platform path.
- Immutable Parquet storage with PostgreSQL manifests and native DuckDB queries.
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
See [database consolidation](docs/database-consolidation.md) for SQLite retirement,
verified archive evidence and PostgreSQL's verified D: storage location.

Recommended local foundation startup:

Startup and shutdown work without NAS access. PostgreSQL checkpoints stay
local and optionally synchronize through `\\192.168.1.32\Public\systematic-trading`.
The latest verified snapshot revision wins; unchanged backups retain their revision
time, and incoming restores wait for stopped services. Read the
[optional NAS backup guide](docs/database-sync.md). A new PC still needs local infrastructure
and credentials. The optional [full-system backup worker](docs/full-system-backup.md)
captures a consistent PostgreSQL/Parquet inventory, native NATS and retained
raw/audited/model/research files with encrypted
deduplicated snapshots and automatic reconnect retries.

```powershell
.\scripts\start_local_platform.ps1
```

This starts native NATS JetStream, verifies PostgreSQL, performs guarded stopped
startup retention, and starts the operator dashboard, event dispatcher and recorder.
DuckDB is embedded; no Docker/WSL service is started. Prospective capture runs during
regular US equity sessions; historical recovery continues outside market hours.
Open `http://127.0.0.1:8000/platform` for health and `/operator` for trading.

Structured operational logs are written to `var/log/platform_operations.jsonl`.

Startup also runs local service recovery: missing services restart through their
normal guarded launchers, with bounded backoff. Explicit stop scripts pause the
corresponding target; full shutdown stops recovery first. Use `-SkipRecovery` to
omit it. See the [recovery review and limits](docs/robustness-review-2026-09-30.md).

Inspect or request a one-shot repair after process, VPN, Wi-Fi, or TWS disruptions:

```powershell
.\scripts\watch_local_platform.ps1
.\scripts\watch_local_platform.ps1 -Repair
```

Native NATS startup verifies its pinned executable and migrated stream. Native
LEAN requires an accepted runtime manifest. Missing infrastructure fails explicitly;
the native profile does not start Docker Desktop. Legacy ClickHouse scripts remain
available only for explicitly selected migration/rollback work.

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

The recorder service starts with the five-symbol `SPY/QQQ/TLT/GLD/IWM` pilot and `-RecorderIntradayFeed delayed-trades`. That channel retains incomplete sampled quotes in five-second buckets, not complete interval OHLCV or market volume; it is raw inspection evidence only. Recorded Bars excludes these samples and defaults to actual IB historical OHLCV candles. The paid `reqRealTimeBars` path remains available with `-RecorderIntradayFeed realtime` after API market-data subscriptions are verified. A separate paced worker recovers up to six months of IB 5-second history, resumes persisted gaps after outages and keeps running after hours. See [intraday recovery](docs/intraday-recovery.md) for progress, limits and configuration.

The recorder service also runs daily-bar backfill through the configured native
store, including after-hours/weekends. Acquisition and source repair remain separate
from the audited publication gates required for research inputs.

Local startup defaults to PostgreSQL, Parquet/DuckDB and native LEAN. Active
dashboard, proposal, broker-record, PnL and outbox state use PostgreSQL; analytical
histories use immutable Parquet. SQLite remains an explicit offline test backend.

Rebalance proposals are time-bound to preserve next-open parity with the backtest. The default execution deadline is 30 minutes after the configured TWAP start on the intended trade date. Change it with `ST_EXECUTION_REBALANCE_TIMEOUT_MINUTES`; expired pending or retryable proposals become `missed`, cannot be approved or resubmitted, and are retained in execution-quality analysis.

The strategy workspace at `/strategies` separates Monitored strategies and Archived artifacts. Membership and calculation settings are configured in `config/strategy-monitoring.json`. The app calculates registered monitored strategies from audited histories, replaying signals and monthly rebalances and updating NAV, held weights and indicative latest targets. The same full report shows risk parity, URTH and SOTA comparisons, period metrics, drawdowns, holdings/contributions, signal attribution and decision charts. Select `calculation.engine` as `lean` (with Python parity) or `python` (the same frozen accounting contract); the app refreshes on input/definition changes or through its Refresh calculations button. No agent scheduler is involved. See [tracked strategy calculations](docs/etf-activity-lag20-tracking.md). The [rolling one-year XGBoost + lag-20 candidate](docs/rolling-xgboost-lag20-tracking.md) adds app-owned monthly fitting across all cores, immutable model lineage, matched controls and inspectable fitted trees; install `.[rolling-research]` for its training worker.

Strategy pages and account performance read committed analytical publications.
A background worker refreshes analytical histories when source data changes.
Daily ETF acquisition retries across Yahoo chart hosts and passes the existing
audit/publication gates; independent USD/CNH evidence catch-up runs before strategy
calculations even when account reconciliation/EOD is blocked. Reports and health
show stale price/NAV dates explicitly. The app catches up when running after a
laptop outage; Gateway connectivity remains necessary for observed FX and trading.
See [analytical time-series migration](docs/analytics-migration.md) for coverage,
verification, freshness, rollback and backup requirements.

## Optional Tushare data

Put a Tushare token in `./tushare_token.txt` or set `ST_TUSHARE_TOKEN_PATH`. The token file is ignored by git. The optional SDK adapter uses Tushare Pro US adjusted daily bars when `tushare` is installed:

```bash
pip install -e ".[data]"
```

## Repository layout

The [documentation index](docs/README.md) groups current runbooks, contracts and
dated findings. Historical session notes and registered research protocols are
preserved in the verified [archive](docs/archive/README.md); use current research
state and the Kanban before interpreting old results or priorities.

- `docs/` architecture and operating notes.
- `docs/industrial-platform-plan.md` target architecture, system chart, service boundaries, promotion gates, and execution schedule.
- `docs/execution-kanban.md` Kanban-style execution tracker with status, acceptance criteria, dependencies, and next work order.
- `docs/service-supervisor.md` local service supervision plan.
- `docs/queue-adapter-selection.md` queue adapter decision and future migration triggers.
- `docs/market-data-recorder-contract.md` raw-before-publish recorder contract and replay rules.
- `docs/market-data-recorder-source-plan.md` two-lane recorder source plan, IBKR capacity limits, and ETF universe seed.
- `docs/market-data-golden-source.md` corrected columnar golden-source model for local market data.
- `docs/postgres-transactional-store-design.md` Postgres schema, migration tooling, and SQLite migration plan.
- `docs/columnar-store-target-design.md` Native PostgreSQL/Parquet/DuckDB analytics and the legacy migration boundary.
- `docs/schema-registry-convention.md` code-based event/data schema registry and compatibility rules.
- `config/service-manifest.json` machine-readable service manifest for the local operator stack.
- `config/market-data-storage.json` tiered hot/archive/backup storage policy for recorded market data.
- `config/market-data-recorder-sources.json` machine-readable recorder lane, capacity, and source policy.
- `config/columnar-store.json` machine-readable columnar store deployment and storage policy metadata.
- `config/native-runtime.json` pinned native NATS/LEAN runtime and acceptance references.
- `deploy/nats/` and `deploy/clickhouse/` legacy migration definitions.
- `docs/research-state.md` current research hurdle and SOTA promotion notes.
- `log.md` project decision and operating log.
- `AGENTS.md` repository-level working rules for agents.
- `.agents/skills/` project playbooks for recurring operating loops.
- `src/systematic_trading/` application package.
- `src/systematic_trading/presentation/assets/` packaged HTML page/report templates.
- `src/systematic_trading/web/contracts.py` HTTP request/response contracts.
- `src/systematic_trading/portfolio/preview.py` validated, side-effect-free proposal previews.
- `scripts/` stable CLI/launcher entry points; [script guide](scripts/README.md).
- `src/systematic_trading/schemas/` code-based schema registry for platform contracts.
- `tests/` deterministic tests for accounting, sleeves, API, and backtests.

## Local state

The local platform uses PostgreSQL metadata/operations and Parquet/DuckDB analytics.
`var/systematic_trading.db` remains frozen historical evidence in file backups.
Its source rows are verified in the PostgreSQL archive; active application and SQL
backup paths do not require SQLite. See [storage locations](docs/database-consolidation.md).
