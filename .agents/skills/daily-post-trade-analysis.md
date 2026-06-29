# Daily Post-Trade Analysis

## Trigger

Run after the relevant market close and after market data, broker orders, fills, cash, positions, and FX are expected to be complete.

## Inputs

- Broker account snapshot.
- Broker open orders, filled orders, executions, and commissions.
- Local proposal, approval, order, and fill records.
- Recorded market data and normalized bars.
- FX rates.
- Strategy targets and rebalance blotter.
- Alert and incident logs.

## Workflow

1. Confirm market-data completeness and freshness.
2. Reconcile broker positions, cash, orders, fills, and commissions to local state.
3. Calculate daily PnL, attribution, exposure, turnover, and cash residuals.
4. Compare intended orders against actual fills and slippage.
5. Review all alerts, stale-data events, rejects, retries, and reconciliation breaks.
6. Identify whether any strategy, data, execution, or operations issue requires follow-up.
7. Stage the next rebalance proposal only if data and reconciliation checks pass.
8. Update `log.md` with status, incidents, and next actions.

## Outputs

- Daily PnL and attribution report.
- Slippage and execution-quality report.
- Reconciliation report.
- Alert and incident summary.
- Next-action list.

## Stop Conditions

- Missing or stale market data.
- Broker/local reconciliation break.
- Unknown order, fill, cash, or position mismatch.
- Unresolved trading-critical alert.
