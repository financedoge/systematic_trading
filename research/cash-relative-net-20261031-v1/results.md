# Cash-relative momentum net retest — October 31, 2026

The withheld experiment is complete: cash-relative ranking improves the matched
removal-only control, but does not establish a replacement for FR25. Retain it as
research evidence; no monitoring, promotion, funding or execution changed.

The training-selected policy is **class-first / monthly**. Selection used only
2021–2024, with the predeclared return/drawdown guards; later performance did not
choose the policy. All 16 arms and all six frictions were replayed without a cost
or IC veto. The dynamic 0.10 arm has stronger later performance but weaker earlier
performance; choosing it now would be retrospective tuning.

![Net returns and drawdowns](comparison.png)

| Policy | Period | Return | CAGR | Sharpe | Max DD | Calmar | Turnover/yr |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cash-relative · class/monthly | calibration | 25.28% | 5.82% | 0.590 | 15.78% | 0.369 | 9.150 |
| Removal-only · class/monthly | calibration | 22.61% | 5.24% | 0.565 | 15.04% | 0.349 | 9.095 |
| FR25 · frozen common-input control | calibration | 29.49% | 6.70% | 0.700 | 7.38% | 0.908 | 8.370 |
| Cash-relative · class/monthly | later | 56.36% | 28.80% | 1.474 | 12.36% | 2.330 | 7.757 |
| Removal-only · class/monthly | later | 36.46% | 19.25% | 1.176 | 12.01% | 1.603 | 9.436 |
| FR25 · frozen common-input control | later | 55.80% | 28.54% | 2.072 | 8.31% | 3.436 | 7.726 |

The selected candidate passes the matched-control guards in 3/6
calibration and 6/6 later settings. Against frozen FR25 it passes
0/6 and 0/6 respectively.
Sharpe uses zero cash rate; Calmar is annualized return divided by drawdown magnitude.
Annualization uses 252 sessions. BIL's very high zero-rate Sharpe mostly reflects
bill carry and low volatility; it is neither free arbitrage nor a risk-matched ranking.

## What is being compared

Let r_i be 126-session adjusted return and sigma_i the 63-session annualized
sample volatility. The control ranks r_i/sigma_i with r_i > 0. The candidate ranks
(r_i-r_BIL)/sigma_i and requires both r_i > 0 and r_i-r_BIL > 0. BIL has zero target
in both; unused slots remain literal, zero-interest cash. Class construction takes
three classes and up to two funds per class, with frozen overlap exclusions,
inverse-volatility sizing, 98% maximum gross and 45% name cap.

Daily audited history → prior-session liquidity/duplicate eligibility → fixed
126/63 score → pooled six slots or three-by-two classes → capped theoretical
weights plus cash → monthly adoption or strict L1 target-change > 0.10/0.40/0.80
versus last adopted target → next-open execution → actual fills/cash/held weights/NAV.
No stop-loss, trailing protection or learned exit exists in this recipe.

The historical 52-candidate batch supports 50 complete histories, including BIL
as reference. BWX and CPER remain excluded under the original published identity/
raw-activity contract. All supported risky names participate; this closes the
frozen experiment, not a new expanded-universe test. Audited adjusted prices supply
returns; audited raw close and volume supply liquidity and inspection context.
The original published pool and all 5,698 adoption decisions reproduce; Decimal
distance sums tolerate only 1e-24 rounding, with exact targets/states/decisions.

Primary USD1m accounts start January 4, 2021 and continue through October 12, 2026.
The later window starts January 2, 2025 and retains the pre-existing book. Each
window includes its prior-close NAV. Costs are 5/10/20 bp on actual traded notional;
delay is zero/one additional session. Delayed targets are sized at the close before
execution. Prices use the shared engine's cent rounding and adjusted synthetic
whole units, not broker raw shares.
No terminal liquidation, spread, impact, tax, FX conversion or cash interest.

## Weakest ETF inspection

Criterion: lowest **actual net contribution / opening portfolio NAV**, excluding
cash/BIL/URTH, under the training-selected policy at 5 bp and no extra delay.
This portfolio-specific criterion avoids inventing a standalone ETF return when
allocation capital changes. FIFO trade outcomes reconcile to total net PnL.

### Calibration: EWH, -2.46 percentage points

![EWH dated inspection](weakest-calibration-EWH.png)

### Later: XLE, -1.98 percentage points

![XLE dated inspection](weakest-later-XLE.png)

[All dated trade outcomes](trade-outcomes.csv) · [All constituent attribution](attribution.json).
Charts show adjusted prices and actual fill markers, raw price/volume, adopted
and held weights, net contributions and explicit absence of protection. Discuss
visual observations as hypotheses for a newly declared test, not silent tuning.

## Uncertainty and chronology

Eight paired contrasts use 2,000 circular 21-session block resamples with identical
date draws, seed 20261031. Both unadjusted and Bonferroni family intervals are
reported. These are conditional development diagnostics, not selection-adjusted
discovery tests or an untouched holdout. The reserved prospective design was never
activated; elapsed calendar time cannot create prospective evidence.

- calibration: family-adjusted Sharpe difference [-0.306, 0.328]; CAGR difference [-2.96, 4.24] pp.
- later: family-adjusted Sharpe difference [-0.194, 0.854]; CAGR difference [-1.65, 24.26] pp.

[All annual and friction metrics](results.json) · [All uncertainty intervals](uncertainty.json) · [Annual policy diagnostics](annual-policy-diagnostics.json). Annual winners are descriptive and never replace the frozen policy.

The family-adjusted intervals include zero in both periods. In 2022 and
2023, subtracting bill return actually hurt this monthly policy; the benefit is
concentrated in 2024–2026. Later average risky exposure is 77.99% versus 77.04%
for removal-only, so average exposure alone does not explain the gain; this is
still not a matched-risk experiment. FR25 averages 97.91% exposure later and is
only 32.72% invested in 2022, when its return is +3.28% versus −4.67% for the
selected candidate. Its advantage depends partly on that defensive behavior,
not a universal law about financial-condition models.

Actual selected-policy annual turnover is 9.15x in calibration and 7.76x later,
equivalent to approximately 45.75 and 38.78 bp/year at the 5 bp assumption.
Actual fees total $20,520.91 and $10,279.48, versus $20,387.92 and $11,382.49 for
removal-only. These measured net outcomes replace the old 44 bp rejection.
The 0.10 dynamic candidate improves later Sharpe to 1.902 but earlier Sharpe is
only 0.349; later turnover is 48.94x and fees $65,192.98. Its apparent later
advantage cannot be used to change the training-selected policy.

The original fixed 1/5/10/21-session signal and payoff diagnostics remain
[available in the historical summary](../cash-relative-momentum-20261017-v1/summary.json).
They are explanatory evidence, not substitutes for these net portfolio results.

## Current monitored strategies: context only

The app reports below are USD at their published 5 bp/no-extra-delay convention, rebased on the same January 2, 2025–October 12, 2026 dates. They use their own verified publication vintages, model warmups and inherited holdings. They are not matched same-input causal controls. The frozen FR25 replay above retains its original common-window refit.

| App strategy | Net return | Sharpe | Max DD | Calmar |
| --- | ---: | ---: | ---: | ---: |
| BroadTrend · Full-Pool ETF Trend | 16.39% | 1.580 | 4.49% | 1.998 |
| FR25 80/20 + conditional short life-cycle sleeve | 49.27% | 2.014 | 7.64% | 3.333 |
| Leading + payroll/inflation context · linear model | 54.88% | 2.037 | 8.46% | 3.324 |
| Qualifying defensive ETFs + cash | 54.90% | 2.024 | 8.75% | 3.212 |
| FR25 · 75% M1 / 25% financial ridge | 56.14% | 2.083 | 8.31% | 3.455 |
| FR25 + 5% Alpha101 family tilt | 56.64% | 2.093 | 8.25% | 3.509 |
| M1/14 · faster momentum, 14 candidates | 49.95% | 1.908 | 8.31% | 3.104 |

## Evidence and handoff

[Frozen protocol](protocol.json) · [Input/adoption verification](input-validation.json) ·
[Independent native accounting](native-validation.json) · [Monitored context provenance](monitored-context.json).
Native LEAN verifies orders/fills/cash/NAV for three declared accounting cases;
it does not independently infer the selection policy. Focused tests verify window
anchors, cash metrics, training-only selection, adoption equality and delayed fills.

Current-cohort survivorship, retrospective taxonomy and historical publication
availability remain limitations. The result warrants discussing why bill-relative
ranking helps and where the extra risk comes from. No new parameter search or
monitoring is implied. Stop here for operator discussion. The next queued item is
the separate full-supported-pool study of the six cost-excluded Alpha101 signals.
