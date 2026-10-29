# Continuous slopes and a fast switching process — 2026-10-26

The operator approved the continuous-slope extension and requested graphs for
every ETF, only two or three main choices, mathematical definitions, and explicit
decoding of the earlier variant names. The October 25 protocol remains frozen;
the run and report were completed October 26. Research only: no operational,
monitoring, funding, promotion or broker changes.

- [Report: three models and all ETF charts](../research/latent-slope-20261025-v1/index.html)
- [Frozen protocol](../research/latent-slope-20261025-v1/protocol.json)
- [Full performance table](../research/latent-slope-20261025-v1/full-etf-table.csv)
- [TLT interval audit](../research/latent-slope-20261025-v1/tlt-case-audit.json)
- [Equations](../research/latent-slope-20261025-v1/equations.json)
- [Previous coupled experiment](tlt-coupled-trends-2026-10-25.md)

## Design and mathematical contract

For each ETF/cutoff, two parallel local-linear filters observe the same adjusted
log close. They are separate estimates of one price, not additive latent factors:

`y_t = log(C_t) = ell_j,t + epsilon_j,t`, `epsilon ~ N(0,R_j)`;
`ell_j,t = ell_j,t-1 + b_j,t-1`;
`b_j,t = b_j,t-1 + zeta_j,t`, `zeta ~ N(0,lambda_j R_j)`.

The forward Kalman recursion uses `F=[[1,1],[0,1]]`, `H=[1,0]`,
`Q=diag(0,lambda R)`, initial mean `(y0,0)` and covariance `R I`.
Profile `R = mean(e_t² / S_t_unit)` over completed training innovations after
252 initialization observations, with floor 1e-12. Optimize log lambda within
slow [1e-10,1e-6] and fast [1e-5,1e-2], including both endpoints. These ranges
identify slow versus fast smoothness. There is no finite rolling trend window,
but fitted noise parameters remain fixed throughout evaluation; this is not
online learning of an arbitrary horizon. Gains settle as covariance converges.

The near-zero slope band is `delta=.02*sigma_r`, where sigma_r is the training
standard deviation of daily log returns. Gaussian direction probabilities are
`P(b<-delta)`, `P(-delta<=b<=delta)` and `P(b>delta)`. Conditional 95% intervals
are `bhat +/- 1.96*sqrt(variance)`, excluding parameter/model uncertainty.

Only three main choices appear in the report:

| Model | Fast direction | Exit policy |
|---|---|---|
| A: continuous slopes | Gaussian fast-slope direction | Uniform |
| B: fast HMM | Three-state HMM of `fast slope / sigma_r` | Uniform |
| C: fast HMM with context | Same HMM as B | Looser during confirmed slow up |

The HMM has Gaussian means down [-2,-.005], range 0, up [.005,2], shared
variance floor .0001, stay probabilities .65–.98, two mean initializations
(.05/.20), 25 EM iterations, and transition pseudocounts 3 on the diagonal plus
.1 everywhere. Select by training likelihood plus prior; evaluation uses exact
forward probabilities. Derived slopes are serially correlated, so these are not
calibrated trading probabilities. This is a two-stage filter/classifier, not a
joint switching-Kalman model.

Buy when armed/flat, fast-up probability reaches .60/.75, and fast slope is
positive. Slow down never vetoes a rebound. Rearm requires fast-up below .50.
Sell on fast-down at .60/.75 or a completed-close protection breach. A range
state alone does not force an exit. C uses down threshold .85 and doubles trail
distance when slow-up probability reaches .70; unknown/down context uses the
ordinary threshold/distance. This is asymmetric tolerance, not a different
entry rule for each long trend.

With actual entry open Oe, training sigma, peak completed close M and ordinary
multiple k0=3/5, `L_next=max(L_old,M-k*sigma*Oe)`. Initial protection uses the
actual fill and signal-day context. Test the adopted level before updating it;
never widen an existing level. No current volatility/volume tightening or
intraday guaranteed stop is added. No new signal uses volume.

Eight paired policy vectors per model, 24 per ETF/cutoff. Retain top two per
model, rescore at all six frictions, prefer >=5 closed training trades and >=5%
exposure, then maximize worst-friction training utility. Same frozen 45/40/15
excess CAGR/Sharpe/regularized Calmar utility, three-block stability and scarcity
penalties as the parent. The report provides the full utility equation, fitting
recursion, actual per-ETF noise values, HMM matrix, means and thresholds.
Policies are refitted separately, so displayed model differences combine the
structural rule change and training selection, not just a matched-policy ablation.

All 52 fits were sealed before evaluation. Two chronologies: train through 2022
/ evaluate January 3, 2023–October 16, 2026, and train through 2019 / evaluate
2020–2022. At least 500 training observations after initialization: 52 later and
50 earlier histories including BIL. All are repeatedly inspected development
history, not new holdouts. Training scores use full-training fitted parameters,
not rolling-refit validation. Preserve the parent's carried-position boundary
semantics, cash-funded fees and idle cash at zero.

Protocol SHA256:
`45065827882125899586431e72b071ceb0cf5d8d919462cd4bbdf1891718c831`.
Signals SHA256:
`184c74e448ff5270d674e56d00e32a5964d7ed2ebe72968989b0f0bcfa857ef8`.
Pinned published adjusted OHLC/raw-volume batch:
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`.
No provider downloads, input substitution or missing-value filling. Volume remains
part of the shared audited input contract, unused by these signals. Historical
membership/publication-vintage and FX limitations remain. Portfolio data end
October 12, asset data October 16; neither is live through the report date.

## Results

All figures below use 5 bp per side and next-open fills. The reference is the
strong earlier multiscale training choice, not the weaker intervening coupled run.

| Later ETF | Earlier return | A | B | C | Training choice |
|---|---:|---:|---:|---:|---|
| TLT | -18.53% | -15.84% | -11.45% | -12.48% | C |
| GLD | +85.78% | +58.32% | +72.15% | +76.60% | A |
| EWA | -18.00% | +3.08% | +18.05% | +23.57% | C |
| MCHI | +7.95% | +8.87% | +41.11% | +52.95% | C |
| IAT | +11.12% | +21.98% | +31.11% | +18.95% | A |
| CORN | -9.86% | -6.12% | -14.16% | -14.19% | C |

| Risky-pool metric | A | B | C | Training choice | Earlier |
|---|---:|---:|---:|---:|---:|
| Later median Sharpe | .374 | .449 | .461 | .461 | .319 |
| Earlier median Sharpe | .340 | .291 | .271 | .236 | .214 |
| Later positive ETFs / 51 | 41 | 40 | 42 | 41 | 40 |
| Earlier positive ETFs / 49 | 35 | 34 | 34 | 32 | 32 |

Every risky fit passes the training trade/exposure adequacy preference. No family
passes the full return/drawdown preservation gate: only 41–59% of later model
fits stay within 1 pp CAGR / 2 pp drawdown guards versus the reference, below 90%.
No model is consistently strongest across both eras. Do not replace training
selection with whichever model subsequently looks best for an ETF.

TLT C uses entry .75, ordinary exit .60 and trail 5 sigmas (10 during slow up).
Full return -12.48%, Sharpe -.340 and DD16.87%, versus -18.53%/-.656/DD20.36%.
B performs better at -11.45%/-.303/DD16.08%. The slow state confirms down on
310 of 951 later sessions and up on 275, versus neither direction ever confirming
in the earlier coupled experiment. It distinguishes contexts, but those labels
are not independently validated regimes or a continuously recognized secular
decline from 2021 onward.

| Declared TLT interval | Earlier | A | B | C |
|---|---:|---:|---:|---:|
| September 2023–January 2024 | -2.11% | +4.41% | +4.67% | +5.12% |
| June–October 2024 | +0.47% | -2.24% | +5.91% | +4.41% |

C's November 6, 2023–January 9, 2024 trade earns +11.59%, but the declared
interval includes a carried August 31–September 22 losing trade (-5.75%).
July 17–September 27, 2024 earns +5.51%; June 7–July 2 loses 1.04%. Full-trade
and matched-interval results answer different questions and must not be confused.
Good rebound capture coexists with 11 losing completed trades out of 16 later.

WEAT is the weakest later training-selected case: B returns -32.51%, Sharpe
-.619, with 10 losses out of 14 closed trades. Gross return already loses 31.56%;
fees add roughly .95 pp cumulative drag. February 15–27, 2023 loses 9.01%
through protection; December 6, 2023–January 19, 2024 loses 7.02% on fast-down.
CORN loses 14.19%, with 8 of 10 completed trades losing and 105 held sessions
in confirmed slow down. These are priority false-upswing/exit-timing cases for
inspection, without inferring that a particular new filter will solve them.

## Portfolio evidence

Same full-pool six-slot momentum/volatility selection and FR25 half/full overlay
as prior work; each ETF uses its training winner among A/B/C. Dynamic membership
and cash-inclusive L1 target-change >=.10 plus month-end overlay adoption are
compared with monthly controls. No annual cost ceiling.

| Later portfolio | CAGR | Sharpe | Max DD | Fees bp/year |
|---|---:|---:|---:|---:|
| FR25 | 16.51% | 1.450 | 8.65% | 43.47 |
| New dynamic selector | 9.44% | .769 | 14.07% | 147.74 |
| New monthly selector | 6.22% | .488 | 14.83% | 53.98 |
| New dynamic overlay | 13.46% | 1.372 | 7.48% | 65.56 |
| New monthly overlay | 13.75% | 1.334 | 8.17% | 48.61 |

Dynamic selection earlier earns 4.64% CAGR/.422 Sharpe versus monthly 4.15%/.362.
Four earlier dynamic-selector gates pass: 5/10 bp with either execution delay.
None of 24 later portfolio gates passes; no both-era/all-friction acceptance.
The overlay's lower drawdown fails to compensate for the lost return under the
declared guardrails.

## What remains unresolved

All 102 slow lambda fits reach the upper bound 1e-6; 100/102 fast fits reach 1e-2.
Calling this unconstrained learned timescale selection would be wrong. R is
fitted, and slopes update continuously, but the speed constraints bind. The
likelihood objective fits price prediction, not an independently defined
long-term corridor. After initialization, gains converge to fixed smoothness.

Before a new experiment, discuss WEAT/CORN false rebounds and whether the slow
state responds too quickly to represent the user's multi-year context. A possible
new design would separate price-level shocks from persistent slope innovations
and assess timescale stability chronologically. This is an inference/hypothesis,
not a proven remedy. Do not silently expand bounds or retune these inspected
TLT events. Keep B/C and the simpler A control visible; no promotion.

## Verification and presentation

3,060 asset/friction cases, 510 primary rows, 408 choice records, 102 portfolio
cases and 306 ETF/era/model charts. Training prefixes and scores reproduce;
independent event-ledger relative NAV error <=2.976e-14. All 612 old asset
controls and 66 old portfolio controls reproduce exactly. Three native Windows
LEAN portfolio replays (overlay delay0/1, selector delay0) have zero NAV difference.
35 focused tests and Ruff pass. Offline Node checks cover all 312 selectable
combinations, 306 charts, parameter tables, date/weekend navigation, two-click
selection, context-only dates, unavailable histories and model-preserving ETF
navigation. Eight static figures and four equation proof sheets were inspected.
Browser layout was not certified because the browser environment blocked local
file access; no alternate access path was used.

The report embeds vector equations, includes each ETF's fitted values and decodes
the prior independent/coupled transition probabilities, uniform/context exit rules,
and price/volume observation distributions. The earlier volume emission has nine
unconstrained joint-state volume means, not additive volume components. No extra
old model selectors appear. The table sorts worst first for the inspected model.
Shared chart arrays are stored once in the HTML and the presentation cache is
compressed; its redundant 122 MB uncompressed file was retired. Frozen models,
fits, inputs, results and operational evidence were preserved.
