# Multiscale trends, adaptive horizons and HMM regimes — October 25, 2026

[Full ETF report and charts](../research/multiscale-modes-20261025-v1/index.html)
· [Frozen protocol](../research/multiscale-modes-20261025-v1/protocol.json)
· [Prior case audit](../research/multiscale-modes-20261025-v1/parent-case-audit.json)

## Operator questions and prior-case diagnosis

The operator requested inspection of GLD's 2026 missed reversal, long/short
context for CORN's decline, adaptive windows and tighter volatility/volume-aware
protection for EWA, and missing TLT/MCHI charts. During implementation they added
hidden Markov modelling of the fast/slow trend process. The HMM comparison was
added before the new protocol was sealed or any new candidate fitting began.
The prior strategy is unchanged; its presentation now has 11 charts, including
GLD short and both TLT/MCHI domains.

- GLD long uses a 126-session down detector. Its down-strength threshold first
  passes June 10, 2026, not in Q1. Quality >=0.4, negative volume pressure,
  activity >=1.1 and three consecutive confirmations never align in 2026 through
  October 16. March 31 still has an upward 126-session slope; June 30 quality is
  only 0.314 and activity 0.991. The retained up label persists. GLD short
  separately confirms down April 30; it is not the same failure.
- CORN short uses up/down/range windows 21/10/42. Its long fit stays flat during
  evaluation. The short fit buys local rallies inside the broad decline.
- EWA's 21-session window identifies range; up uses 10 and down 42. The previous
  model has no independent stop-loss. Four of five exits with complete subsequent
  21-session history are followed by gains. That future diagnostic is excluded
  from model inputs.
- TLT short has 11 closed trades, six followed by positive 21-session returns.
  MCHI short also has 11, only two followed by such rebounds. Failed entries and
  lagging exits are distinct mechanisms; no universal local-bottom claim.

## Frozen experiment

Protocol hash:
`60ef669a458665a043b5d790b24fe1dd440a1352b7b7d84957d87420f2e9a86b`.
The same published adjusted OHLC/audited raw-volume batch and input hashes are
verified through the prior protocols. No downloaded prices or source substitutions.
Historical membership/vintage limitations remain. Assets end October 16, portfolios
October 12. USD adjusted-unit research, no FX claim.

One combined strategy per ETF replaces separate short/long result domains:

1. Fixed multiscale: fit fast 10/21/42/63 and slow 63/126/189/252 sessions.
   Separate up/down thresholds and range geometry; slow down either blocks entry
   or requires twice fast-up strength and a close above the prior fast box plus
   0.5 prior ATR.
2. Adaptive: choose fast/slow horizons daily by trailing 21 completed one-step
   log-regression forecast errors divided by prior ATR, plus fit-quality penalty.
   Zero/15% improvement hysteresis and five-session dwell. Horizon banks remain
   declared; this is not an unrestricted continuous window estimator.
3. Protected: monotone peak-close trail at 2/3/4 ATR aligned, 1/1.5 ATR countertrend.
   Distance uses min(entry ATR, current ATR); it never widens.
4. Stress: tighten distance by 0.5/0.75 when relative volatility crosses 1.25/1.5;
   volume variants additionally tighten at relative volume 1.5/2.0.
5. HMM without protection, HMM protected and HMM stress, described below.

All seven components have paired price/volume versions and the same 32 base
vectors: 448 candidates per ETF/cutoff. Fresh fast down cannot be vetoed by older
slow up or a hard volume condition. Entry needs a fresh eligibility edge. Uncertain
fast evidence expires after five sessions, slow after 21. HMM context uses current
probabilities instead of retained discrete evidence.

Protection is tested at completed closes, not intraday. Test the previously
adopted level before today's close/volume tightens the following close's level.
Initial protection uses actual entry open and prior ATR. Fill next open, with
one additional session tested symmetrically; pending targets remain binding.
Cash-funded fees, idle cash zero. Gaps can exceed indicated protection. No service,
allocation, monitoring, approval, broker or execution-policy changes.

Top three per family are rescored at 5/10/20 bp per side and zero/one extra session.
Prefer >=5 closed training trades and >=5% exposure across frictions, otherwise
flag. Select worst-friction training utility across full history and three blocks
using the prior objective. All 52 fit files sealed before evaluation: 52 later,
50 earlier fits, 45,696 initial scores and 21,420 additional finalist scores.
No old-strategy fallback. Train through 2022/test 2023–October 2026; independently
train through 2019/test 2020–2022. Both periods are inspected development evidence.

## HMM contract and limits

Separate three-state diagonal Gaussian fast/slow HMMs are combined at trading
decisions. This is not a fitted factorial/coupled HMM and does not make horizon
length itself latent. Each observes all four associated horizons' normalized
slopes, average efficiency and relative volatility. Volume models add signed
volume pressure and relative volume.

Training-only scaling, two deterministic starts, up to 25 EM iterations,
variance floor 0.05 and sticky transition pseudocount three are frozen.
Extreme drift centroids receive up/down names only after crossing +/-0.05;
the middle state is range only if absolute drift <=0.15, otherwise unknown.
Trading uses forward filtering, never Viterbi or smoothed full-sequence states.
Backward inference is used only inside training EM. Probability thresholds
0.55/0.7 are selected on training outcomes. Models stay fixed during evaluation;
training scores condition on emissions fitted to the whole training period and
are calibration, not rolling model-fit evidence.

The local Python 3.14 environment lacks a compatible hmmlearn wheel/compiler.
A small NumPy implementation avoids compiler/runtime dependencies. Forward
probabilities, training posterior and transition counts are independently checked
against exhaustive enumeration of short state sequences. Prefix tests verify
future observations cannot alter earlier probabilities. Background:
[hmmlearn decoding/smoothing reference](https://hmmlearn.readthedocs.io/en/stable/api.html).

Observed probabilities are often close to zero or one. Correlated horizon features
and diagonal covariance can encourage overconfidence. They are not calibrated
probabilities of profitable future trades. Validate state semantics, covariance
and duration before adding latent dimensions. HMM chart window lines are auxiliary
adaptive corridors; HMM probabilities observe all declared horizons.

## Outcomes

Later period, 5 bp/side, next open; methods selected on training only:

| ETF | Selected method | Prior union return | New return | Sharpe | Max DD |
| --- | --- | ---: | ---: | ---: | ---: |
| GLD | Fixed + volume | +117.54% | +85.78% | 1.080 | -18.52% |
| CORN | HMM protected, price | -29.19% | -9.86% | -0.320 | -17.93% |
| EWA | Fixed, price | +23.69% | -18.00% | -0.357 | -22.47% |
| TLT | Fixed + volume | -15.56% | -18.53% | -0.656 | -20.36% |
| MCHI | Fixed, price | -9.72% | +7.95% | 0.203 | -25.39% |
| IAT | Fixed, price | +38.55% | +11.12% | 0.249 | -26.27% |
| SLV | Fixed, price | +84.14% | +24.65% | 0.355 | -49.80% |
| SOXX | Fixed + volume | +335.90% | +152.05% | 0.929 | -30.29% |

The prior control is the causal union of two previously fitted position latches,
not either individual short/long result. GLD's fixed model sells March 26, 2026
at 408.53 after January 2025 entry at 253.19 (+61.19% net trade). Recognition
improves but full-period return is reduced. CORN's protected HMM limits damage;
unprotected price HMM still loses 31.12%. EWA/TLT remain poor. MCHI benefits from
faster direction changes without a separate stop. SLV retains large drawdown
and repeated re-entries; faster detection alone does not solve it.

Later: 40/51 risky ETFs positive, median CAGR 2.83%, Sharpe 0.319 against union
0.615. Only three improve prior CAGR; 15.69% stay within 1 pp CAGR / 2 pp DD guards.
Earlier: 32/49 positive, median CAGR 1.55%, Sharpe 0.214 versus 0.198; 24 improve
CAGR, 55.10% within guards. No positive alpha survives Holm in either era; median
IC21 -0.088 later, +0.037 earlier. All selected risky fits have adequate training
evidence. Seven later/27 earlier cases have fewer than five closed evaluation trades.

| Family | Later median Sharpe | Earlier median Sharpe |
| --- | ---: | ---: |
| Fixed, price | 0.364 | 0.223 |
| Adaptive, price | 0.297 | 0.189 |
| Protected, price | 0.109 | 0.160 |
| HMM, price | 0.336 | 0.292 |
| HMM + volume | 0.308 | 0.203 |
| HMM protected, price | 0.155 | 0.290 |
| HMM stress, price | 0.172 | 0.342 |
| HMM stress + volume | 0.121 | 0.195 |

No family passes preservation checks. Global selection chooses fixed methods for
34/52 later fits, HMM for 11, adaptive for five, other protection for two. HMM price
has useful earlier evidence, but no consistent benefit. Tight exits often reduce
later trend participation and compound re-entry timing losses.

## Portfolio and decision

The full-pool selector and dynamic/monthly controls are retained. New binary
latches and prior unions use identical FR25 multiplier 0.5 + 0.5 × latch,
diverting weight to BIL. This differs from the earlier graded short/long overlay;
use the matched union control in this report.

| Later, 5 bp/side | CAGR | Sharpe | Max DD | Annual cost bp |
| --- | ---: | ---: | ---: | ---: |
| FR25 | 16.51% | 1.450 | -8.65% | 43.47 |
| Prior union dynamic overlay | 16.19% | 1.437 | -8.92% | 44.59 |
| New dynamic overlay | 13.95% | 1.339 | -8.44% | 56.12 |
| New monthly overlay | 15.15% | 1.421 | -8.14% | 46.54 |
| Prior union dynamic selector | 10.82% | 0.795 | -14.36% | 106.38 |
| New dynamic selector | 7.66% | 0.587 | -14.05% | 131.01 |

No later portfolio gate passes. Earlier dynamic selection improves to 3.36%
CAGR / 0.310 Sharpe / -14.42% DD from union 1.87% / 0.198 / -21.20%, passing
all six frictions against both union and momentum. Earlier monthly deteriorates.
Thus 6/36 gates pass, all earlier dynamic; chronological transfer fails. No SOTA
replacement or promotion.

9,792 asset/friction and 102 portfolio cases. Prefixes/training scores reproduce;
independent event-ledger relative NAV error <=2.91e-14. All 54 unchanged portfolio
controls reproduce exactly. Three native Windows LEAN checks have zero NAV error.
Twenty-six focused tests and Ruff pass. Offline controls cover 1,632 detail rows,
118 charts and 608 chart windows; nine static figures visually inspected. Browser
layout is not certified. Frozen strategy code was not edited after fitting.

Before further optimization, inspect HMM meanings, sharp probabilities and trade
level missed recovery/stop costs. A future declared study can test regularized
correlated emissions, explicit state duration and retaining exposure through
uncertain fast reversals. Latent horizon/state expansion is a separate hypothesis
requiring a new validation design. Do not retune this completed run or select
ETF membership from its evaluation winners.
