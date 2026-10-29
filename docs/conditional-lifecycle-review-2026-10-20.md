# Recent-change review and corrected conditional lifecycle retest

Reviewed `ffa3996` and the preceding calculation/backup changes. The operator
selected the conditional FR25/lifecycle branch for continuation. The corrected
fixed 10% dynamic candidate **does not pass the research gate**. Keep FR25 as the
comparison hurdle; do not promote, fund or retune the candidate on this inspected
sample. Monitoring membership and existing execution authority are unchanged.

## Review findings and repairs

| Priority | Finding | Repair and evidence |
| --- | --- | --- |
| P1 | Automatic renewal skipped a newer independent pending, approved/claimed or rejected proposal and could renew an older target for the same allocation. Renewal lineage alone did not establish the latest intent. | Only the newest target-date/creation-time allocation intent is considered, including newer proposals outside the prepared-renewal path; ambiguous ties require review. Three initial regression cases failed before repair; coverage also checks three non-prepared newer intents. Existing reconciliation, policy, broker-attempt and approval checks remain. |
| P1 | The candidate reported USD=1 accounting as CNH, manufactured cash as 2% of NAV, reconstructed final quantities from target weights, and supplied empty fill/target arrays. | Explicit USD accounting, initial cash anchor, actual engine cash/quantities/fills, separate adopted and indicative targets, complete allocation and report fields. The report's JavaScript current-state renderer now executes without missing fields. |
| P1 | Monitored calculation bypassed input verification and used a frozen panel/breadth series regardless of newly published data. “Waiting for missing ETF prices” was not a valid explanation for its cutoff. JSON parameters and frozen input identities were absent from calculation revisions. | Verify 58 retained input files and 107 published source receipts, pin the batch, bind inputs/JSON parameters before revision calculation and verify again before publication. Preserve required inputs through an explicit retention pin. Mark this family **Historical only**, with allocation readiness false even if its end date matches a queried historical date. Current signal extension remains unimplemented. |
| P2 | App Rule A differed from its research recipe: alphabetical entry ordering, wrong empty-book parking, and normalization that could refill FR25's defensive cash. Trigger distance omitted cash; the registered universe described 14 rather than 52 ETFs. | Restore the declared entry-score ordering, BIL parking, proportional core weighting, full cash-inclusive L1, explicit 52-ETF membership and final 45% name cap with excess in cash. Implementation revision 1.1.0; frozen fit parameters unchanged. These edge repairs do not change the primary sample's final NAV. |
| P2 | Research metrics omitted the first session by starting returns at the first post-trade NAV. Sortino used the standard deviation of negative returns instead of their lower partial moment. Random-condition controls used a different trigger from the selected candidate. Delayed sizing used the close immediately before execution instead of the original decision close. | Include initial capital/first fill, use downside RMS across all sessions and unregularized Calmar, match random controls at the primary 10% clock, freeze original decision-close reference prices. Recalculate every control at the same costs and delays. |

The old validator merely compared saved artifacts, included a positive-CAGR
check labelled as a Sharpe comparison, and claimed runtime verification it did
not perform. It now recalculates the app module, compares exact NAV/positions,
checks targets to 1e-12, validates the report/holdings contract and explicitly
reports that running-app publication has not been verified.

The prior backup lock separation/stall handling, dashboard invalidation/retry,
14-ETF execution data union and adopted-target repairs passed the focused review
checks. This is not an exhaustive certification of every repository path.

## Frozen experiment

[Protocol](../research/fr25-lifecycle-review-20261020-v1/protocol.json),
[full report](../research/fr25-lifecycle-review-20261020-v1/index.html),
[scenario table](../research/fr25-lifecycle-review-20261020-v1/scenarios.csv),
[results and annual diagnostics](../research/fr25-lifecycle-review-20261020-v1/results.json).

- All 52 supported ETFs, pinned audited batch
  `5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`.
  Adjusted OHLC for returns and audited raw volume for lifecycle signals.
  No provider archives or online price fetches used as research inputs.
- Pre-2023 parameters and breadth threshold 36/52 remain fixed. Period:
  January 3, 2023–October 12, 2026, with December 30, 2022 initial cash anchor.
  The original cohort and previously inspected dates remain development evidence.
- Primary: 80/20 conditional blend with monthly anchors and 10% full L1 target
  trigger. Monthly control and 0/5% trigger sensitivities; no new winner selection.
  Unconditional, three matched random-condition, equal-weight 52 and URTH controls.
- 12 constructions × six frictions = **72 replays**: 5/10/20 bp per side, next
  open and one extra session. Actual traded notional and cost; no annual-cost veto.
- Gate: beat matched FR25 Sharpe, Sortino and Calmar, with drawdown no worse
  and CAGR loss no greater than one percentage point, at all six frictions.
  Annual diagnostics are reported without parameter retuning.

## Results

USD, 5 bp per side; annualized figures:

| Strategy | Extra delay | CAGR | Sharpe | Sortino | Max DD | Calmar | Turnover/year | Cost bp/year |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen FR25 | 0 | 16.51% | 1.450 | 2.125 | -8.65% | 1.907 | 8.69× | 43.47 |
| Conditional dynamic 10% | 0 | 15.85% | 1.459 | 2.133 | -7.64% | 2.075 | 8.80× | 43.98 |
| Conditional monthly | 0 | 15.96% | 1.462 | 2.148 | -8.39% | 1.902 | 8.53× | 42.63 |
| Frozen FR25 | 1 | 15.77% | 1.408 | 2.075 | -8.33% | 1.892 | 8.70× | 43.48 |
| Conditional dynamic 10% | 1 | 14.91% | 1.394 | 2.044 | -8.01% | 1.861 | 8.79× | 43.97 |
| Conditional monthly | 1 | 15.23% | 1.415 | 2.088 | -8.26% | 1.843 | 8.53× | 42.64 |

Primary passes only **2/6 gates**: 5 and 10 bp without extra delay. It fails
Sharpe/Sortino/Calmar at every delayed friction. At 20 bp without extra delay,
Sortino is below matched FR25, superseding the previous “all four risk measures
at all costs” claim. Monthly timing is competitive; it does not establish a
uniformly superior replacement either.

At 5 bp without extra delay, random-condition seeds 7 and 11 have Sharpe
1.466 and 1.462, above the primary's 1.459; seed 23 is 1.425. The earlier
claim that the true condition beats all random controls does not survive
matching the trigger. Three placebos do not provide a significance test.

Annual primary-minus-FR25 Sharpe differences are +0.024 (2023), +0.224 (2024),
-0.051 (2025) and -0.064 (2026 through cutoff). CAGR is lower by 2.80 pp in
2025 and 3.45 pp in annualized 2026-to-cutoff. The small full-period risk
advantage is not chronologically consistent.

The primary's final NAV remains USD 1,738,429.33 and it still has 55 rebalances.
Its corrected CAGR is 15.85%, rather than 16.09%, because the return calculation
now includes the initial capital and first trading session. This is a metric
correction, not evidence that a new fitted parameter improved the strategy.

## Verification and deployment boundary

- Initial review: **170 passed, 2 skipped** across paper renewal, initial
  allocation, market data, strategy execution, dashboard, lifecycle and backup.
- After repairs: **122 passed, 2 skipped** across the changed runtime/execution
  paths and their dependencies; **37 passed** in the added report, lifecycle,
  metrics and readiness checks. Suites overlap; these are not unique-test totals.
- Final renewal/deferred-rebalance check, including newer intents outside the
  prepared path: **48 passed, 1 skipped**.
- Four native Windows LEAN checks: FR25, conditional monthly, conditional
  dynamic, and delayed conditional dynamic at 5 bp. All succeed with **0.00 USD
  maximum NAV difference** against the retest. See
  [native receipts](../research/fr25-lifecycle-review-20261020-v1/native-checks.json).
- Corrected app calculation and offline full report checked against the study;
  [validation](../research/fr25-lifecycle-review-20261020-v1/validation.json).
  The report client-side allocation renderer is exercised without browser/network
  I/O; this is not a visual browser-layout certification.
- Ruff and the documentation link checker pass. No broker requests, policy
  edits, monitoring-membership edits, allocation changes or app restarts were
  performed in this review.

Code is ready for guarded deployment; the running application may still serve
the prior publication. Its restart/republication has **not** been verified.
Current-signal monitoring remains a separate implementation gap: replace the
frozen FR25/breadth series with versioned app-owned daily calculations, preserve
point-in-time source cutoffs, and validate extension/parity before claiming
freshness. Merely extending price arrays is insufficient.

Daily opens do not establish historical 09:30–10:00 TWAP fills. Delay tests
freeze targets/reference prices and rebalance then-held quantities; they do
not simulate queued orders or partial fills. Production execution-clock
claims require separately admitted intraday evidence. No such evidence was
invented here.

## Next decision

The dynamic candidate's delay weakness persists, and its condition does not
beat all matched placebos. Close this fixed candidate's promotion case. Retain
the corrected historical report and existing monitoring membership for operator
review; do not silently archive an operator-added strategy. Do not rescue it
with another threshold search on 2023–2026. The earlier full-pool cash-relative
net retest remains the next separate research-plan item after this report.
