# Large-loss feedback: useful damage control, an overly restrictive response

Research-only, completed October 26, 2026. The operator asks for a warning after
a single large loss, especially a losing stop, using one sigma of tested gains
as a candidate scale. This study actually resimulates changed trades and portfolio
targets. It preserves the previous market models and their per-ETF training choices.
It does not perform online market-model refits or change any operational strategy.

## Result and interpretation

The extra warning materially reduces WEAT's loss. A blanket pause followed by a
strict four-trade recovery rule sacrifices too much performance elsewhere. Keep
loss severity and stop outcomes as candidate diagnostic features; reject this
exact response as a general replacement. A narrower monthly portfolio-selection
benefit survives both eras/all tested frictions against the matched fixed policy,
but superiority over stronger alternatives is not established.

| Later primary case, net cumulative return | A: existing policy | B: streak feedback | C: plus large-loss/stop warnings |
|---|---:|---:|---:|
| WEAT | -32.51% | -22.45% | -5.36% |
| GLD | +56.69% | +2.32% | +10.66% |
| TLT | -12.48% | -13.63% | -4.22% |
| CORN | -14.19% | -10.09% | -10.66% |
| MCHI | +41.30% | +39.82% | -7.29% |

Primary = 5bp per side and next-open execution. Each ETF starts newly funded and
flat at its evaluation boundary; this differs from the previous experiment's
carried-position accounting. In particular, GLD's prior +58.32% headline is not
this matched baseline. The late ETF period is January 3, 2023–October 16, 2026;
earlier is 2020–2022. All these historical periods were already inspected, so this
is development evidence, not a genuinely unseen prospective test.

## Exact definitions and what was fitted

Freeze the previously training-selected market policy separately for each ETF
and cutoff. Complete all new threshold calibration before running any evaluation.
For its closed training trade net returns r_i, define

`G = {r_i : r_i > 0}`
`sigma_g = sqrt(sum_(g in G)(g - mean(G))^2 / (|G|-1))`.

Require at least five winners. The sigma feature is unavailable for CPER in the
later era and BIL in both eras; do not replace it with another volatility series.
With the evaluation's known one-way cost f, define

`tau = max(sigma_g, 2*f, 1e-6)`
`r_mark,t = (close_t / entry_open) * (1-f)/(1+f) - 1`.

C requests an exit when r_mark,t < -tau, filled at the next permitted open. At
actual close of the trade, a net loss larger than tau, or an exit requested by
that marked-loss condition, pauses new entries and emits a refit-review event.
Other losing protective exits put a normal strategy into defensive mode.
Profitable protective exits do not warn merely because they hit a trailing stop.
The marked-loss event can pause even if the eventual gap fill recovers; the alert
was already observed. No loss is retrospectively removed from the ledger.

This is **loss magnitude relative to dispersion of winning trades**, not a
Gaussian tail probability or a confidence interval. A tightly clustered set of
large winners can have a small sigma. Training-selected returns are in-sample;
the dispersion estimate can be unstable or optimistic. It is a direct, bounded
test of the operator's suggested scale, not a statistically established risk limit.

A uses the existing fitted entry, fast trend exit and protection. B adds the
previous 3/4-loss controller. C adds the two severity/stop features above to B.
Both adaptive policies use the same predetermined defensive response: half risk,
half initial/trailing protection distance, fast-down exit threshold at most0.6.
Adopted protection never loosens. Probation uses quarter risk. Actual position
size is fixed in units until exit, so the strategy is not silently rebalanced daily.

Paused recovery uses the frozen reference strategy's *fresh* entries after the
pause. Four closed reference trades must include at least three winners, positive
sum risk-normalized returns and positive compounded net returns. Then quarter-risk
actual probation requires three trades with at least two winners and positive
totals to recover; two consecutive losses pause again. A refit-review request is
recorded but no new parameters are fitted at that point in this experiment.

Initial and subsequent trade outcomes are measured net per unit of committed
capital. Cutting position size does not make a bad signal look healthy simply
because its contribution to total portfolio P&L became smaller. Cash/share
accounting includes entry/exit costs and next-open or extra-session delay.

## WEAT: the warning arrives earlier, recovery remains too slow

WEAT has13 positive training trades out of32 completed trades. The average winner
is7.25%; winning-return sigma is4.2067%. The old initial protection for its first
trade is about8.38% below entry before fees/gap effects.

The new marked-loss condition fires on January 4, 2023 and fills January 5 at
37.80 adjusted dollars versus39.90 entry. Net loss is5.36%, exceeding the4.21%
threshold because a daily close rule cannot guarantee an exact stop price.
The original first trade exits January 11 for-6.99%; its next trade loses9.01%.
C avoids the second entry after pausing from the first loss.

C has only one actual closed WEAT trade. It spends925 of951 evaluation sessions
paused and recovers to probation only September 15, 2026; no new actual entry
occurs before the evaluation ends. Maximum drawdown drops from35.11% to5.44%,
but Sharpe remains negative (-.658 versus-.619). This is avoidance of repeated
losses, not demonstrated profitable capture of short rebounds. It also misses
opportunities during the long pause. B changes the subsequent trades and ends
at-22.45%; its streak never reaches the same four-loss sequence as the unchanged
ledger, illustrating why the prior warning audit was not an adaptive backtest.

The original January/February exits looking near local lows cannot be used as
contemporaneous evidence that a bottom had formed. Post-exit rebounds may diagnose
lag after those future prices arrive; they cannot justify historical earlier exits
or re-entries at the bottom. The relevant learning questions are stop overshoot,
entry extension, profit giveback, and whether the *future* recovery policy works.

## Full-pool results and preservation

| Evaluation | Policy | Median Sharpe | Median CAGR |
|---|---|---:|---:|
| 2023–2026 | A | .412 | 4.36% |
| 2023–2026 | B | .111 | 0.61% |
| 2023–2026 | C | -.102 | -0.39% |
| 2020–2022 | A | .276 | 2.43% |
| 2020–2022 | B | .242 | 1.76% |
| 2020–2022 | C | -.021 | -0.40% |

Compared with A, C improves cumulative return on9/51 later and19/49 earlier risky
ETFs. Only29.4%/46.9% remain within the declared1pp CAGR and2pp drawdown guards,
versus a90% preservation requirement. Neither B nor C passes the full-pool
acceptance in any of the six friction settings in either era. Median pause fractions
for C are36.3% and38.0%. This broad weakness is not confined to the WEAT example.

GLD pauses after a large loss on May 14, 2025 and returns to probation February 2,
2026, missing much of a strong rise. Failed probation pauses it again March 4.
It ends+10.66% versus A+56.69%. The warning detects a loss, but does not establish
that the long upward opportunity has ended. This supports separating market
context, loss severity and the policy chosen in response.

## Portfolio evidence: one limited positive result

All52 ETFs remain eligible for selection subject to supported coverage. Six
momentum-ranked slots are gated/scaled by the stand-alone theoretical ETF health
path; vacancies and reduced risk go to BIL. These health outcomes are not the
portfolio's actual closed-trade ledger. The later FR25 overlay retains half of
the incumbent allocation and scales the experimental half; paused health does
not liquidate the retained incumbent half. Dynamic target adoption compares the
latest cash-inclusive theoretical target with the last adopted target at10% L1
distance or month end; monthly adoption is the explicit fixed-interval control.

| Primary portfolio | CAGR | Sharpe | Maximum drawdown |
|---|---:|---:|---:|
| Later A, dynamic overlay | 13.18% | 1.352 | 7.48% |
| Later C, dynamic overlay | 10.93% | 1.470 | 5.98% |
| Later FR25 | 16.51% | 1.450 | 8.65% |
| Later A, monthly selection | 6.58% | .511 | 14.84% |
| Later C, monthly selection | 6.10% | .615 | 13.52% |
| Earlier A, monthly selection | 4.75% | .405 | 16.52% |
| Earlier C, monthly selection | 4.24% | .518 | 13.47% |

The dynamic overlay buys risk reduction at a substantial return cost and fails
the1pp CAGR preservation guard versus A. Higher Sharpe than FR25 does not overcome
that evidence. Annual assumed costs fall from66.1bp for A to45.4bp for C in this
case; no absolute annual-cost ceiling is imposed.

Monthly C selection passes Sharpe/return/drawdown guards versus monthly A in both
eras and all six friction settings (12/12 comparisons). That is a useful limited
finding. At the later primary setting it trails B monthly selection (7.72% CAGR,
.625 Sharpe), and it does not consistently beat simple momentum. Earlier simple
monthly momentum earns7.49%/.567 versus C4.24%/.518. Later simple monthly momentum
earns7.79%/.585, offering more return but more drawdown than C. No universal
superiority follows from these comparisons. FR25 remains an empirical comparator.
The six friction settings are correlated perturbations of the same histories,
not six independent confirmations of a trading edge.

## Weakest cases prepared for inspection

The declared primary C rule is fixed for every ETF and applied to that ETF's
training-selected market policy; we do not pick a health rule using evaluation
returns. Among risky ETFs, weakest by net cumulative return:

- Later **EWH**: -20.57%, Sharpe-.888, drawdown22.29%. Four-loss pause January9,
  2024 persists696 sessions; it misses the later recovery. Its winner sigma10.78%
  is wide, so ordinary streak feedback is still the decisive warning in this case.
- Earlier **EWY**: -19.36%, Sharpe-1.061, drawdown19.74%. Large-loss pause February24,
  2020, probation September25 and normal risk January19,2021 show a slow recovery
  after the initial shock; a second pause follows in November2021.

The report opens EWH; its weakest-case button switches to EWY in the early era.
WEAT has its own button. Every supported ETF/era has all three chart choices,
exact date selection, observed raw volume, probabilities, health states, actual
fills, both protection levels and NAV. Four static figures are ready for EWH,
EWY, WEAT and GLD.

## Next hypothesis

Carry severity/stop flags into the accepted multiscale research, but separate
their *measurement* from the action they trigger. Candidate next features are
loss normalized by entry-time planned risk and conditional predicted volatility;
realized stop overshoot; profit giveback; and slow-context interaction. Treat
winning-trade sigma as one diagnostic rather than the sole loss scale.

A modest warning can reduce risk and request a bounded fast-layer/exit refit.
A severe risk-budget breach can pause. Recovery should test the replacement
model's forward predictive performance and context as well as trade outcomes,
without using a calendar timeout or hindsight peak as evidence of restored edge.
The unchanged four-trade shadow requirement demonstrably risks years of inactivity.
Test response/recovery changes separately before adding further market-model
complexity. Do not retune this completed experiment after observing failures.

## Validation and artifacts

Frozen protocol814ecf84e479e300abd093af17e37deb773d344ea207532675aba37c29059ff0.
Per-ETF thresholds sealed before evaluation.1,836 ETF/friction cases,138 portfolio
cases,5/10/20bp per side and0/1 additional-session delay.612 baseline simulations
match the existing engine to8.9e-15 NAV; independent cash/share accounting error
is4.9e-15. Three native Windows LEAN portfolio replays match NAV exactly.
Twenty-nine focused Python tests and all306 offline chart combinations pass;
four figures and seven mathematical equations inspected. Browser-layout
certification is not claimed. Full source/publication hashes remain pinned.

- [Interactive report](../research/loss-feedback-20261026-v1/index.html)
- [All asset results](../research/loss-feedback-20261026-v1/asset-results.json)
- [All portfolio results](../research/loss-feedback-20261026-v1/portfolio-results.json)
- [Calibration](../research/loss-feedback-20261026-v1/calibration.json)
- [Native verification](../research/loss-feedback-20261026-v1/native-checks.json)

Methodological background on accumulated shortfall and estimation uncertainty:
[NIST CUSUM](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm),
[Lo on Sharpe estimation](https://alo.mit.edu/publications/page/18/). Neither source
establishes that one winner-sigma is a suitable trading stop. No external price
series was used as a research input.
