# Individually fitted ETF breakouts: failures, regimes and range redesign

The operator requested full-pool short/long results with independent hyperparameter
fits for every ETF, followed by diagnosis of weak outcomes and changes that preserve
stronger results. Subsequent steering added earlier profit protection, trend
direction and a redesign of range recognition.

## Existing independently fitted results

[Full sortable table and trade attribution](../research/etf-breakout-failure-review-20261023-v1/index.html)
contains 104 later ETF/domain fits and 100 available earlier fits. It verifies and
reuses the October 21 sealed independent fits: 241 candidates per ETF/domain/cutoff,
training-only finalist selection across six frictions. It does not transfer GLD
parameters or claim a new rerun of that original 27-coordinate search on October 23.
All 52 published price-supported ETFs are included; BIL is a cash reference and
excluded from the 51-risky-ETF family summaries. CPER/XLC have insufficient earlier
training history; other sparse original training evidence is explicitly flagged.

Primary period is January 3, 2023–October 16, 2026, 5 bp per side, next-open fills,
zero interest while idle. Earlier fits train through 2019 and evaluate 2020–2022.
Both periods were previously inspected. USD adjusted prices and separately audited
raw volume come from the same pinned published batch:
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`.
Price auditing does not establish historical publication availability or historical
universe membership. No provider data were downloaded or substituted.

| Later own-ETF fit | Short | Long |
| --- | ---: | ---: |
| Positive net return | 39/51 | 37/51 |
| Beat own ETF's buy/hold CAGR | 2/51 | 2/51 |
| Beat own ETF's buy/hold Sharpe | 3/51 | 5/51 |
| Median state IC21 | -0.097 | -0.054 |
| Fewer than five newly completed evaluation trades | 34/51 | 50/51 |

| Example | Net cumulative | Sharpe | Standard Calmar | IC21 | Own ETF buy/hold cumulative |
| --- | ---: | ---: | ---: | ---: | ---: |
| IAT short | -29.93% | -0.476 | -0.243 | -0.219 | +36.77% |
| WEAT short | -23.04% | -0.645 | -0.236 | -0.113 | -39.85% |
| XLB long | -21.32% | -0.769 | -0.261 | -0.294 | +40.82% |
| MCHI long | -20.03% | -0.233 | -0.178 | -0.216 | +17.42% |
| XLY short | -19.32% | -0.668 | -0.271 | -0.239 | +79.75% |
| CORN short | -17.31% | -0.642 | -0.284 | -0.097 | -32.45% |
| EWY long | -7.60% | -0.605 | -0.217 | -0.040 | +186.13% |
| SLV short | -6.82% | -0.048 | -0.114 | -0.140 | +133.92% |
| GLD short, own bounded refit | +30.30% | 0.657 | 0.465 | -0.079 | +125.19% |
| GLD long | +51.45% | 1.290 | 1.025 | 0.025 | +125.19% |
| SLV long | +84.41% | 0.905 | 0.899 | 0.069 | +133.92% |
| PPLT long | +40.32% | 0.600 | 0.523 | 0.096 | +48.57% |

The original heavily optimized GLD short fit in the inspection chart remains
+40.70% cumulative, 1.004 Sharpe, 0.777 Calmar and 0.127 IC. It is a different
vector from the equal-budget corrected pool refit. Neither is silently substituted
for the other. Standard displayed Calmar is CAGR/absolute maximum drawdown;
zero drawdown is unavailable. The archived optimizer's 3% denominator floor is
preserved in optimization and labelled separately in the detailed evidence.

## What actually failed

“Trail activated” does not guarantee useful profit protection. IAT short has a
34.35% peak trail; XLY short has a 25.46% peak trail. An unheated percentage trail
with those distances requires a 52.3%/34.2% peak gain just to rise above the entry
price, although their activation thresholds can be only roughly 1–4%. In the
later sample, 20 closed episodes armed their trail but still exited at the unchanged
initial floor. This is a parameter interaction, not an accounting error.

XLY's November 2024 trade peaked at +14.11% and closed at -5.45%. Its armed trail
never raised the initial floor. Fees account for only about 0.32 percentage points
of the strategy's -19.32% cumulative result. IAT's July 2023 trade peaked at +9.12%
and closed at -12.10%. Wider trails, delayed close-to-open execution and gaps all
matter; an entry-price stop is not a guaranteed breakeven fill.

XLB long's five evaluation trades all lost and none armed the trail. Required
activation gains were about 9.36–15.31%; actual peaks were mostly much lower.
MCHI's first trade lost 25.47% with a very loose initial floor; its +9.36% peak
did not reach the +10.49% activation requirement. Tightening a rule that never
activates does not address those examples.

EWY long held only 14 of 951 evaluation sessions (1.47%) and missed nearly all of
a +186.13% ETF advance. Entry/range recognition and re-entry coverage matter here.
SLV short also missed much of a later rally between sparse entries. Conversely,
WEAT and CORN lose in absolute terms but avoid part of larger underlying declines;
this is different from failing to participate in a strong rally.

Every later path reconciles to exact overnight/intraday exposure and fee accounting.
Stop levels are independently reconstructed. Closing-state counts are descriptive,
not a causal decomposition: being flat without a fresh range does not by itself
prove that changing the range would create a profitable entry.

## Declared component experiment

The new experiment is separate from the preserved baseline. Each available
ETF/domain/chronology fits 90 structural combinations around its own sealed
27-parameter vector. The original coordinates remain the anchor; the new search
fits exit mode, trend gate and range family/lookback. Four selections isolate
exits, trend, range and their combination. The original fit remains eligible.

- Exits: original; entry-price floor after a 1 confirmation-ATR peak gain;
  0.5/1/2 current-ATR trail activated after that gain, with heat disabled; or the
  first lower close after that gain. Original initial risk/time/cooldown/re-entry
  rules remain. The forced first-lower rule is also evaluated for all ETFs as a
  diagnostic, regardless of training selection.
- Trend: own-ETF close versus its 200-session average and that average versus
  its value 63 sessions earlier. Both positive means up, both negative down,
  otherwise mixed. Entry choices are unrestricted, avoid down, or up only.
  This gates confirmation and continuation; existing positions follow exits.
  It is not a broad equity-market filter imposed on gold or bonds.
- Range: original; flat 10/90% band with low path efficiency, limited fitted
  drift and width at most 8 prior ATR20; or a rising log-regression residual
  channel at most 4 prior ATR20. Both require last-third volatility no higher
  than full-window volatility. Short lengths 21/63; long lengths 126/252.
  Recognition uses prior closes only; a channel is projected one session forward.

The best five candidates in each family plus baseline are rescored at all six
cost/delay combinations. Replacements require at least five closed training
trades and 5% exposure, no more than 1 percentage point CAGR loss or 2 points
drawdown deterioration at every training friction, and better worst-friction
utility. Otherwise the baseline is retained. All choices are sealed before
evaluation; no asset list is selected from the observed evaluation winners.

The declared family acceptance test requires improved median Sharpe and improved
lower-quartile CAGR, with at least 90% of eligible ETF/domain cases within the
same return/drawdown guards. It must survive both chronologies and all frictions.
Separate full-pool selection and FR25 overlay tests compare dynamic and monthly
adoption, including actual costs and delay. These are research comparisons only.

During preflight, a display-oriented serializer was found to round parameters.
It was replaced with full-precision machine serialization before any evaluation;
incomplete training files were discarded and the identical declared search was
restarted. The prior protocol and correction receipt are retained. No candidate,
objective or acceptance rule was changed in response to evaluation outcomes.

## Component experiment outcome

[Complete component and regime report](../research/adaptive-breakout-20261023-v1/index.html)
includes 7,344 asset/friction cases, 102 portfolio cases and exact per-regime
log-return attribution. All 1,224 baseline metric cases reproduce the prior
sealed study exactly. Event-ledger error is below 2e-15 relative NAV; all selected
training prefixes reproduce exactly. Three native Windows LEAN cases have zero
NAV difference. Forty focused tests, Ruff and both offline report-control suites
pass; static scientific figures were inspected. Browser layout is not certified.

The forced first-lower-close rule helps several weak later cases but damages
many stronger cases. These are cumulative net returns, not annualized returns:

| ETF/domain | Existing fit | First lower close after 1 ATR peak gain |
| --- | ---: | ---: |
| IAT short | -29.93% | +13.92% |
| XLY short | -19.32% | -1.02% |
| XLB long | -21.32% | +0.79% |
| MCHI long | -20.03% | +5.78% |
| EWY long | -7.60% | -7.60% |
| GLD long | +51.45% | +13.08% |
| SLV long | +84.41% | +14.21% |
| PPLT long | +40.32% | -34.31% |

Across the 99 later risky ETF/domain cases with adequate original training
evidence, forced first-lower improves CAGR in 23, impairs it in 74 and leaves
two unchanged. Median paired CAGR change is -2.30 percentage points; median
paired Sharpe change -0.209. Earlier: 29 improve, 56 worsen, one unchanged among
86 eligible cases. These are full-history strategy replays: earlier exits also
change subsequent entries and carried positions, not merely the sell price of
the same fixed trade list.

Training chose combined changes in 13/104 later fits and 11/100 earlier fits.
It retained GLD and the highlighted IAT/XLY/EWY/SLV baselines. The later eligible
combined cases improve CAGR in three, worsen it in seven, and leave 89 unchanged.
EMB short improves from +0.13% to +8.60% cumulative. IWM short falls from +33.01%
to -12.08%, TIP short from +6.66% to -1.96%, and XLU long from +23.45% to zero
through lack of entry. None of the fitted component families satisfies the
declared cross-chronology acceptance design.

Trend classification is useful context but not an oracle. XLY short holds all
122 active sessions in the lagged "up" regime and still loses. A simple slow
uptrend gate would not remove that failure. WEAT is in the "down" state on
744/951 sessions, while GLD has no "down" sessions by this definition. Regime
labels can lag a reversal or remain negative during a rebound. The report uses
labels known before each return and avoids future turning-point labels.

Later dynamic combined overlay: 12.38% CAGR / 1.404 Sharpe / -7.31% DD, versus
FR25 16.51% / 1.450 / -8.65%. All 24 later portfolio/friction gates fail. Six of
12 earlier selector gates pass, but the gain does not transfer to the later
period. The tested changes do not justify promotion or replacing SOTA.

## Operator's next hypothesis: exit on failure of the new upward trend

The operator clarified that the long-only profit exit should follow the rising
trend established after a horizontal/downward breakout, and sell when that new
trend breaks. This differs from exiting on the first lower close. It could allow
normal GLD pullbacks while protecting a steep IAT advance; that is a hypothesis,
not a conclusion from the preceding first-lower experiment.

Keep this as a separate declared experiment: causal post-entry rising support
with noise allowance, an independent initial protective stop, fixed entry rules
for attribution, and training-only per-ETF selection across the full pool. Do
not change the sealed component experiment or choose rules solely to rescue the
already inspected GLD/IAT paths. Larger-universe admission remains a separate
published-data prerequisite. No promotion, monitoring or execution changes.

## Post-entry rising-support experiment outcome

[Trend-failure exit report and GLD/IAT plots](../research/post-breakout-trend-20261023-v1/index.html)
implements that hypothesis as a separate version. The boundary uses only prior
post-entry closes, starting after five observations, with a growing window capped
at 10/21/42/63 sessions. A positive log-regression slope projects a lower residual
boundary, less a 0.5/1/2 prior-ATR noise allowance. It ratchets upward. Original
initial risk remains; the old failed-breakout time rule applies until rising
support is first established. A closing breach sells at the next open. The old
profit trail/heat rule is replaced; entries and re-entry remain fixed.

The 12 combinations plus unchanged baseline were fitted separately for every
available ETF/domain/chronology. Under the declared training trade-count,
return/drawdown and worst-friction utility requirements, none of the 104 later
fits selected the new exit; three earlier fits did. The fixed 21-session / 1 ATR
rule is a predeclared, unselected common control, not a fitted winner.

| Later ETF/domain | Existing cumulative | Fixed trend-exit cumulative | Existing Sharpe | Trend-exit Sharpe |
| --- | ---: | ---: | ---: | ---: |
| GLD short, equal-budget pool fit | +30.30% | +13.38% | 0.657 | 0.535 |
| GLD long | +51.45% | +10.40% | 1.290 | 0.624 |
| IAT short | -29.93% | -5.07% | -0.476 | -0.081 |
| IAT long | +6.72% | +10.05% | 0.187 | 0.438 |
| MCHI long | -20.03% | +27.83% | -0.233 | 0.690 |
| PPLT long | +40.32% | +36.25% | 0.600 | 0.651 |
| SLV long | +84.41% | -20.31% | 0.905 | -0.560 |

The separate original heavily optimized GLD short anchor falls from +40.70% to
+11.39% with the same fixed trend-exit control. Do not substitute it for the pool
short vector. All table results cover 2023–October 16, 2026, 5 bp per side, next
open, zero idle-cash interest. The report retains all costs/delays and both eras.

IAT's July 13, 2023 trade now exits August 10 at +6.03%, after peaking +9.12%,
instead of the original October exit at -12.10%. Its November 2023 entry earns
+14.62% through January 4, 2024. Later failed entries still hurt: three later
losing trades never establish rising support. The full IAT short control remains
negative; preventing profit giveback does not repair every false breakout.

GLD long exits May 17, 2023 at -1.82% and next enters December 6. Later it exits
a February 2024 entry on March 25 at +6.96%, then waits until July 12. Its fitted
continuation re-entry flag is off. Exposure falls from 40.06% to 10.83% of the
evaluation period. A projected steep local line can break during deceleration
without ending the broader upward trend, and the preserved entry rule can then
miss continuation. These are concrete limitations of this implementation, not
proof that all trend-structure exits fail.

The fixed rule improves later CAGR in 28/99 eligible risky ETF/domain cases,
worsens 70, leaves one unchanged; median paired CAGR change is -2.49 percentage
points. Earlier: 35 improve, 50 worsen, one unchanged among 86. No family passes
the full acceptance design. Later selected portfolios equal their existing
baselines because no new exit is selected; 0/24 later and 4/12 earlier portfolio
gates pass, without cross-chronology support. No strategy change is justified.

The new study has 3,672 asset/friction and 102 portfolio cases, 1,224 exact baseline
regressions, exact training-prefix checks and independent ledger error below
1.6e-15 relative NAV. Regime contributions reconcile below 4e-16 log return.
Forty-five focused tests and Ruff pass; standalone controls and GLD/IAT figures
were checked. Three native checks have zero NAV difference. These receipts verify
selected portfolio accounting; with baseline
retention they are not evidence of a profitable new exit or independent signal
validation. No browser-layout, live readiness or untouched-holdout claim.

Next research design should distinguish a steep advance slowing into consolidation
from a structural reversal, then coordinate a continuation re-entry rule with
the exit. Causal higher-low structure or multiple trend timescales are hypotheses
to predeclare, not changes applied to this inspected sample. The initial failed-
breakout risk rule also remains a distinct problem for trades that never trend.

## Full-pool actual trend-exit table and worst-case inspection

The operator requested the trend exit across the full ETF table, followed by
inspection of the worst result. The [paired table and trade inspector](../research/trend-exit-failure-review-20261023-v1/index.html)
now makes the actual fixed 21-session/1 ATR control explicit. The independently
fitted entry/risk anchors are retained for every ETF. This is not a claim that
the common exit was independently selected: all 104 later training choices
retained the previous exit. Both chronological tables and all six cost/delay
cases remain available; 104 later paths plus their matched baselines were replayed.

Among 102 risky ETF/domain cases (BIL excluded, limited-training rows retained
and marked), 56 have positive net return, 46 lose, 28 improve the previous exit,
73 worsen and one is unchanged. Short:29 positive/22 negative. Long:27/24.
The earlier family gate's narrower evidence subset remains unchanged.

| Worst later net returns | Previous exit | Trend exit | Sharpe | Calmar | IC21 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SLV long | +84.41% | -20.31% | -0.560 | -0.222 | -0.191 |
| TLT short | -12.73% | -15.93% | -0.723 | -0.282 | -0.231 |
| DBC long | +0.57% | -15.11% | -0.666 | -0.168 | -0.092 |
| MDY short | +25.86% | -13.41% | -0.465 | -0.229 | -0.140 |
| EFA short | +23.49% | -11.93% | -0.378 | -0.141 | -0.129 |

Same 2023-January-3 through 2026-October-16 evaluation, 5 bp per side, next-open
fills and zero idle-cash interest. Worst net loss differs from largest damage:
SOXX short remains positive at +24.62%, but falls from +187.66% previously.

SLV long has six completed trades, five losses, 101/951 held sessions, -26.31%
maximum drawdown, -11.65% annualized same-ETF/BIL-adjusted alpha, and -0.191 IC21.
The alpha/IC estimates do not imply out-of-sample predictive significance after
repeated development on this history. Its actual trade ledger is:

| Entry | Exit | Net trade return | Peak closing gain | Initial risk below entry | First support |
| --- | --- | ---: | ---: | ---: | --- |
| 2023-04-11 | 2023-05-12 | -3.76% | +4.54% | 20.68% | 2023-05-05 |
| 2024-04-10 | 2024-04-23 | -2.74% | +4.26% | 18.55% | 2024-04-17 |
| 2024-05-09 | 2024-05-23 | +10.91% | +15.60% | 19.29% | 2024-05-16 |
| 2024-10-28 | 2024-12-19 | -13.57% | +2.21% | 23.96% | 2024-12-10 |
| 2025-03-19 | 2025-04-04 | -8.96% | +2.09% | 18.57% | 2025-03-28 |
| 2025-06-10 | 2025-06-25 | -2.44% | +1.29% | 19.39% | 2025-06-18 |

The October 2024 entry at 30.71 initially protects only around 23.35. First rising
support appears December 10 around 27.20, after a decline and small rebound. A
positive rolling slope below the original entry is not proof that the breakout
established a durable profitable trend. Exit decision December 18 is below the
27.53 ratcheted boundary; next-open fill is 26.57. The March 2025 decision has a
30.05 boundary, 28.89 closing price and 27.96 next-open fill, illustrating both
closing overshoot and overnight risk. All six exits are labelled trend support
because they eventually raise the initial floor; that label alone hides the late
formation and below-entry support problem.

The final June 2025 sale is at 32.53. No further position occurs by the cutoff,
when SLV is 58.35% higher. Continuation is disabled and the five-session cooldown
alone cannot explain this entire absence. Observed flat states:363 sessions with
no fresh qualifying range,402 waiting for a crossing,49 awaiting confirmation,
six buy-queued and30 cooldown. These counts are descriptive, not a counterfactual
proof that relaxing a specific condition improves returns. Fees explain only
0.48 pp of the -20.31% cumulative return. At 5 bp with one added execution session,
SLV loses -30.85%; at20 bp plus delay, -32.19%.

TLT's ten trades include two initial-risk exits and three failed-breakout time
exits; half never form rising support. SOXX retains continuation but has20-session
cooldown and fitted continuation conditions; it holds219/951 sessions. These
different mechanisms argue for separating entry failure, support establishment
and continuation design rather than assuming one universally tighter exit.

Validation:208 paths reproduce saved metrics with zero error, independent event
ledger error<=1.12e-15 relative NAV, exact trade and overnight/intraday log sums,
and15,875 independently reconstructed held-session boundaries with maximum price
error6.48e-12. A symmetric SHY price window produced an approximately3e-16
least-squares slope rounding residue in the independent checker; treating slopes
<=1e-14 as numerical zero restored the mathematically flat result. The frozen
engine and all saved outcomes remain unchanged. Eighteen focused tests and Ruff
pass, including rejection of corrupted support, carried/pending/cutoff semantics
and the zero-slope case. Offline controls cover both eras, all204 detail records,
rank/search and31 focused chart views; static plots inspected. No browser-layout
certification or new portfolio result is claimed. All inputs and upstream hashes
verified; no provider fetch, strategy change, deployment or promotion.
