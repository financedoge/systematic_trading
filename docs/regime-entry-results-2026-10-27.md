# Trend detection and cautious entry — 27 October 2026

[Report, mathematical rules and every ETF chart](../research/regime-entry-20261027-v1/index.html).

Completed the operator's requested market-dependence investigation and next
component experiment. Neither challenger is adopted. There are 1,836 cases:
52 later / 50 earlier ETFs, three algorithms, six cost/delay combinations.
Both chronological eras were already inspected; this is development evidence.
No portfolio overlay, broker, monitoring or live changes.

## Market dependence

The preceding adaptive thesis-exit B strategy has median daily-return correlation
0.601 later / 0.542 earlier and beta 0.360 / 0.293. Median annualized regression
intercept is -0.49% / +0.59%, with median HAC(5) t -0.111 / +0.150. Regression uses
the ETF's daily arithmetic returns and zero cash rate, not cumulative price
levels; its intercept is descriptive, not causal or risk-free-adjusted alpha.
GLD later correlation is 0.811, beta 0.654. TLT later captures 36.0% of negative
ETF-day return magnitude versus 30.8% of positive-day returns. High correlation
alone is not failure, and reducing exposure alone is not evidence of skill.

## Frozen design

- A: existing per-ETF detector and selected thesis exit, **fixed base policy0**.
- B: A with a newly fitted fast-slope three-state HMM for every ETF. Separate
  Gaussian variances; down/up means constrained beyond -2b/+2b; neutral mean0
  and variance capped b². b=.05/.10 selected per ETF by forward slope likelihood
  over final252 training observations; refit selected band on full training.
- C: B with stronger confirmation when slow-up probability<.7 or after a loss.
  Up>=max(.8,base entry), positive slope, 2/3 consecutive flat opportunity closes,
  and log price advance >=.5/1 training daily sigma + twice per-side fee. Following
  a loss, also require a fresh up<.5 observation at/after actual exit and one extra
  confirming close. Nonlosing completion clears the loss flag. No permanent pause.

All three hold Bayesian policy learning fixed to separate signal effects from
shadow-policy feedback. A is **not** the actual adaptive incumbent. Its separately
reported historical performance prevents presenting component gains as upgrades.
Original fast/slow Kalman fits, base trading thresholds, thesis exit, stop
distances and causal next-open execution remain. No independent hard-risk stop
or predictive-return gate was added. Raw audited volume remains descriptive.

Four C rules are selected over final756 training returns against B, requiring
>=3 completed trades, improved Sharpe, CAGR within1pp and DD within2pp; otherwise
disable. C enables on23/51 later and29/49 earlier risky ETFs. Existing Kalman and
trading parameters see the entire training period, so the HMM holdback is not
nested validation of the entire pipeline; guard selection is in-sample.

## Results at 5bp per side and next open

| Metric | Later A | Later B | Later C | Earlier A | Earlier B | Earlier C |
|---|---:|---:|---:|---:|---:|---:|
| Median Sharpe | .419 | .367 | .247 | .276 | .255 | .309 |
| Median CAGR | 4.18% | 3.34% | 2.14% | 2.43% | 1.58% | 1.30% |
| Preservation vs A | 100% | 45.1% | 47.1% | 100% | 67.3% | 55.1% |
| Annual median cost bp | 45.0 | 62.2 | 53.0 | 43.4 | 63.3 | 50.0 |
| Daily median correlation | .643 | .656 | .640 | .579 | .571 | .532 |
| Median raw score IC5 | -.036 | -.040 | -.040 | .033 | .031 | .031 |

Neither challenger passes any of12 era/friction cases. Acceptance requires higher
median Sharpe and lower-quartile CAGR, with >=90% preserving CAGR within1pp and
DD within2pp of A. No absolute annual cost ceiling. B/C IC is identical because
it measures their shared raw HMM score; C changes entry selection. IC is the
overlapping five-session open-return Spearman diagnostic, not every holding
horizon or a cost-adjusted return metric.

| Net cumulative return | Fixed A | New HMM B | C |
|---|---:|---:|---:|
| GLD later | +57.14% | +58.27% | +58.27% |
| GLD earlier | -6.87% | +8.63% | +8.63% |
| WEAT later | -32.51% | -13.21% | -13.21% |
| WEAT earlier | +8.78% | +24.41% | +24.41% |
| TLT later | -12.48% | -21.14% | -21.14% |
| INDA later | -0.57% | -14.29% | -14.29% |
| MCHI later | +41.30% | +24.72% | -1.71% |
| ITA earlier | -10.39% | -14.83% | -34.12% |

Previous **adaptive** incumbent GLD later/earlier +85.87%/-12.74%, WEAT later
-13.88%, TLT later -17.66%. WEAT's big improvement over fixed A is only a small
improvement versus that actual incumbent; GLD's component comparison likewise
does not establish a direct adaptive-strategy upgrade.

## Why it failed

**New HMM state-meaning defect:** separate unbounded Gaussian tails can defeat
directional mean constraints. ITA earlier down/up normalized variances are
.2005/.01565. Its broad down state becomes an outlier state, assigning99.89%
down on April9,2020 while fast slope is +.970 training daily sigma; May27's
slope +1.202 also gets effectively100% down. This is a specification flaw in
this experiment, not evidence those upward slopes are economically downward.
The post-evaluation state audit is descriptive and does not feed selection.
Reject this parameterization; operational tests do not validate economic labels.
Opposite-sign state probability>=80% occurs in11/51 later and17/49 earlier risky
ETFs:288 later/442 earlier down-with-positive-slope sessions and3 earlier
up-with-negative-slope sessions. This is a semantic audit, not observed state truth.

**Weakest earlier C, ITA:** -34.12%, Sharpe-1.207, DD39.33%,13 completed trades,
only2 wins. C skips B's April8–13 +4.81% and May22–28 +11.32%, yet takes
July23–31 -4.77% and October19–28 -8.24%. Incorrect HMM states and over-demanding
confirmation both contribute. This is not just excessively wide protection.

**Weakest later C, TLT:** -21.14%, Sharpe-.619, DD24.47%,23 completed trades/6wins
versus A16/5. C's gate was disabled by training, so this failure is the detector,
not an enabled confirmation rule. November3,2023–January8,2024 still earns8.94%
(A November6–January9 earns11.59%). A July17–September27,2024 earns5.51%; B
fragments it into July15–26 -.15% and August2–September25 +1.53%. Extra losing
June/July2023 and April2025 entries add damage. Finer classifications overtrade.

**MCHI confirmation delay:** B's September20–October9,2024 earns18.90%; C buys
September25, same exit, earns11.15%. Several delayed rebounds produce C -1.71%
versus B +24.72%. Waiting for more price progress can worsen entry value.

**WEAT improvement remains incomplete:** June8–29,2023 earns4.66% versus A's
June16–29 -2.18%, but July2023 still loses7.85%. INDA's December2024 incident
remains contained; new HMM nevertheless increases completed trades19→29 and
adds small losing entries through2025–26.

## Decision and next step

Keep these results frozen and reject both replacements. Preserve simple thesis
invalidation as a component, not a universal validated strategy. Before the next
return search, test directional state semantics on extreme observations; consider
shared directional variance or sign-constrained latent drift with measurement
uncertainty. Do not silently repair this completed experiment.

Next prioritize training-only chronological forecasts of conditional future
returns/downside risk, with declared forgetting/change-point candidates. Slope
likelihood is insufficient evidence of profitable entry. Replace generic waiting
for a bigger rise with entry-value/risk assessment relative to a causal
invalidation boundary; preserve brief countertrend rebounds. Keep independent
risk-boundary work separate. Reconnect Bayesian policy adaptation only after
signal components improve matched fixed-policy outcomes. No portfolio overlay.

## Evidence and checks

Protocol a464de989ffd329ab2944816687470cb38915612f105c436d59fde247f276378.
Published batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd;
chart hash1c35aa34e95b9cdb64dab9aed8b27026c13c0419968321a4bfdb9dcc1dd6f808.
Published adjusted prices/raw volume and parent hashes verified; historical
publication-vintage limitations remain. One pre-evaluation initialization-bound
correction was recorded in protocol-amendments.json; all partial fits were
discarded and full training restarted before any evaluation outcomes were seen.

31 tests (12 new) pass.612 fixed controls agree within9.4e-15; independent ledger
within5.8e-15.306 offline chart combinations/date controls pass. Eight export
charts plus formula proof are prepared. Native INDA delay0,GLD delay1,TLT delay0
match app whole-unit accounting exactly; fractional/native cumulative returns
-14.2869%/-14.2234%,+64.0167%/+63.9667%,-21.1439%/-21.1071%; maximum normalized
path difference0.23pp. Native checks frozen accounting, not independent inference.
The state-semantics audit rejects the model despite these implementation checks.
No browser-layout certification is claimed.
