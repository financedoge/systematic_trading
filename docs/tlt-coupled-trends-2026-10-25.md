# TLT rebounds and interacting latent trends — 2026-10-25

The operator requested short upswing capture inside TLT's broad decline, learned
slow/fast regimes without fixed trend windows, looser exits during a long uptrend,
and exact date selection in the charts. The completed experiment captures the
late-2023 rebound but does not establish useful long-trend recognition or a robust
strategy improvement. No deployment, monitoring, allocation or broker changes.

- [Interactive case inspection and full pool](../research/coupled-trends-20261025-v1/index.html)
- [Frozen protocol](../research/coupled-trends-20261025-v1/protocol.json)
- [TLT interval/trade/model audit](../research/coupled-trends-20261025-v1/tlt-case-audit.json)
- [Full table](../research/coupled-trends-20261025-v1/full-etf-table.csv)
- [Earlier experiment](multiscale-hmm-research-2026-10-25.md)

## What failed before

TLT's prior selected multiscale model uses 63-session up/down identification and
252-session context; it is a fixed-window volume model, not the HMM comparison.
It has no protective stop. In the declared September 2023–January 2024 interval,
the adjusted close trough is October 19 and the subsequent peak is December 27:
22.63% in hindsight. Fast-up and eligibility first turn true December 14; the
December 15 entry exits March 4, 2024 for a 4.55% net loss. Recognition is late.

The June 27, 2024 entry is timely enough to reach 9.41% unrealized gain at the
September 16 close. The October 30 exit retains only 0.47% net. This is an exit
problem. In the declared June–October interval, the July 1–September 16
trough-to-subsequent-peak rise is 13.45%. These extrema are descriptive diagnostics,
not optimizer targets or evidence that their dates were tradable in advance.

## Frozen experiment

Protocol SHA256:
`80b4e47541b5d047e59805191c56bd0fd622fe7696f04036922c6d8c35d5f25f`.
Pinned published input batch and hashes are inherited and verified through the
parent experiment. Adjusted OHLC is used for returns/fills, separately audited raw
volume for activity. No provider downloads, online prices, missing-value fills or
new data splices. Asset data end October 16; later portfolio data end October 12.

The new model represents two latent factors with down/range/up states, giving
nine joint states. Daily adjusted log return is the price observation; the volume
pair adds daily raw-volume log change. There are no rolling trend features or
fixed observation windows. Return mean is an additive slow plus fast drift with
direction-constrained fitted coefficients; range contribution is zero. Gaussian
variance is shared across states, preventing states from merely becoming
different volatility buckets. This restriction can also be too inflexible.

The coupled transition is
`P(L_t | L_prev, S_prev) × P(S_t | S_prev, L_t)`; the independent control removes
both cross-factor transition dependencies. Exact nine-state forward/backward EM
uses training only. Evaluation signals use forward filtering only. Conditional
stay probabilities are constrained to 0.98–0.999 for slow and 0.65–0.97 for fast.
These are explicit timescale assumptions, corresponding to conditional geometric
durations of 50–1000 and 2.86–33.3 sessions, not arbitrary learned durations or
hard lookback windows. A coupled factor's actual marginal duration need not equal
a single conditional geometric duration. The two factors may be weakly identified.
See the [factorial HMM reference](https://mlg.eng.cam.ac.uk/pub/pdf/GhaJor97a.pdf)
for the underlying multiple-factor representation; our transition coupling and
constraints are the declared experimental design, not a replication of that paper.

Four model fits per ETF/cutoff: independent/coupled × price/volume. EM uses two
initializations and up to 20 iterations, selected by likelihood plus persistence
priors. A training-only TLT smoke check revealed diffuse probabilities before
protocol sealing; the final grid explicitly includes 35%/40%/50% fast-up entry
thresholds. It does not pretend 35% is high confidence. Fast-down thresholds are
35%/50%. Entry also requires positive one-step expected return; slow down never
vetoes a short upswing. Rearm after an exit requires fast-up probability below 35%.

Uniform protection trails peak closes by 2/3/4 training daily return sigmas times
entry price. Context policy doubles the distance and raises the down threshold
to 65% when slow-up probability exceeds 55%. Adopted levels never widen: test the
old level at the close, then update for the next close. Initial protection uses
the actual fill and lagged known context. Fills are at next open or one extra
session, with 5/10/20 bp per side. Stops are not intraday orders or loss guarantees.
This isolation test does not add volatility-spike or volume-spike tightening.

18 matched policy vectors × eight families = 144 candidates per ETF/cutoff;
top two per family undergo all six frictions. Same training utility and
trade/exposure adequacy preference as the parent. Both fitted eras are retained:
train through 2022 / evaluate 2023–October 2026, and train through 2019 / evaluate
2020–2022. There are 52 later and 50 earlier histories, including BIL; both eras
are repeatedly inspected development history, not fresh holdouts. Model fitting
uses the full training period, so training strategy scores are in-sample
calibration rather than rolling model-refit evidence. Preserve carried-position
evaluation semantics from the parent; do not describe this as a fresh-funded
deployment on the evaluation boundary.

All 52 fits were sealed before evaluation. There are 6,120 asset/friction cases,
1,020 primary table rows, 918 selected-policy records and 102 portfolio cases.
Signals SHA256:
`25af75dbdac142e4030685acb6acadeb70a044edb802e32762e650646be6c056`.
The old multiscale training-selected strategy is the matched baseline.

## TLT results

Matched interval returns at 5 bp per side and next-open fills:

| Interval | Prior selected | New selected |
|---|---:|---:|
| September 1, 2023–January 31, 2024 | −2.11% | +9.24% |
| June 3–October 31, 2024 | +0.47% | −0.98% |
| January 3, 2023–October 16, 2026 | −18.53% | −17.81% |

The new training winner is `coupled_uniform_price`, entry 35%, down threshold
35%, trail four daily sigmas. It buys November 3, 2023 at adjusted 78.41665 and
exits January 5, 2024 at 85.75189: +9.24% net. Its peak unrealized gain is 13.90%.
In 2024 it buys June 5, exits July 2 for −2.28%, then buys August 2 and exits
September 26 for +1.33%. Those two trades compound to −0.98%. At July 15 the
fast-up probability is still 32.44%; it reaches 35.41% on August 1, causing the
next-open entry. Removing hard windows does not remove delayed recovery entry.

Full-period Sharpe is −0.596 and max drawdown 25.13%, compared with −0.656 and
20.36% previously. Independent price model return is −15.49%, better than coupled.
The independent model makes the same trades in the two highlighted intervals.

Crucially, neither slow-up nor slow-down probability exceeds 55% on any of TLT's
951 later evaluation sessions. Slow-down probability ranges 23.58–37.75%; fast-up
25.84–40.73%. Total predicted daily return stays positive. The context policy
therefore never activates its looser regime and gives identical TLT trades to
uniform protection. Volume-change emissions also leave the selected TLT trades
unchanged. This does **not** validate the intended long-down/short-up distinction.

## Preservation and portfolio tests

| Later case | Prior selected return | New selected return |
|---|---:|---:|
| GLD | +85.78% | +18.02% |
| CORN | −9.86% | −1.64% |
| EWA | −18.00% | +3.51% |
| MCHI | +7.95% | +24.72% |
| IAT | +11.12% | 0.00% |
| SLV | +24.65% | +1.66% |
| SOXX | +152.05% | +117.27% |

Later selected risky cases: 35/51 positive versus 40/51; median Sharpe 0.3156
versus 0.3188, median CAGR 1.95% versus 2.83%. Earlier: 31/49 positive versus
32/49; median Sharpe 0.2155 versus 0.2139, median CAGR 1.29% versus 1.55%.
Adequate new training evidence exists for 45/51 later and 44/49 earlier risky
fits. All cases remain visible, including low-evidence fits and zero exposure.

No family/friction acceptance gate passes; none of 36 matched portfolio gates
passes. Dynamic selection earns 10.46% CAGR / 0.829 Sharpe later, but −1.51% /
−0.055 earlier. Later dynamic overlay earns 11.35% / 1.401 with 6.15% drawdown,
versus FR25 16.51% / 1.450 with 8.65% drawdown. Its annual cost is 58.81 bp,
versus 43.47 bp for FR25; costs are measured, not capped. The dynamic selector
costs 154.24 bp/year; monthly control 48.62 bp/year. The smaller overlay drawdown
does not justify its return loss under the predeclared guards.

## Verification, inspection and next research

32 focused tests pass, covering transition factorization and persistence bounds,
training-only inference prefix invariance, exact filtering/smoothing reference
paths, delayed next-open execution, countertrend admission, rearming, monotone
protection and independent cash accounting, together with inherited contracts.
All fitted training prefixes/scores reproduce. Maximum independent asset-ledger
relative NAV error is 3.864e-14. All 66 unchanged portfolio controls reproduce
exactly. Three native Windows LEAN comparisons have zero NAV differences.
Ruff passes. Offline report controls cover all 1,040 selectable combinations
(including unavailable histories), 118 charts, exact date inputs, weekend
snapping, two-click selection, copyable interval text and empty periods. Four
static figures are retained; browser layout is not certified.

The previous multiscale report also gains the same date-selection workflow
without changing any frozen strategy, model, fit or result. New later charts
show 2021 onward prices but deliberately hide model states before 2023; earlier
evaluation remains selectable separately. The new report shows signal and fill
dates, protection, forward probabilities, slow drift, expected return and net NAV.

Retain this as a diagnostic failure, not a promotion candidate. The promising
observation is the recoverable 2023 rally; coupling itself has not earned credit.
Next declared hypothesis: a continuous latent slow price slope with uncertainty
(able to express a negative slope flattening toward zero), plus a fast switching
rebound component. Learn adaptation from training, check corridor recognition
and rebound timing directly, then net-return preservation across the full pool.
Do not lower thresholds on these two inspected events or silently retune this run.
