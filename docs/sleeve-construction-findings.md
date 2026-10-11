# P4.16 — Sleeve-aware construction

Does selecting within asset-class sleeves beat the pooled top-six over fourteen
heterogeneous instruments? Run as its own frozen study in
`var/research/sleeve-construction-20261010-v1/` (protocol SHA-256 `dc73d46d…`),
completed 2026-10-10. Every candidate was screened by the
[P4.15 turnover gate](turnover-gate.md) **before** any replay.

Report: [`research/sleeve-construction-2026-10-10/index.html`](../research/sleeve-construction-2026-10-10/index.html).

Research finding only. Nothing here changed a monitored strategy, an allocation, an
approval or a broker record.

## Verdict: inconclusive, with a directional result and a larger structural finding

| Frozen arm | CAGR | Sharpe | Calmar | Max DD | Turnover | Cost | Mean invested |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **CP** — published pooled control | 11.92% | **1.106** | **1.435** | **−8.31%** | 8.59× | 43.0bp | 86.6% |
| **POOL** — construction-matched pooled control | 9.50% | 0.754 | 0.455 | −20.89% | 9.05× | 45.3bp | 95.0% |
| **SLV-COMP** — within-sleeve, composition budgets | 10.89% | 0.792 | 0.697 | −15.64% | 9.24× | 46.2bp | 90.9% |
| **SLV-EQ** — within-sleeve, equal budgets | **12.00%** | 0.983 | 0.705 | −17.02% | 6.64× | 33.2bp | 93.0% |

Evaluation window from fresh cash, 5bp, zero delay. **No contrast clears the
family-adjusted interval**: all six registered contrasts have 95% intervals spanning
zero at 3, 6 and 12 months, with Holm p = 1.000 (the intervals are wide relative to
the differences, and the family adjustment is conservative). The bootstrap reports
**annualised mean monthly differences** — +1.38% for the composition arm and +2.13%
for the equal-budget arm — which differ slightly from the CAGR differences quoted here
because one is an arithmetic mean of monthly differences and the other is compounded.

So the honest answer to the plan's question is: **within-sleeve selection with sleeve
budgets is directionally better than pooled selection *under a matched
construction* — +1.39pp (composition) and +2.50pp (equal budgets) of CAGR with 5.2pp
and 3.9pp less maximum drawdown — but this sample cannot distinguish it from noise.**

## The larger finding: the published control's edge is its fallback, not its pooling

The construction-matched pooled arm makes **the same decision on 119 of 130 days** as
the published pooled control, and the 11 differences are *all* defensive-fallback days
(11 membership differences, **zero** weight-only differences). Because the two books
are otherwise identical, the entire performance gap between them is that one contract:

| | CP (fallback on) | POOL (fallback off) | Difference |
| --- | ---: | ---: | ---: |
| CAGR | 11.92% | 9.50% | **+2.42pp** |
| Max drawdown | −8.31% | −20.89% | **+12.58pp of protection** |
| Mean invested | 86.6% | 95.0% | −8.4pp |

The published control spends about 8% of the window in its defensive
IEF/TLT/GLD-or-cash state, and that is worth more to its risk profile than the pooling
it is usually credited with. The monitored strategy's risk control lives in its
**fallback rule**, not in its selection rule. The sleeve arms sit between the two,
because an unfilled sleeve budget also stays in cash — they recover part of the
protection automatically but not all of it.

### But that value is one bear market, and it was negative before it

Tiling the full-window replay at the 11 differing decisions attributes the whole gap
exactly (the tiles telescope to 100% of the +11.51 log-point full-window difference).
Reproduce with `scripts/analyze_fallback_episodes.py`; receipt in
`var/research/sleeve-construction-20261010-v1/followup/fallback-episodes.json`.

| Fallback decision | Runs to | Sessions | CP − POOL | CP return | POOL return | SPY | CP held |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2016-01-04 | 2018-07-02 | 628 | −0.72 | +26.95% | +27.87% | +42.03% | IEF+TLT |
| 2018-07-02 | 2018-11-01 | 86 | −1.54 | −4.23% | −2.75% | +1.06% | **cash** |
| 2018-11-01 | 2018-12-03 | 21 | −0.49 | +0.25% | +0.74% | +2.12% | IEF |
| 2018-12-03 | 2022-03-01 | 815 | +0.57 | +41.57% | +40.77% | +62.87% | IEF |
| 2022-03-01 | 2022-06-01 | 64 | **−2.92** | +1.44% | +4.45% | −4.45% | GLD |
| **2022-06-01** | **2022-07-01** | **21** | **+8.94** | −0.26% | **−8.79%** | −6.52% | GLD |
| 2022-07-01 | 2022-08-01 | 20 | +0.31 | 0.00% | −0.31% | +7.75% | cash |
| 2022-08-01 | 2022-09-01 | 23 | −0.27 | 0.00% | +0.27% | −3.49% | cash |
| 2022-09-01 | 2022-11-01 | 42 | +3.49 | 0.00% | −3.43% | −2.60% | cash |
| 2022-11-01 | 2022-12-01 | 21 | +0.18 | 0.00% | −0.18% | +5.95% | cash |
| 2022-12-01 | 2026-10-08 | 965 | +3.96 | +70.19% | +63.58% | +100.10% | cash |

**All four pre-2021 episodes are net negative: −2.18 log points over five years. All
seven evaluation-window episodes are 2022, totalling +13.69.** Of that, **+8.94 comes
from a single month** (June 2022: the fallback held GLD while the diversified book fell
8.79%), and a further +3.96 is the compounding tail of the 2022 divergence rather than
a fresh decision.

So the honest reading of "+2.42pp CAGR and 12.58pp of drawdown protection" is that it is
a **one-episode statistic from one bear market**, not a property that has been
demonstrated across regimes. In 2022 the rule was also mixed: it de-risked into GLD too
early and **lost 2.92pp** in March–June before the June–July episode paid for it many
times over, and it flickered in and out of cash month by month through the second half
of the year. Before 2022 it cost 2.18pp, including a month in which a defensive IEF-only
book made +0.25% while the diversified arm made +0.74%.

This is evidence *for* the timing intuition rather than against it, with one refinement:
the rule does not call tops and bottoms — it responds mechanically to **momentum
breadth** (fewer than four of fourteen names above their 126-session momentum) — but it
still exits after prices have turned and re-enters after they have recovered, so whether
it helps depends on whether a breadth breakdown is followed by further declines (2022:
yes, dramatically) or by a quick recovery (2018: no). **A single realisation cannot
establish that, and this study should not be read as having done so.** The drawdown
figure is the part most likely to survive: it is a property of not being invested during
a decline, which does not require forecasting one.

This also retroactively confirms that P4.14's FR25-versus-CP contrast was unaffected:
both of those arms share the same fallback, so that comparison never mixed the two.

## What sleeve budgets actually do

Sleeve budgets force representation, and the effect is stark for the single-instrument
sleeves. Over the 70 evaluation decisions:

| Instrument | Sleeve | SLV-COMP held | POOL held |
| --- | --- | ---: | ---: |
| DBC | commodity | **70 / 70** | 36 / 70 |
| GLD | gold | **70 / 70** | 36 / 70 |
| HYG | fixed income | 48 / 70 | 24 / 70 |
| XLE | equity | 29 / 70 | 40 / 70 |
| SPY | equity | 24 / 70 | 46 / 70 |

`DBC` and `GLD` are held at **every** evaluation decision under composition budgets,
because each is the only instrument in its sleeve and its 126-session gate passed
throughout. "Within-sleeve selection" is therefore, for two of the four sleeves,
not selection at all: it is permanent allocation. That is the mechanism under test and
it is reported as such.

Realised sleeve shares are not the budgets. The budgets constrain **selection**; the
downstream overlays and the adaptive-trend exposure move composition and gross
afterwards, so SLV-COMP's realised mean weights are equity 58.0%, fixed income 20.3%,
commodity 6.3%, gold 6.4% against declared budgets of 57.1/28.6/7.1/7.1% of the
incoming gross. Fixed income runs below its budget because its names frequently fail
the positive-momentum gate and the unfilled share stays in cash.

## The P4.15 gate, applied before any replay

| Arm | Implied turnover | Implied annual cost | Breakeven IC | IC margin | Gate verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| POOL (control) | 9.18× | 45.9bp | 0.00733 | 12.86× | reject — control, replayed anyway |
| **SLV-COMP** | 9.35× | **46.8bp** | 0.00747 | 12.63× | **reject — boundary case, replayed** |
| **SLV-EQ** | 6.80× | **34.0bp** | 0.00543 | 17.37× | pass |
| CP (reference) | 8.72× | 43.6bp | 0.00696 | 13.54× | pass |
| M1 (reference) | 8.75× | 43.7bp | 0.00698 | 13.50× | pass |

The gate did its job: the composition-budget arm costs **6% more than the ceiling**,
because forcing a commodity and a gold name in and out of the book creates churn the
pooled control never pays. It was replayed as a **boundary case** under P4.15's own
published rule — "a candidate within a few percent of the ceiling must be replayed
before a decision is taken" — with the gate verdict recorded unchanged. The equal-budget
arm is *cheaper* than everything else, including the pooled control, because unfilled
sleeves stay in cash.

The dispersion is this study's own recomputation (0.052190 over 21 sessions) and
matches the published P4.15 calibration exactly, so the two items provably share one
input definition.

## What this means for the programme

1. **The premise question is answered with a qualified no.** On this universe, pooled
   selection is not shown to be worse than within-sleeve selection, and within-sleeve
   selection is not shown to be better. The pooled cross-section is therefore an
   acceptable construction — but the test could not establish an advantage either way,
   which is itself the answer P4.17 needed.
2. **Where a sleeve-aware construction *does* differ is cost and representation, not
   information.** Composition budgets buy permanent DBC/GLD exposure and pay 6% more
   than the ceiling for it; equal budgets cut turnover by a quarter and let the
   defensive dimension do the work.
3. **The defensive/cash dimension dominates the partition dimension.** A 2.4pp CAGR and
   12.6pp drawdown gap is attributable to the fallback contract alone, while the entire
   sleeve-vs-pooled question moves CAGR by 1.4–2.5pp with intervals spanning zero.
   Any future construction work should treat the fallback and exposure rule as the
   first-order object, not the cross-section.
4. **P4.17 should not expect construction to rescue a weak signal.** If a sleeve
   partition — a large, structural change — cannot produce a family-adjusted
   difference here, an additional selection feature faces the same noise floor.

## Verification

17 focused tests in `tests/test_sleeve_construction.py` cover the frozen plan (the
four-way partition of all fourteen instruments exactly once, the budget derivations,
the declared slot rule bounded by sleeve size, the overlay's pooled parameters), the
registered six-contrast family, the job matrix, every verdict branch including the
family-adjusted interval requirement and the exact-zero boundary, the frozen gate
record, the construction-matched parity check (11 differences, all fallback days, zero
weight-only), and every frozen decision's cap, long-only and per-sleeve slot contract.
Ruff passes.

Three faults were found by running the study rather than by reading it: the parity
check compared target weights as strings, so decimal spellings of zero were misreported
as 89 changed decisions instead of 11; the defensive-fallback classifier tested the
subset relation the wrong way round and counted zero fallback days; and the first test
of the sleeve contract asserted realised weights stay inside the budgets, when the
budgets constrain selection and the downstream overlays legitimately move weights
afterwards.

## Limitations

- **Nothing here is out-of-sample evidence.** The evaluation window was already
  inspected when the pooled control was chosen.
- **The sleeve map is a modelling choice**, not an observed taxonomy. XLE and XLB are
  sector equity inside the equity sleeve; DBC and GLD are single-instrument sleeves,
  which makes their "selection" permanent.
- **Breadth is matched but not identical across the family**: the pooled arm may hold
  six names, the sleeve arms may hold two per sleeve (six in practice, because the
  single-instrument sleeves cannot fill their second slot).
- **The construction-matched control is not the published control.** POOL differs from
  CP in its fallback contract on 11 days, and that difference is large. The primary
  contrast is measured against POOL for that reason; the CP contrasts are reported but
  carry the fallback difference with them.
- **Cost, delay, currency and cash treatment are inherited from the parent study** and
  were not re-optimised. No threshold grid and no parameter search was run.
- **A reject is a research finding.** It does not deallocate, and switching remains an
  operator decision through the existing allocation workflow.
