# Architecture

## Principles

- Optimize for low turnover, concentrated, thesis-driven portfolios.
- Keep CNH as the accounting and risk currency even when assets trade in foreign currencies.
- Separate research, backtesting, proposal generation, and broker execution concerns.
- Keep v1 human-in-the-loop. The platform proposes trades and explains them; the operator accepts or rejects them.

## Layers

1. Domain layer: instruments, theses, proposals, orders, positions, fills, and portfolio snapshots.
2. Data layer: market data adapters, FX series, filings, corporate actions, and quality checks.
3. Research layer: watchlists, memo drafting, valuation context, catalysts, and invalidation rules.
4. Strategy layer: beta and alpha sleeves that emit target weights and human-readable rationale.
5. Backtest layer: deterministic daily engine with open and TWAP-like execution assumptions.
6. Execution layer: Interactive Brokers paper-first routing, validation, reconciliation, and audit.
7. Web layer: thin operator interface for monitoring, approvals, and paper trading.
8. Storage layer: local SQLite persistence for watchlists, proposal queues, and decision history until a larger database is warranted.

## Initial module boundaries

- `domain/`: schema and business language.
- `backtest/`: FX conversion, cash ledger, valuation, risk helpers, and daily engine.
- `storage/`: local persistence and schema management.
- `portfolio/`: sleeve logic and proposal builders.
- `data/`: source manifests and future provider adapters.
- `execution/`: broker environment manifests and future routing adapters.
- `web/`: API endpoints and request contracts.

## Near-term roadmap

- Add persistent storage for raw data, normalized bars, FX, and research artifacts.
- Add filings and macro adapters.
- Add paper broker state mirroring and approval queue persistence.
- Add a thin web UI on top of the current API.
