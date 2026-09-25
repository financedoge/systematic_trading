# Architecture

Local two-PC operation uses the [NAS database handoff protocol](database-sync.md):
one active workspace, local PostgreSQL/SQLite engines, verified immutable NAS
snapshots, startup conflict detection, and a final stopped-service backup before
ownership release. It does not replicate ClickHouse, broker configuration or raw
market-data files, and it does not change execution approval or reconciliation gates.

## Target State

The embedded trading management loop owns an optional paper automatic-approval controller. Its machine/profile/strategy-bound policy defaults off and is audited locally and in the event outbox. Eligible new strategy proposals pass fresh account, data, sizing, exposure, open-order and session checks before a compare-and-set approval and normal idempotent router handoff. A durable attempt claim precedes submission; restarts never retry uncertain attempts. SQLite and PostgreSQL approval decisions support expected-status checks. Read-only post-trade TWAP jobs use a separate IB client and retain observed bars in `var/execution_benchmarks/`.

The target architecture is an industrial 24x7 systematic trading platform: micro-services connected by a message queue, immutable market-data recording, columnar analytics storage, transactional order and approval state, LEAN-compatible backtesting, Interactive Brokers execution, strong portfolio rebalancing controls, and Grafana-class monitoring.

The full target-state system chart and execution schedule are maintained in `docs/industrial-platform-plan.md`.

## Current State

The current implementation is the v0 control plane and research harness. It is intentionally Python-first, local-first, and paper-first while the contracts, tests, and operator workflow are hardened.

## Principles

- Optimize for low turnover, concentrated, thesis-driven portfolios.
- Keep CNH as the accounting and risk currency even when assets trade in foreign currencies.
- Separate research, backtesting, proposal generation, and broker execution concerns.
- Keep v1 human-in-the-loop. The platform proposes trades and explains them; the operator accepts or rejects them.
- Preserve point-in-time data contracts between research, backtesting, paper trading, and live trading.
- Treat every order intent, approval, broker event, fill, reconciliation result, and operator action as audit data.
- Keep paper and live behavior on the same contracts, separated by environment controls and hard limits.
- Use Go, Rust, or C++ only for service boundaries where measured Python performance or reliability is insufficient.

## Layers

1. Domain layer: instruments, theses, proposals, orders, positions, fills, and portfolio snapshots.
2. Data layer: market data adapters, FX series, filings, corporate actions, and quality checks.
3. Research layer: watchlists, memo drafting, valuation context, catalysts, and invalidation rules.
4. Strategy layer: beta and alpha sleeves that emit target weights and human-readable rationale.
5. Backtest layer: deterministic in-repo engine for unit-scale checks; LEAN-compatible production backtests for promotion.
6. Portfolio layer: rebalance blotter, constraints, pre-trade checks, sizing, and approval workflow.
7. Execution layer: Interactive Brokers paper-first routing, validation, reconciliation, idempotent order submission, and audit.
8. Web layer: operator interface for monitoring, approvals, paper trading, and later controlled live trading.
9. Storage layer: SQLite for v0 local persistence; Postgres for transactional target state; ClickHouse for columnar query serving; Parquet for immutable market-data archive and DuckDB-readable research snapshots.
10. Observability layer: metrics, logs, traces, dashboards, alerts, incidents, and daily operating reports.

## Initial module boundaries

- `domain/`: schema and business language.
- `backtest/`: FX conversion, cash ledger, valuation, risk helpers, and daily engine.
- `storage/`: local persistence and schema management.
- `portfolio/`: sleeve logic and proposal builders.
- `data/`: source manifests and future provider adapters.
- `execution/`: broker environment manifests and future routing adapters.
- `web/`: API endpoints and request contracts.

## Target Service Boundaries

- Market data recorder: capture raw live data before downstream processing and publish normalized events.
- Data quality service: validate freshness, gaps, duplicates, corporate actions, FX, and source precedence.
- Feature service: compute versioned point-in-time features shared by research, backtests, paper, and live.
- Strategy service: load approved strategy versions and emit target portfolios.
- Portfolio service: convert targets into rebalance proposals with risk and cash constraints.
- Order management service: persist order intents, enforce idempotency, submit to IB, and track lifecycle.
- Reconciliation service: compare local state to broker orders, fills, positions, cash, and commissions.
- Alert service: route warnings to email, SMS or push, desktop popup, dashboards, and incident logs.
- Reporting service: generate post-trade, PnL, slippage, exposure, and robustness reports.

## Near-Term Roadmap

- Add persistent storage for raw data, normalized bars, FX, and research artifacts.
- Add filings and macro adapters.
- Add paper broker state mirroring and approval queue persistence.
- Add a thin web UI on top of the current API.
- Introduce event schemas, Postgres transactional state, and the ClickHouse plus Parquet columnar market-data path.
- Maintain event and data schemas through the code-based registry in `systematic_trading.schemas` until a separate schema registry service is justified.
- Build an always-on market-data recorder and replay path.
- Promote ClickHouse `market_data.daily_bars` and later intraday tables as the golden market-data source for UI, research, backtests, feature jobs, and validation.
- Integrate LEAN into the promotion path for production candidates.
- Build the strong rebalance blotter before any live trading.
- Add Grafana-class dashboards and multi-channel alerts.
