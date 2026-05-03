# Systematic Trading

Python-first toolkit for global long-horizon stock and ETF research, backtesting, and paper-first execution.

## Scope

- Long-only global stock and ETF portfolios across the US, Europe, HK, Japan, and Korea.
- CNH-denominated reporting and risk.
- Watchlist-first research workflow with explicit thesis and invalidation rules.
- ETF and index risk parity as the beta bedrock.
- Manual approve and reject workflow before any broker order is routed.

## Current implementation slice

- Project scaffolding and environment-driven settings.
- Core domain models for instruments, research memos, portfolio state, proposals, and orders.
- CNH-aware FX conversion and multi-currency cash ledger.
- Initial inverse-volatility risk-parity sleeve and proposal preview builder.
- Minimal daily backtest engine for deterministic portfolio simulations.
- Thin FastAPI operator API for health, manifest, and risk-parity proposal previews.
- Local SQLite persistence for watchlists, theses, normalized price bars, FX rates, proposal queues, and approval decisions.
- Provider and broker manifests so the operator API can expose data-source coverage and paper-vs-live execution boundaries.

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

## Repository layout

- `docs/` architecture and operating notes.
- `src/systematic_trading/` application package.
- `tests/` deterministic tests for accounting, sleeves, API, and backtests.

## Local state

The API now initializes a local SQLite store at `var/systematic_trading.db` by default. This is used for watchlist instruments, thesis memos, normalized price bars, FX rates, queued proposals, and approval decisions.
