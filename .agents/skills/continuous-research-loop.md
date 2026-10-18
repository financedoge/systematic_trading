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
   Always include dynamic rebalancing as a research option alongside a fixed-interval control. Register the event/threshold grid before results, including joint selection-width/timing choices when relevant. Target-change events compare latest theoretical with last adopted target weights, including cash; adopted-target versus actual-held alignment stays in Trading. Evaluate net Sharpe with return/drawdown guards, actual traded notional and costs, execution delays and chronological parameter stability. Do not carry the current universe's preference for monthly rebalancing forward as a universal conclusion.
4. Compare against SOTA, relevant external benchmarks, and risk-adjusted metrics.
5. Separate in-sample, out-of-sample, walk-forward, and stress-period results.
6. Check turnover, liquidity, concentration, drawdown, fee sensitivity, and parameter stability.
   The 44 bp annual-cost ceiling was retired by the operator on 2026-10-17. Extra trading cost is acceptable when incremental return exceeds incremental cost against a matched control. Replay the declared candidates and controls without an absolute-cost filter; judge net Sharpe with return/drawdown guards, cost/delay stress and chronological stability. IC/breakeven margins remain diagnostics, not portfolio-return evidence. Use `turnover_gate.screen` for current diagnostics; `legacy_screen` and the old frozen runners are historical reproduction only.
7. Record artifacts and decide whether the candidate is rejected, retained for observation, or sent to promotion review.
8. Update `docs/research-state.md` and `log.md` when the research state changes.
9. On retirement/completion, apply the operator's storage policy: keep compact
   findings, the definition/runner and retirement receipt; discard unneeded bulky
   exploratory artifacts after checking active/paper/promotion dependencies. Exact
   replay is required for active candidates and promotion evidence, not for every
   retired historical experiment. Reruns on replacement audited batches are new
   evidence. Follow `docs/storage-retention-and-windows-native-plan.md`.

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
- An active or promotion candidate cannot be reproduced from its retained inputs;
  intentionally retired historical research instead carries its retirement status.
