# P4.17e — Daily, threshold-triggered tilting: high frequency destroys value

Operator clarification, 2026-10-11: *not the monthly rebalance — monitor daily, and whenever the alpha
signal gives a buy/sell, rebalance X% of the portfolio. High rebalancing frequency to enhance the
return. If cost becomes an issue, control the threshold at which the signal trades, to reduce its
trading frequency.*

Run as its own frozen study in `var/research/alpha101-tilt-daily-20261011-v1/` (protocol `725aa02b…`):
FR25 and the current SOTA over the same 70-month / 1,448-session evaluation window, X ∈ {5%, 10%, 20%}
and a re-tilt threshold of {daily, 50%, 100%, 200%, 300%} of the budget, plus the monthly arm as the
frequency reference. Report:
[`research/alpha101-tilt-daily-2026-10-11/index.html`](../research/alpha101-tilt-daily-2026-10-11/index.html).

Research finding only. Nothing here changed a monitored strategy, an allocation, an approval or a
broker record.

## Verdict: the frequency is the problem, and the threshold that fixes cost undoes the frequency

**Every daily arm is worse than doing nothing, and costs 2–5.5× more.**

| FR25 arm | X | Threshold | Re-tilts | Total return | CAGR | Sharpe | Calmar | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **control** | — | — | 0 | **105.8%** | **13.36%** | **1.214** | 1.549 | 40.9bp |
| daily | 5% | daily | 1,269 | 101.1% | 12.90% | 1.174 | 1.440 | 91.8bp |
| daily | 10% | daily | 1,269 | 96.5% | 12.45% | 1.131 | 1.346 | 142.8bp |
| daily | 20% | daily | 1,269 | **87.6%** | **11.55%** | **1.042** | 1.204 | **243.3bp** |
| wide band | 5% | 200% | 86 | 106.2% | 13.40% | 1.212 | **1.614** | **42.8bp** |
| wide band | 10% | 300% | 64 | 104.9% | 13.27% | 1.204 | 1.598 | 40.9bp |
| **monthly reference** | 10% | monthly | 70 | 104.1% | 13.20% | 1.196 | 1.608 | 41.7bp |

The same ordering holds on the SOTA (control 76.2% / 0.916 Sharpe / 36.7bp; daily 10% → 67.2% / 0.833 /
137.0bp; daily 20% → 59.3% / 0.751 / 235.5bp).

**The threshold works exactly as proposed — and that is the problem.** Raising the re-tilt threshold
from daily to 300% of the budget cuts re-tilts from **1,269 to 64 a year** and cost from **92–243bp to
37–51bp**. But to fit the 44.0bp ceiling the threshold has to be **200–300% of the budget**, and at that
point the arm trades **64–86 times a year — which is the monthly design (70 a year)**. Daily monitoring
behind a wide deadband is the monthly tilt with extra bookkeeping.

## The threshold/cost frontier, and where the ceiling actually sits

| X | Threshold | Re-tilts/year | Cost | Against the 44.0bp ceiling |
| ---: | ---: | ---: | ---: | --- |
| 5% | daily | 1,269 | 91.8bp | 2.1× over |
| 5% | 100% | 671 | 76.3bp | 1.7× over |
| 5% | **200%** | **86** | **42.8bp** | **fits** |
| 10% | daily | 1,269 | 142.8bp | 3.2× over |
| 10% | 100% | 671 | 112.1bp | 2.5× over |
| 10% | 300% | 64 | 41.6bp | fits |
| 20% | daily | 1,269 | 243.3bp | 5.5× over |
| 20% | 300% | 64 | 43.8bp | fits |

Cost is close to linear in both X and frequency, so the ceiling permits roughly **one re-tilt a month at
a 5–10% budget** — not a daily or weekly one. That is the quantitative answer to "control the threshold
to reduce the trading frequency": the threshold that fits the budget is so wide that the frequency
collapses back to monthly.

**A mechanical note on why the wide bands are the monthly design.** The tilt is established on the first session it is computable, and from then on the deadband governs. Because the distance from a zero tilt is only about one budget, a band of a whole budget or more can essentially never open between strategy rebalances, so those arms re-derive the tilt almost only when the base book itself rebalances — which is why their trade counts land on 64–86 a year against the monthly arm's 70.

## Why more frequency makes it worse, not better

The family's information lives at the **21-session horizon** — the P4.17 screen measured 21-session rank
ICs of 0.05–0.075, and the daily arms are re-trading on one-session signal changes that carry almost
none of it. So frequency multiplies the cost linearly while the information per trade falls towards
zero, and the result is a monotone degradation: on FR25 the cumulative return falls 4.7pp at a 5%
budget, 9.3pp at 10% and 18.2pp at 20%. The tilt is not a high-frequency signal, and no threshold makes
it one.

## Nothing is established even where it looks slightly better

Every threshold arm that clears the cost ceiling is **statistically indistinguishable from the
untouched book**: mean annual differences of +0.04%, +0.03%, +0.01% (FR25) and +0.00%, −0.01%, −0.18%
(SOTA) at the 200% threshold, with all 95% intervals spanning zero and **Holm p = 1.000** across each
book's registered family. The best in-sample arm (FR25, X = 5%, threshold 200%) beats the control by
0.4pp of cumulative return and 0.02 of Sharpe — noise, and it is reported as an in-sample maximum
rather than an optimum.

## What this means

1. **The operator's mechanism works; the premise behind it does not.** The threshold is an effective
   frequency and cost control, but there is no frequency regime where this signal pays for the extra
   trading — the cheap configuration is the monthly one already measured in P4.17b–P4.17d.
2. **The tilt family stays where it was**: a monthly, NAV-neutral, family-ranked tilt at 5–10%, worth
   roughly nothing measurable and costing roughly nothing measurable. Nothing here promotes it.
3. **A genuinely higher-frequency use would need a genuinely higher-frequency signal** — one whose
   information is measured at one to five sessions rather than twenty-one. That is a different study
   with a different signal, and the P4.15 gate would have to pass it first.

## Verification

The daily rows are checked against the zero floor and the 45% cap in the run that produces them; the
base books are re-checked by hash against their frozen roots; the tilt arithmetic is the same rule
already covered by the P4.17b/P4.17c tests, and the shared `tilt_vector` refactor that this study
required was proven behaviour-preserving because the earlier frozen artifacts still reproduce exactly.
The alpha cross-sections are computed from audited bars strictly before each session, with every
registered alpha window-bounded by 260 sessions, and are cached in the root so the study is
reproducible.

## Limitations

- **One inspected window**, 2021-01-04 to 2026-10-01; nothing here is out-of-sample evidence.
- **The strategy book is held between its monthly decisions**, so the daily trade flow is the tilt; a
  strategy that also rebalanced daily would trade more.
- **The threshold grid is declared** ({daily, 50, 100, 200, 300}% of the budget) and the best arm is an
  in-sample maximum on that grid.
- **Costs are the parents' 5/10/20bp** with zero and one-session delay; none is re-optimised.
- **No promotion**: the 45% cap, the cash reserve, the cost ceiling and the IC margin are unchanged.
