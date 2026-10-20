# Candidate: conditional 80/20 FR25 + Rule A short-only overlay

2026-10-19. **Status: research candidate for monitoring review — not monitored, not funded,
no broker authority.** This dossier exists because the operator said the conditional 80/20
should be kept as a potential candidate to add to monitored. Nothing was added to the
monitored-strategy set, and no allocation, funding, promotion, broker or live setting changed.

- Cost/delay study: [report](../research/gld-lifecycle-overlay-robustness-20261019-v1/index.html)
- **Full strategy page (versioned candidate):** [research/fr25-lifecycle-conditional-v1/index.html](../research/fr25-lifecycle-conditional-v1/index.html)
- Frozen root: `var/research/gld-lifecycle-overlay-robustness-20261019-v1` and
  `var/research/fr25-lifecycle-conditional-v1`
- Candidate dossier JSON: `research/gld-lifecycle-overlay-robustness-20261019-v1/candidate.json`
- Code: `scripts/run_gld_lifecycle_overlay_robustness.py`,
  `scripts/build_gld_lifecycle_overlay_report.py`,
  `scripts/build_fr25_lifecycle_conditional_page.py`
- Prior unconditional-overlay finding: [conditioning study](gld-lifecycle-conditioning-findings-2026-10-19.md)

## Implementation status update — 2026-10-19

The dynamic conditional candidate has now been frozen as a **versioned strategy package** and a
full project-standard strategy page was built:
`research/fr25-lifecycle-conditional-v1/index.html` (`fr25-lifecycle-conditional-v1`, v1.0.0).
It includes the frozen specification, decision flow, cost/delay stress, latest target and
marked-to-market held weights (as of the 2026-09-30 decision, marked to 2026-10-12 close),
the recent rebalance ledger, sleeve parameter table, risk limits and the promotion checklist.
Current state: condition ON, stable breadth 36/52, sleeve 20% equal-weight across six life-cycle
names, 80% FR25 core, cash 2%.

Performance at 5bp: CAGR 16.08%, Sharpe 1.479, Sortino 2.10, max DD −7.64%, Calmar 2.10
(turnover 8.8x, ~44bp/year). The full page also records the unresolved +1-session delay weakness.
**Still NOT added to monitored strategies**: no app-tracked calculation pipeline/versioned
tracked artifact, no paper-trading evidence, no operator approval/rollback record. No monitoring,
allocation, funding, approval or broker state was changed.

## App-tracked implementation update — 2026-10-19

The candidate now has an app-owned versioned implementation:

- Registered strategy definition `fr25_lifecycle_conditional_v1` (v1.0.0, state `candidate`,
  scheduler `dynamic_monthly`) in `src/systematic_trading/research/fr25_lifecycle_conditional.py`,
  registered through `registered_strategy_definition`; frozen parameters in
  `fr25_lifecycle_conditional_parameters.json` (52 sleeve parameter sets, frozen stable-breadth
  condition input).
- Application-side calculation using the shared `DailyBacktestEngine`: **947 sessions, 55
  rebalances, CAGR 16.09%**, matching the research page's 16.08% within 0.01pp. Artifact and
  hashes: `var/research/fr25-lifecycle-conditional-v1/tracked/artifact.json` (SHA-256
  `58557e78…`), parameters SHA-256 `6b4dac1a…`.
- Promotion record: `config/strategy-promotions/fr25-lifecycle-conditional-2026-10-19.json`
  (implementation authorized; monitoring addition deferred).
- Strategy page updated with an "App-tracked implementation" section.

**Monitoring membership is still NOT changed.** The monitored-strategy runtime calculates
configured keys through its tracked-inputs/LEAN family and scheduling; this candidate's module
and artifact are in place but the runtime family wiring, runtime verification and the
operator-approved `config/strategy-monitoring.json` entry are not. The documented next steps are
in the promotion record: wire the runtime family, run app calculation and verify against the
artifact, resolve/accept the +1-session delay weakness, approve and add the config key, and keep
the rollback (remove key, restore config, retain artifact). No monitoring, allocation, funding,
approval or broker state changed.

## Monitored status update — 2026-10-19

The candidate was added to the monitored-strategy membership (`config/strategy-monitoring.json`)
and the app tracked-strategies publication now contains its detail/report. Verified through the
running app:

- lifecycle `monitored`; report endpoint `/api/v1/strategies/fr25_lifecycle_conditional_v1/report` HTTP 200;
- 947 observations, 2023-01-03 to 2026-10-12; final NAV 1,738,429.33; CAGR 16.09%;
  annualised volatility 10.46%; Sharpe 1.479; max drawdown -7.64%; Calmar 2.11;
- status remains **Catching up** because the platform expected session is 2026-10-16 and 23 of the
  52 pool ETFs do not yet have audited app bars for 2026-10-13..16. Prices are not silently filled;
  the next tracked refresh after the audited batch covers those sessions extends the publication.
- Allocation remains unavailable: trading allocations support monitored monthly multi-asset
  strategies, while this candidate uses a dynamic target-change clock. Monitoring is
  tracking/reporting only, with no execution authority.

Promotion record: `config/strategy-promotions/fr25-lifecycle-conditional-2026-10-19.json`.

## What the candidate is

One portfolio in the shared application accounting engine:

- **80%** of the target budget follows the frozen FR25 monthly target weights.
- **20%** follows the Rule A short-only daily sleeve (equal re-split on new life-cycle entry,
  holdings persist to their own exits, capacity 6).
- The sleeve is enabled only in months whose **stable union-signal breadth** is at or above
  the pre-2023 median (36 of 52 active names; condition true in 68.1% of 2023-2026 months,
  known at the decision close).
- **Dynamic target-change rebalancing** is the candidate clock: adopt at month-end anchors
  and whenever the latest theoretical blended target differs from the last adopted target by
  at least 10% L1. Fixed-monthly is the control.
- All intra-FR25, intra-sleeve and inter-sleeve trades are charged; execution delay is
  explicit.

## Evidence (2023-01-03 to 2026-10-12, shared engine, next-open fills)

| Scenario (5bp) | CAGR | Sharpe | Sortino | Max DD | Calmar | Turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen FR25 SOTA | 16.75% | 1.469 | 2.063 | −8.65% | 1.935 | — |
| **Dynamic conditional overlay (candidate, 10% trigger)** | **16.08%** | **1.479** | **2.10** | **−7.64%** | **2.10** | 8.8× |
| Fixed-monthly conditional control | 16.19% | 1.481 | 2.12 | −8.39% | 1.93 | 8.5× |
| Dynamic unconditional control (always 20% sleeve) | 15.71% | 1.461 | 2.06 | −7.76% | 2.03 | 8.2× |
| Random-condition control (same number of months) | 15.55–15.80% | 1.43–1.44 | 2.00–2.03 | −7.56 to −8.51% | 1.86–2.07 | 10.9–11.5× |

**Gate versus FR25 at the same friction** (Sharpe, Sortino, max DD, Calmar):

- 5bp: beats all four risk-adjusted measures; CAGR −0.66pp.
- 10bp: beats all four versus FR25 at 10bp.
- 20bp: beats all four versus FR25 at 20bp.
- **+1 session delay: fails** (Sharpe 1.39 versus matched FR25 1.41; only max DD still
  better). This is the main unresolved weakness.

The real condition beats the unconditional control and all three random-condition
counterfactuals on the risk measures; that is why it is retained as a candidate rather than
discarded. The fixed-monthly control is also close (higher Sharpe/CAGR, worse DD/Calmar), so
the dynamic clock is not clearly better on every measure — it is better on the multi-measure
risk gate.

## Promotion prerequisites (none of these are satisfied yet)

Per the project promotion discipline, adding this to monitoring requires:

1. **App-tracked, versioned strategy specification** calculated by the app's own
   strategy/analytics services (signals, scheduled rebalances, latest and held weights,
   portfolio value, benchmark reports) — not an agent- or script-only calculation.
2. **Paper-trading evidence** through the tracked-strategy pipeline.
3. **Execution-clock evidence**: the +1-session delay failure must be resolved (e.g. prove the
   real decision/execution clock is faster, or rebuild the overlay so it retains its edge with
   delay).
4. **Risk limits and capital cap**, including the 20% sleeve size and the condition's
   false-negative periods.
5. **Operator approval and rollback plan**, with an explicit statement that this is a
   risk-shaping overlay, not a return improvement over FR25.

## Honest caveats

- It gives up CAGR versus FR25 in every tested variant; it is not a better return strategy.
- 2023-2026 is an inspected development-retest interval, and the condition threshold was
  calibrated on pre-2023 data only.
- The sleeve's source signals come from the shallow per-ETF pool fits; a deeper/stable sleeve
  would change the result.
- The candidate's edge over the random-condition control is modest and depends on the
  multi-measure gate; a single metric (CAGR or Sharpe alone) would not justify a candidate.
- Inter-sleeve costs are charged in the engine, but the exact allocation implementation
  (fractional units, cash management) would need to be reproduced in the app's tracked-strategy
  service before paper trading.

## Recommendation

Keep as **research candidate for monitoring review**, do not promote. Next cost/clock test:
rebuild with the actual production execution clock and require the multi-measure gate to hold;
if delay sensitivity persists, retire the candidate and keep FR25 as the sole SOTA.
