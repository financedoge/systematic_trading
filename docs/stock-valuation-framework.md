# Probability-Based Stock Valuation Implementation

This is the code-backed first pass for `docs/Probability Based Stock Valuation Framework V1.pdf`.

## Scope

- `systematic_trading.valuation.framework` defines the scorecard, behavioral overlay, scenario valuation, and ranking models.
- `systematic_trading.valuation.ai` calls the OpenAI Responses API with structured JSON output and optional web search.
- `systematic_trading.valuation.screener` builds market-data features and a deterministic fallback score for plumbing tests.
- `systematic_trading.backtest.stock_replacement` replaces the `SPY` target inside the existing monthly SOTA ETF strategy with a selected stock basket.
- `scripts/run_stock_replacement_backtest.py` ties the workflow together: fetch data, rank candidates, choose the top 10, backtest the SPY replacement, and write comparison/report artifacts.

## Important Research Caveat

The first backtest uses a static current ranking to select the stock basket. That is useful for testing the framework plumbing, but it is lookahead-biased as a historical strategy test. Promotion-quality research needs point-in-time fundamentals, historical rankings, survivorship controls, and dated evidence snapshots.

## Run

```powershell
.\.venv\Scripts\python.exe .\scripts\run_stock_replacement_backtest.py --start-date 2012-01-01 --end-date 2026-04-29
```

Useful switches:

- `--no-openai` uses the deterministic market-data fallback.
- `--no-openai-web-search` uses OpenAI without live web search.
- `--ranking-path PATH` reuses a prior `stock_framework_rankings.json`.
- `--stock-weighting equal|framework|inverse-vol` changes stock weights inside the replaced SPY sleeve.
- `--candidate-symbols AAPL,MSFT,NVDA` restricts the candidate universe.
- `--market-data-source tushare-first|tushare|yahoo` controls missing US bar fetches; the default is `tushare-first`, with Yahoo still used for USD/CNH FX.
- `--stock-selection-mode quantitative-point-in-time` re-ranks the candidate universe at each rebalance using only prior prices and fundamental snapshots whose `available_date` is on or before that rebalance date.
- `--fundamentals-path PATH` loads point-in-time fundamental snapshots from JSON before ranking/backtesting.

The OpenAI API key is read from `OPENAI_API_KEY` or `./openai_key.txt`.
The Tushare token is read from `ST_TUSHARE_TOKEN_PATH` or `./tushare_token.txt`.

## Point-in-Time Fundamentals

The quantitative path expects stored `FundamentalSnapshot` records with `symbol`, `period_end`, and `available_date`. The `available_date` is the time gate: a 2020 rebalance cannot see a 2021 filing even if both records are in the database. Example JSON:

```json
[
  {
    "symbol": "MSFT",
    "period_end": "2019-12-31",
    "available_date": "2020-02-01",
    "free_cash_flow_yield": "0.035",
    "earnings_yield": "0.032",
    "return_on_invested_capital": "0.22",
    "net_debt_to_ebitda": "0.3",
    "analyst_eps_revision_90d": "0.04"
  }
]
```

Free US point-in-time snapshots can also be derived from SEC EDGAR Company Facts:

```powershell
.\.venv\Scripts\python.exe .\scripts\backfill_sec_fundamentals.py --database var\stock_replacement.db --start-date 2012-01-01 --end-date 2026-04-29 --user-agent "Your Name your.email@example.com"
```

SEC fair-access policy requires a declared user agent with contact information. You can also set `ST_SEC_USER_AGENT` in `.env`.
