> **Corrected 2026-10-11 after peer review.** Re-run as `var/research/alpha101-tilt-surface-20261011-v2`
> after the alpha 43 and hold-semantics fixes, with the SOTA base now taken from the corrected replay root.
> The verdicts are **unchanged in shape**: X = 10% and X = 20% pass the gate on FR25 and X = 30% upward is
> rejected, with the same monotone cost degradation as the budget rises. Record:
> [alpha101-peer-review-corrections.md](alpha101-peer-review-corrections.md).

# P4.17d — The tilt budget surface: how far the envelope goes

Operator request, 2026-10-11: *also add it to the FR25 strategy and see how much further we can push
the envelope. Raise the budget much higher. Don't worry about the cost first — let's find the optimal
X% tilt.*

Run as its own frozen study in `var/research/alpha101-tilt-surface-20261011-v1/` (protocol `99cd55a8…`):
FR25 (`research_fr25_14_v1`) and the current SOTA, both over the same 70 evaluation decisions
(2021-01-04 to 2026-10-01), monthly family tilt at X ∈ {10%, 20%, 30%, 50%, 75%, 100%, 150%}. Every arm
was replayed regardless of its gate verdict, on the operator's instruction, and the gate verdict and
incremental cost are still recorded for each. Report:
[`research/alpha101-tilt-surface-2026-10-11/index.html`](../research/alpha101-tilt-surface-2026-10-11/index.html).

Research finding only. Nothing here changed a monitored strategy, an allocation, an approval or a
broker record.

## Verdict: there is no higher-X regime, and the tilt saturates at about half of NAV

**FR25** (untouched: 106.0% / 13.37% CAGR / 1.218 Sharpe / 1.545 Calmar / −8.66% maxDD / 41.0bp):

| Declared X | Effective tilt | Total return | CAGR | Sharpe | Calmar | Max DD | Cost |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **untouched** | — | **106.0%** | **13.37%** | **1.218** | 1.545 | −8.66% | 41.0bp |
| 10% | 9.8% | 104.1% | 13.20% | 1.196 | **1.608** | **−8.21%** | 41.7bp |
| 20% | 19.5% | 102.1% | 12.99% | 1.167 | 1.474 | −8.82% | 44.0bp |
| 30% | 28.3% | 99.6% | 12.76% | 1.131 | 1.308 | −9.75% | 46.7bp |
| 50% | 41.4% | 94.9% | 12.29% | 1.059 | 1.105 | −11.12% | 51.7bp |
| 75% | 48.5% | 92.7% | 12.07% | 1.016 | 1.041 | −11.60% | 55.1bp |
| 100% | 50.6% | 95.8% | 12.38% | 1.027 | 1.067 | −11.61% | 56.5bp |
| 150% | **50.7%** | 96.2% | 12.42% | 1.028 | 1.070 | −11.61% | **56.5bp** |

**Raising the budget makes every measure worse, not better, and the tilt saturates.** Beyond a declared
100% the *effective* tilt stops growing — 50.6% at X = 100% and 50.7% at X = 150%, with identical cost to
the tenth of a basis point — because one shrink factor keeps every name inside the 45% cap and above
zero, and a six-name book can only move as much as its smallest weight before a name would go negative.
That is the envelope: **about half of NAV, no matter how much more you declare.**

On the SOTA the shape is the same with a peak at the smallest budget (untouched 76.4% / 0.916; X = 10% →
77.5% / 0.922; X = 50% → 78.2% / 0.885; X = 150% → 82.0% / 0.881 — more return but a worse Sharpe,
Calmar and drawdown, and 56.9bp of cost).

## Cost, measured but not binding by instruction

The gate verdict is recorded for every arm: on both books **X ≤ 20% passes** the 44.0bp ceiling and
**X ≥ 30% is rejected** (FR25: 44.0bp at 20%, 46.7bp at 30%, 56.5bp at 100%; SOTA: 41.8bp at 20%, 45.7bp
at 30%, 56.7bp at 100%). The operator asked to search the performance surface irrespective of cost, so
every arm was replayed anyway — a documented deviation from gate-before-replay, and one that promotes
nothing. It turns out not to matter: the arms above the ceiling are also the ones that degrade the
portfolio.

## No optimal X is declared

The best X by any metric on this surface is an **in-sample maximum on an inspected window**, not an
optimum: FR25's best CAGR, Sharpe and Calmar all sit at X = 10% (and its shallowest drawdown), the SOTA's
at X = 10% for Sharpe and Calmar. Choosing X from this surface would be tuning, and the family-adjusted
contrasts decide: at X = 10% the annualised difference against the untouched book is +0.12% on the SOTA
with an interval spanning zero and Holm p = 1.000 (P4.17c), and FR25's X = 10% arm is slightly *below*
its control on return while slightly better on drawdown.

**The honest recommendation is the smallest budget in the grid, or none at all.** The tilt is a cheap,
nearly neutral overlay; it does not become more valuable when it is made larger, and the cost ceiling
stops it at 20% anyway.

## Verification and limits

Both base books are read, never recomputed — FR25 from the frozen P4.14 Part B root whose FR25 arm
reproduces the published forecasts exactly, and the SOTA from the frozen P4.17c root — and both are
re-checked by hash. Every tilted decision is checked against the zero floor and the cap in the run that
produces it. The window is 2021-01-04 to 2026-10-01 and has already been inspected by P4.13–P4.17, so
nothing here is out-of-sample evidence; the threshold grid is declared; the tilt is applied at the base
book's own monthly decisions; and no promotion, monitoring or allocation change follows.
