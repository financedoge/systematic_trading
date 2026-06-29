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
- Manual approve and reject workflow before any broker order is routed.
- Long-term target: micro-services, event bus, columnar research store, transactional order state, live market-data recorder, strong rebalance blotter, and continuous operating loops.

## Current implementation slice

- Project scaffolding and environment-driven settings.
- Core domain models for instruments, research memos, portfolio state, proposals, and orders.
- CNH-aware FX conversion and multi-currency cash ledger.
- Initial inverse-volatility risk-parity sleeve and proposal preview builder.
- Minimal daily backtest engine for deterministic portfolio simulations.
- Thin FastAPI operator API for health, manifest, and risk-parity proposal previews.
- Local SQLite persistence for watchlists, theses, normalized price bars, FX rates, proposal queues, and approval decisions.
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
4. Run the API:

```bash
uvicorn systematic_trading.app:app --reload
```

5. Run tests:

```bash
pytest
```

## Local Platform Startup

Recommended local foundation startup:

```powershell
.\scripts\start_local_platform.ps1
```

This starts NATS JetStream, verifies Postgres, starts ClickHouse, and starts the operator dashboard plus event dispatcher. Open `http://127.0.0.1:8000/platform` for service health and `http://127.0.0.1:8000/operator` for the trading operator UI.

Structured operational logs are written to `var/log/platform_operations.jsonl`.

Check and optionally repair the required local services after Docker, VPN, Wi-Fi, or TWS disruptions:

```powershell
.\scripts\watch_local_platform.ps1
.\scripts\watch_local_platform.ps1 -Repair
```

The market-data recorder is opt-in to protect disk space:

```powershell
.\scripts\start_local_platform.ps1 -StartMarketDataRecorder
```

Recorder pilots default to IB delayed market data so the pipeline can be tested without paid live subscriptions. Use `-RecorderMarketDataMode live` only after the needed IB market-data subscriptions are active.

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
- `docs/postgres-transactional-store-design.md` target Postgres schema and SQLite migration plan.
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

The API now initializes a local SQLite store at `var/systematic_trading.db` by default. This is used for watchlist instruments, thesis memos, normalized price bars, FX rates, queued proposals, and approval decisions.
