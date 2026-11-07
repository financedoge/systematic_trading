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
   Before retirement or archival, run and retain the strategy/asset dependency
   impact review. Do not remove required inputs or stop shared publishers when
   their portfolio report is archived. For new tracked composites, verify the
   asset-pool reuse review, pinned decomposition and automatic signal-monitoring
   coverage described in `docs/strategy-assets.md`.
2. Verify strategy, data, feature, and universe versions are fixed and reproducible.
   For a new signal or changed recipe, attach the versioned P4.20 dossier and
   `scripts/review_research_evidence.py` assessment described in
   `docs/research-evidence-governance-v1.md`. Check actual evidence quality, not
   only checklist completeness. Reused evaluation periods are development data
   for any selection they inform. Half-life/IC/cost diagnostics cannot replace
   realized net comparisons; no universal lifetime or annual-cost veto applies.
   The assessment grants no monitoring, promotion, allocation or execution authority.
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
