# Strategy Promotion Control

## Trigger

Run whenever a strategy is proposed for promotion from research to paper, paper to shadow live, shadow live to live, or live to retired.

## Inputs

- Strategy specification and version.
- Universe, data, and feature versions.
- Backtest artifacts and report hashes.
- Benchmark, stability, and robustness reports.
- Paper-trading evidence when applicable.
- Risk limits, capital caps, and liquidity checks.
- Rebalance blotter output.
- Operator approval record.

## Workflow

1. Confirm the current promotion state and requested target state.
2. Verify strategy, data, feature, and universe versions are fixed and reproducible.
3. Verify point-in-time data and no known lookahead or survivorship issue.
4. Review benchmark, out-of-sample, stress-period, turnover, drawdown, and fee sensitivity results.
5. Verify risk limits, capital caps, liquidity limits, and kill-switch conditions.
6. Verify paper execution, reconciliation, and slippage evidence before shadow or live promotion.
7. Confirm rollback plan and disable procedure.
8. Record the decision and update the strategy registry, research state, and `log.md`.

## Outputs

- Promotion decision: approve, reject, defer, retire, or rollback.
- Required evidence checklist.
- Artifact references.
- Follow-up actions.

## Stop Conditions

- Missing reproducible artifacts.
- Missing point-in-time evidence.
- Missing paper-trading evidence for live promotion.
- Unresolved reconciliation break.
- No rollback plan.
