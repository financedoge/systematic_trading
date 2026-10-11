> **Corrected 2026-10-11 after peer review.** This measurement used the defective alpha 43 and the

> **Superseded evidence — 2026-10-11 second review.** Earlier numerical and exit/budget conclusions on this page are historical. The prior repair was incomplete. See [the current review](strategy-review-2026-10-11.md) for the raw-activity, monthly scheduling, funding and matched-payoff fixes, accepted replacement roots, and limits. The old grids have not all been rerun and must not support promotion.

> pre-fix rank IC. The corrected study is `var/research/alpha101-tilt-20261011-v2`: 48 candidates,
> **29 pass / 16 reject / 3 insufficient**, i.e. 12 passing alphas at X = 5%, **11 at X = 10%** (one
> fewer than before) and 6 at X = 20%. The shape of the finding — wide at 5%, slightly narrower at 10%,
> deeply broken at 20% — is unchanged. Record:
> [alpha101-peer-review-corrections.md](alpha101-peer-review-corrections.md).

# P4.17b — Alpha101 as a tactical tilt: the cost/alpha balance

Operator proposal, 2026-10-11, after [P4.17](alpha101-screen-findings.md) closed the family at the
mapping stage: *if the problem is turnover, do not use the alpha to choose the book — use it to
overweight and underweight the holdings we already have. Set aside some X% for that and find the
balance between cost and alpha. Add the alpha to the IC decay monitor; the IC threshold does not
need to be that high.*

Measured as its own frozen study in `var/research/alpha101-tilt-20261011-v1/` (protocol
`1fa318f9…`). Report:
[`research/alpha101-tilt-2026-10-11/index.html`](../research/alpha101-tilt-2026-10-11/index.html).
Pre-registered: the tilt shape, the budget family, the cost test and the information source were
frozen before the measurement ran. **No economics were produced and nothing was replayed** — the
item's own rule is that a candidate is gated before any portfolio work.

Research finding only. Nothing here changed a monitored strategy, an allocation, an approval or a
broker record.

## Verdict: the tilt works where the mapping did not — and 5–10% is the balance

| Budget X | Alphas passing | Incremental turnover | Incremental cost | Worst candidate against 3.65bp headroom | Cap binding |
| --- | ---: | ---: | ---: | ---: | ---: |
| **5%** | **12 of 16** | 0.00× – 0.10× | **0.00bp – 0.48bp** | **13%** | 2% of decisions |
| **10%** | **12 of 16** | 0.00× – 0.34× | 0.00bp – 1.69bp | 46% | 3% of decisions |
| 20% | 5 of 16 | 0.00× – 1.03× | 0.00bp – 5.17bp | **142%** | 7% of decisions |

The monitored book already measures **40.35bp** of traded-notional drag against the published
**44.0bp** ceiling, so a new overlay has **3.65bp a year** of headroom. A 5% monthly tilt uses
**at most 0.48bp of it — 13%** — and most alphas use one to eight percent. P4.17's top-six mappings
needed 44.7bp to 76.5bp; the tilt needs a rounding error.

At **20% the balance breaks the other way**: the worst candidate costs 5.17bp, above the headroom
itself, and only 5 of 16 clear. So the cost/alpha balance the operator asked for sits at
**5–10%**, and at those budgets cost is no longer the binding question at all.

## The breakeven IC collapses, which is why a low threshold is now enough

| | Full mapping (P4.17) | 5% tilt (P4.17b) |
| --- | ---: | ---: |
| Incremental annual turnover | 7.62× – 15.29× | 0.00× – 0.10× |
| Breakeven IC at the frozen 5bp | 0.0061 – 0.0122 | **0.00000 – 0.00008** |
| Observed IC needed to clear the 3× margin | 0.018 – 0.037 | **0.00000 – 0.00023** |

The absolute IC bar falls by **two orders of magnitude** — not because the gate was relaxed (the 3×
margin is applied unchanged) but because the breakeven IC scales with turnover and the tilt barely
trades. That is the operator's intuition, and it is a consequence of the design rather than an
assumption.

## Every alpha at the 5% budget

| Alpha | Incremental cost | Breakeven IC | Observed IC (21) | IC margin | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| 24 | 0.03bp | 0.00000 | +0.0435 | 10,228× | pass |
| 6 | 0.00bp | 0.00000 | +0.0009 | 3,777× | pass |
| 21 | 0.02bp | 0.00000 | +0.0135 | 3,466× | pass |
| **53** | 0.42bp | 0.00007 | **+0.0747** | 1,109× | pass |
| 51 | 0.19bp | 0.00003 | +0.0325 | 1,084× | pass |
| 54 | 0.31bp | 0.00005 | +0.0441 | 899× | pass |
| 49 | 0.29bp | 0.00005 | +0.0411 | 896× | pass |
| **26** | 0.48bp | 0.00008 | **+0.0572** | 745× | pass |
| 46 | 0.30bp | 0.00005 | +0.0355 | 738× | pass |
| 43 | 0.41bp | 0.00007 | +0.0196 | 300× | pass |
| 9 | 0.32bp | 0.00005 | +0.0042 | 83× | pass |
| 35 | 0.29bp | 0.00005 | +0.0014 | 31× | pass |
| 101 | 0.40bp | 0.00006 | **−0.0749** | −1,159× | reject |
| 23 | 0.06bp | 0.00001 | −0.0136 | −1,316× | reject |
| 12 | 0.36bp | 0.00006 | −0.0007 | −13× | reject |
| 7 | — | — | not measurable | — | not judged |

**The three rejections are all information failures, not cost failures.** Alpha 101's tilt points
the wrong way — its 21-session rank IC is −0.0749 with an interval excluding zero — and alphas 23
and 12 are negative too. A long-only tilt of a negative-IC alpha is a short signal, so these fail
the IC test while costing almost nothing, which is exactly the inversion of P4.17's pattern (there,
cost killed everything; here, information decides).

**Alpha 7 remains degenerate** — the paper's dollar-volume-versus-share-volume quirk makes it a
constant, so it cannot rank inside the book either, and it is reported as not judged rather than
passed.

**The 45% cap interaction is modest and measured.** The per-decision shrink factor averages
0.98–1.00 and binds on 2–7% of decisions: a book sitting at the cap cannot be overweighted into, so
the whole tilt shrinks rather than breaching the limit. It is a real constraint, not a blocker, and
it is reported beside every candidate.

## A defect found by the test, fixed before publication

The first version of the rule tilted a *constant* held cross-section on the alphabetical
tie-break — issuing arbitrary overweights — and because such a tilt trades almost nothing, its
incremental cost of 0.00bp then read as a **pass**. That is the same false-pass class the P4.17
screen hit with alpha 7. Two rules were added and frozen in the protocol before publication:

- **A held cross-section with fewer than two distinct values cannot rank**, so it is left untilted
  instead of being tilted on the symbol tie-break.
- **A candidate that never ranked the book, or whose IC cannot be measured, is reported
  *insufficient*** and is never passed on a zero incremental cost.

The correction cannot manufacture a pass: it only reclassifies a candidate that never expressed a
view. Re-measured after the fix, the grid moved from 28 to 29 passes, and the ternary alphas became
*cheaper* (for example alpha 21 at 20% fell from 1.68bp to below the headroom) because days on which
the alpha says nothing about the held book no longer trade.

## What this means for the programme

1. **The operator's design solves the problem P4.17 could not.** Handing the alpha a bounded share
   of NAV, inside a book it does not choose, converts a family that could not pay for itself into
   one where 12 of 16 candidates pass the gate with two orders of magnitude of cost headroom to
   spare.
2. **Cost is no longer the question; information is.** At 5–10% the gate is passed on cost by
   everything with positive information, so the next test is whether the tilt *improves the book*
   once the engine, the existing overlays and the 45% cap are all in the path.
3. **X must not be picked from the outcome.** 5% and 10% both pass 12 of 16, and their difference
   is a cost difference, not a quality difference; 20% is where cost binds. Any performance claim
   must be family-adjusted across the whole declared grid.
4. **Registered next: P4.17c — the tilt replay.** A small declared family — the equal-weight tilt
   composite across the family at 5% and 10% (which avoids selecting on the in-sample ICs), the
   matched untilted control, and the best-*cost* variant — replayed through the engine, with
   family-adjusted intervals, the 45% cap and cash reserve unchanged, and judged on drawdown
   across episodes as well as return. If a tilt is ever monitored it enters the P4.13 decay
   instrumentation like every other signal.

## Verification

12 tests in `tests/test_alpha101_tilt.py` cover the rank scores, NAV-neutrality and the exact
budget spend, the cap and zero-floor shrinks, the refusal to tilt a cross-section with no spread,
the derivation of the headroom from the published ceiling and the monitored drag, the frozen 3×
margin, and — against the frozen artifact — the whole 48-candidate grid with a reason on every
verdict, the 5% cost ceiling of 0.13× headroom, the breakeven collapse below 0.001, the balance
break at 20%, the negative-information rejections, and exact reproduction with every input
re-checked by hash. The monitored drag is asserted against the published 40.4bp, so a wrong arm or
artifact stops the study instead of silently changing the headroom.

## Limitations

- **The ICs are in-sample.** They come from the same inspected window as the P4.17 screen, so a
  passing candidate is a candidate, not evidence of future information.
- **No economics.** Nothing was replayed, so nothing here speaks to return, drawdown or the tilt's
  interaction with the model tilt, relative momentum, USD ridge, activity concentration and the
  final cap — those are replay questions.
- **Monthly re-tilting only.** A daily tilt would cost multiples of this and is not measured here.
- **The base book is the published pooled control.** A different base book would change both the
  turnover and the achievable tilt.
- **X is reported, not chosen.** 5–10% is where the cost test stops binding; the difference between
  them is not a quality finding.
