# Trading costs and information diagnostics

## Current policy — October 17, 2026

The operator retired the **44 bp annual-cost ceiling**. Additional trading cost
is acceptable when additional return pays for it. Compare the candidate with its
matched control after costs, using net Sharpe, return/drawdown guards, actual
traded notional, fee/slippage and execution-delay sensitivity, and chronological
robustness. No absolute-cost filter may remove a candidate or its comparison arm.
IC/breakeven margins remain visible diagnostics; they cannot establish portfolio
profitability or replace a net replay. A positive net difference alone does not
establish robustness or confer promotion/execution authority.

`turnover_gate.screen` now returns `requires_replay` for complete diagnostics,
with no cost ceiling and no automatic strategy pass. Missing IC/dispersion stays
`insufficient`; another signal's IC is never substituted. `legacy_screen` retains
the original arithmetic only for reproducing dated experiments. Existing legacy
study modules explicitly use that entry point; do not reuse their admission rules
in a new study. Historical results and registered thresholds remain unchanged.

See the [rejection audit and reopened research](research-cost-policy-review-2026-10-17.md).

## Historical P4.15 contract — superseded

The following was the original pre-test for later research items in the
[signal decay and alpha plan](signal-decay-and-alpha-plan.md). Registered
2026-10-10, implemented in `src/systematic_trading/research/turnover_gate.py`, and
consumed as a library — an item that cannot state its turnover, its IC and its
dispersion has not answered the first question the programme asks.

**The question.** For a candidate overlay: how much turnover does the mapping imply,
what does it cost at the frozen 5bp, and what IC must the signal earn to survive it?

**Published result and calibration:**
[report](../research/turnover-gate-2026-10-10/index.html) ·
[calibration artifact](../var/research/turnover-gate-20261010-v1/calibration.json).

## Frozen thresholds

Declared before the calibration was run and not revised after it.

| Setting | Frozen value | Why |
| --- | --- | --- |
| Cost per traded dollar | **5bp** | the frozen cost of every parent study, so gate results are comparable with published replays |
| Cost ceiling | **40bp** annual drag (+10% tolerance → 44bp) | the monitored strategy measures 40.4bp of traded-notional drag, so a new overlay must not be more expensive than the book it would sit on |
| IC margin | **3×** the breakeven IC | `breakeven_ic` deliberately omits the selection-intensity multiplier and ignores estimation error; the monitored signal clears it by ~15× and the Alpha101 archetypes do not clear it at all |
| Dispersion | **21-session** forward-return dispersion, supplied by the caller | measured by the app's own decay code; a missing dispersion is reported as *insufficient*, never as a pass |

Two tests, both required: the annual cost must stay inside the ceiling **and** the IC
must clear the margin. A candidate that fails either is rejected, and the reason is
recorded.

## Two turnover conventions, and which one a figure uses

They are not interchangeable, and mixing them overstates cost headroom:

| Convention | What it counts | FR25, measured | Annual cost at 5bp | Used for |
| --- | --- | ---: | ---: | --- |
| **Traded notional / NAV** | every traded dollar over pre-trade NAV, annualised (`momentum_analysis.statistics`) | **8.07×** | **40.4bp** | this gate, and the plan's "~8× turnover, ~40bp drag" |
| **Selection-change proxy** | the share of the top-slot set replaced per decision, annualised (`signal_decay_job.turnover_and_sigma`) | **3.97×** | 19.8bp | decay gating in P4.13, which therefore overstates cost headroom |

The gate uses the first, because it is what the cost is actually charged on. The
second is a decay diagnostic. Both are reported side by side in the gate report.

## The implied mapping, and its calibration

`implied_turnover(weights_by_decision)` charges every target change, with the first
decision charged as establishing the book from cash. Measured against **217** frozen
replays from P4.14:

- median measured / implied **0.9854**, interquartile range 0.9843–0.9861, full range
  0.9653–0.9886;
- the implied number is conservative in **every** replay — it overstates turnover by
  1.1–3.5%, because the engine trades to targets only in whole adjusted units and
  beyond its target tolerance, so sub-threshold target changes never trade while the
  mapping still counts them;
- at the 44bp ceiling the raw implied number produced **zero false passes** across the
  217 replays, while applying the median ratio as a correction would have admitted one
  that the measured replay rejects.

**Therefore the screening basis is the raw implied value, with no correction factor.**
Erring 1–3% on the expensive side is the right direction for a cost gate. The 31
conservative rejections this produces are all arms measuring 43–44bp — the existing
book sitting on its own ceiling — so the gate does not discriminate *within* the
existing family. Its job is to stop candidates multiples above it, which it does.

## Registered candidate verdicts

| Candidate | Annual turnover | Cost at 5bp | Breakeven IC | IC margin | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Alpha101 fastest archetype | 404× | 2,020bp | 0.3225 | 0.29× | **reject** |
| Alpha101 median archetype | 120× | 600bp | 0.0958 | 0.98× | **reject** |
| Alpha101 slowest archetype | 40× | 200bp | 0.0319 | 2.95× | **reject** |
| Monitored strategy (FR25) | 8.07× | 40.4bp | 0.0064 | 14.64× | pass |

The three archetypes come from the plan's Appendix A and are rejected on the cost
ceiling by roughly 5×, 14× and 46×. The slowest also misses the margin, but the cost
test alone decides it, so the gate does not rest on the margin threshold.

## Usage contract for later items

```python
from systematic_trading.research import turnover_gate

mapping = {day: turnover_gate.weights_from_targets(row["targets"]) for day, row in decisions.items()}
implied = turnover_gate.implied_turnover(mapping)["annual_turnover"]
verdict = turnover_gate.screen(implied, sigma=measured_dispersion, candidate_ic=measured_ic)
```

1. **P4.16, P4.17, P4.18 and P4.19 must call the gate and report its output before any
   portfolio result is produced.**
2. Use the implied value directly — no correction factor, by measurement.
3. Supply the candidate's own measured IC where one exists; otherwise the gate uses
   `PROGRAMME_REFERENCE_IC` (the best IC this programme has measured, 0.0943), which
   judges an unspecified candidate generously rather than strictly.
4. A candidate within a few percent of the ceiling must be replayed before a decision
   is taken, because the implied/measured gap is small but not zero.
5. Keep one cost definition: the gate delegates to `signal_decay.breakeven_ic`. Do not
   re-derive it.
6. An item may proceed after a reject only by changing the candidate so that it clears
   the gate, and must say so explicitly.

## What the gate does not do

- It says nothing about signal quality, capacity, or whether the edge that exists is
  worth the cost. Clearing it is **necessary and not sufficient**.
- It is calibrated on monthly-decision, daily-rebalanced, long-only ETF portfolios. A
  daily or intraday candidate sits outside that population, and for those the
  assumption that every target change trades is weaker rather than stronger.
- It is a screen, not a promotion gate, and it changes no monitored strategy,
  allocation, approval or broker record.

## Verification

23 focused tests in `tests/test_turnover_gate.py` cover the mapping arithmetic
(establishing charge, full switch, unusable calendars, negative and non-finite
weights, the two-times-NAV guard), the cost and breakeven delegation, every verdict
branch including the cost tolerance and the insufficient-dispersion case, the
calibration direction test, the registered archetypes, and re-verification of the
published calibration against its acceptance hash. The published verdicts are
recomputed from the recorded dispersion in the test suite, so the report cannot drift
from the artifact.
