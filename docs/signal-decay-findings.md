# P4.13 — Signal decay, IC instrumentation and the decay warning

Findings for the first item of the [signal decay and alpha plan](signal-decay-and-alpha-plan.md).
Completed 2026-10-10. Decision support only: this item changed no monitored
strategy, no allocation, no approval and no broker record.

## What was built

| Piece | Where |
| --- | --- |
| Decay and IC measurement | `research/signal_decay.py` (pure functions) |
| Signal series, job and publication | `research/signal_decay_job.py` |
| Strategy-to-signal join and warning logic | `research/signal_health.py` |
| Read-only API | `GET /api/v1/strategies/signal-decay` |
| Dashboard panel | **Signal decay** at the top of `/strategies` |
| Operator warning | Banner on `/operator`, only when a *funded* strategy is affected |
| Durable alert | `_check_signal_decay` in the analytics readiness loop |

The measurement runs in the analytics research lane as the `signal-decay` job,
after the audited batch and the tracked strategies. It is independent of the
tracked calculation on purpose: a strategy that refuses to compute must not hide
the fact that its signal has decayed.

## Method, and why it is conservative

- **Labels use the executable convention**: next session's adjusted open to the
  open *h* sessions later. The platform decides at the close and fills at the next
  open, so a close-to-close label would credit return the strategy cannot capture.
- **Rank IC** is Spearman's rho across the candidate pool per decision date,
  computed through the platform's own normalised ranks so the diagnostic and the
  strategies agree on what a rank means.
- **Intervals** come from a circular block bootstrap over decision dates at the
  platform's 3/6/12-month blocks. Forward windows overlap at the 21- and
  63-session horizons, so a naive t-statistic would be badly overstated.
- **Breakeven IC** scales the annual cost to the signal's own horizon before
  comparing it with return dispersion, and omits the fundamental law's
  selection-intensity multiplier. It is therefore a conservative gate: clearing it
  is necessary, not sufficient.

## Findings

130 monthly decisions, 2016-01-04 to 2026-10-01, 14 candidates, batch `b02d9372…`,
5bp costs. Measured annual one-way turnover on the top-six selection: **3.97×**
(deliberately measured, not assumed). Forward-return dispersion over 21 sessions:
**5.22%**.

| Signal | Long-run IC | Recent IC | IC IR | Hit | Half-life | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **m1_total** (selection score) | 0.0548 | **0.0943** | 0.13 | 54% | n/a | healthy |
| m1_trend | 0.0473 | 0.0945 | 0.12 | 57% | n/a | healthy |
| m1_volume | 0.0141 | **−0.0110** | 0.04 | 50% | 46d | **decayed** |
| momentum_126 | 0.0242 | 0.0306 | 0.06 | 54% | n/a | healthy |
| momentum_21 | 0.0152 | 0.0434 | 0.04 | 53% | n/a | healthy |
| momentum_63 | 0.0696 | 0.1245 | **0.16** | 52% | n/a | healthy |
| momentum_252 | −0.0159 | 0.0848 | −0.04 | 46% | n/a | healthy |
| realized_vol_63 | 0.0485 | 0.2194 | 0.11 | 58% | 174d | healthy |
| drawdown_252 | −0.0085 | −0.1639 | −0.02 | 45% | n/a | **decayed** |

IC by horizon (mean rank IC):

| Signal | 1 | 5 | 10 | 21 | 63 |
| --- | ---: | ---: | ---: | ---: | ---: |
| m1_total | 0.0548 | 0.0633 | 0.0485 | 0.0560 | 0.0813 |
| m1_trend | 0.0473 | 0.0704 | 0.0610 | 0.0576 | 0.0830 |
| m1_volume | 0.0141 | 0.0025 | −0.0334 | 0.0029 | 0.0026 |
| momentum_63 | 0.0696 | 0.0380 | 0.0255 | 0.0219 | 0.0448 |
| realized_vol_63 | 0.0485 | 0.1005 | 0.0992 | 0.0449 | 0.0585 |

**The headline answer for the funded strategy.** `m1_total`, the score F3
currently depends on and 75% of what M1/14 and FR25 rank on, shows **no decay**.
Its recent 24-decision mean IC (0.0943) is *above* its long-run mean (0.0548).
The concern raised by FR25's concentration in recent selections is therefore not
visible as a loss of ranking power in the M1 component.

**But the interval spans zero.** `m1_total` at the 1-session horizon has a 95%
block-bootstrap interval of **[−0.016, +0.127]** at 3 months, [−0.023, +0.134] at
6 and [−0.023, +0.136] at 12. The point estimate is positive and its sign is
consistent across all five horizons, but with 130 overlapping monthly decisions
this sample cannot establish that the ranking edge is nonzero. That is the honest
reading and it is stated in the published output.

**Two decayed signals.** `m1_volume` — a quarter of the M1 score — has a
long-run IC of 0.0141 and a *negative* recent IC of −0.0110, with the weakest IR
of the family. `drawdown_252` is negative throughout and strongly negative
recently, i.e. the pool's recent drawdown state has been mildly *rewarded*, which
is the opposite of a defensive signal on this mixed pool.

**Cost headroom is large.** At the measured 3.97× turnover the breakeven IC is
**0.0032**, roughly 17× below the observed `m1_total` long-run IC of 0.055. On
this pool the current selection signal is not remotely cost-constrained.

## What this means for the Alpha101 plan

The same gate applied to Alpha101's own turnover numbers, from Appendix A of the
plan, with the same dispersion:

| Turnover | Breakeven IC |
| ---: | ---: |
| Current strategy, 3.97× measured | 0.0032 |
| Alpha101 median, ~120× | **0.1000** |
| Alpha101 fastest, ~404× | **0.3367** |

The best IR in this study is `momentum_63` at 0.16 with a mean IC of 0.070. A
formulaic alpha at median turnover would need an IC of **0.10** — above every
signal measured here, and far above what a cross-sectional alpha can plausibly
deliver on a 14-asset mixed pool. P4.15's gate is therefore no longer a
formality; it is the thing that decides whether P4.17 is viable at all.

## Coverage gaps, published not hidden

Four signals the strategies consume are **not** measured yet, because their
per-decision values are not published and reproducing them means re-running the
frozen monthly model schedules: `financial_ridge_forecast` (FR25),
`context_ridge_forecast` (CR), `rolling_xgboost_forecast`, `usd_ridge_forecast`.
They appear in the API response, in the panel footer and in this report. The
consequence is concrete: **the FR25 warning currently rests on the M1 component
only, not on its financial ridge.** Closing this is the obvious next increment of
P4.13 and is required before the warning can be called complete for FR25 and CR.

## Limitations carried in the published output

- IC uses forward returns as labels; it is a diagnostic, not a tradable signal.
- Overlapping forward windows invalidate naive t-statistics; block bootstrap only.
- A 14-asset pool makes each single-date rank IC coarse, so the average is the
  finding and dispersion is published beside it.
- **The pool mixes asset classes**, so a cross-sectional rank partly measures
  asset-class differences rather than selection skill within a homogeneous
  universe. This is the same caveat raised against applying Alpha101
  cross-sectionally here, and it applies to our own numbers too.
- `half_life_sessions` is null when the IC curve does not decline monotonically,
  which means "no decay detected in this window", not "very long half-life".
- Historical inputs are revised provider vintages; historical publication
  availability is not certified.

## Verification

29 focused tests in `tests/test_signal_decay.py` cover the IC maths, tie and
minimum-name handling, forward-return alignment and unobserved windows, the block
bootstrap including missing dates, half-life edge cases, the cost scaling in
`breakeven_ic`, all four status branches, the funding join, warning gating,
coverage-gap reporting, route ordering ahead of `/strategies/{id}`, panel/script
element-id agreement, and the graceful skip before any audited batch exists. A
wide regression batch over the strategy, API, UI, recorder and governed-refresh
suites passes. Node is not installed on this machine, so the repository's `.cjs`
browser checks are skipped here; the panel and alert were verified by asserting
the served HTML from the live application and by the element-id agreement test.

One integration fault was found and fixed by that regression batch: the job
originally raised `M1/14 requires published audited histories` into the research
lane when nothing had been published yet. A diagnostic must not add a failure mode
to the lane, so it now skips quietly in that case and still raises on any other
error.

## A side effect worth knowing

`calculation_code_hashes()` (derived in the earlier hardening item) covers every
module under `research/`. Putting the decay diagnostic there therefore means **a
pure diagnostic edit changes the strategy calculation revision and forces a full
recalculation of all monitored strategies** — roughly ten minutes of CPU for a
change that cannot affect a single strategy number.

This is the conservative direction of the fix (wider coverage, never narrower), so
it is not a correctness problem, but it is a real cost. Options if it becomes
annoying: move diagnostics to a package outside the calculation set, or narrow
`CALCULATION_PACKAGES` to the modules the calculations actually import. Both
reduce the safety margin, so neither should be done without deciding it
deliberately. Recorded here rather than acted on.
