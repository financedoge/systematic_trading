# Continuous Research Loop

## Trigger

Run daily for lightweight checks and weekly for deeper challenger strategy review.

## Inputs

- Current SOTA definition and artifacts from `docs/research-state.md`.
- Strategy registry and candidate specs.
- Point-in-time data and feature versions.
- Published audited continuous histories only, pinned to their batch and verified hashes. Choose the supported raw or dividend/split-adjusted basis explicitly. Provider downloads are audit evidence, not direct inputs to new research; acquire, reconcile and publish missing data before use. Missing raw observations and unresolved identities must remain excluded under the declared coverage rules. Historical vintage limitations remain even after price auditing.
- Backtest reports and benchmark comparisons.
- Post-trade observations and live or paper slippage evidence.

## Workflow

Tracked candidates must be implemented as full executable strategy definitions and calculated by the application's analytics service. Agents may develop and validate that code, but must not become recurring calculation workers or maintain manually refreshed strategy cards. Use the shared full report with current held/target weights, NAV, matched benchmarks and the complete decision chart. See `AGENTS.md` and `docs/etf-activity-lag20-tracking.md`.

1. Start from the current SOTA hurdle, not from a weak benchmark.
2. Define the research question and expected failure mode before running experiments.
3. Use point-in-time features and explicit universe rules.
4. Compare against SOTA, relevant external benchmarks, and risk-adjusted metrics.
5. Separate in-sample, out-of-sample, walk-forward, and stress-period results.
6. Check turnover, liquidity, concentration, drawdown, fee sensitivity, and parameter stability.
7. Record artifacts and decide whether the candidate is rejected, retained for observation, or sent to promotion review.
8. Update `docs/research-state.md` and `log.md` when the research state changes.

## Outputs

- Candidate report.
- Benchmark comparison.
- Stability and overfit audit.
- Recommendation: reject, observe, paper candidate, or retire.

## Stop Conditions

- Non-point-in-time inputs.
- Missing benchmark comparison.
- Unexplained out-of-sample jump.
- Parameter search without overfit accounting.
- Candidate cannot be reproduced from stored artifacts.
