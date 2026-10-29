# Trained per-ETF decision reviewer

Completed the authorized training study on the full supported 52/50 ETF pool.
[Interactive report and all charts](../research/trained-review-20261028-v1/index.html).
Both challengers are rejected as replacements. No portfolio overlay, promotion,
broker, monitoring or live change. The earlier entry-value B remains the broader
research reference; standing protection is this experiment's matched control.

## Design and provenance

Protocol `38a22ef38f411fe536aead6b686ef7c3b974cf3d3ab057b4b1490360068a66c9`.
Audited published batch
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`,
verified adjusted OHLC and raw share volume. No provider archives or online prices.
Historical publication-vintage limitations remain. No parent source changes or
post-evaluation parameter adjustments.

Three main arms: A unchanged standing protection; B trained price/trade-context
review; C same procedure plus relative volume, signed volume pressure and a
volume/close-location interaction. Each ETF separately fits continuation and
post-exit recovery return/downside models. Labels follow the protected path for
ten bars, with a terminal mark at the next open; all mature only at t+11. Actual
trades have no ten-day expiry. Hypothetical recovery holding states augment the
training sample; episode weights reduce overlapping-path domination.

Training uses the final 756 reference returns, with the final 252 sessions for
reviewer calibration. Prefix reviewer labels are purged across that boundary.
Weighted validation error selects an intercept or ridge strength 1/10/100.
A strategy replay selects margin disabled/0/.25/.5 subject to Sharpe, return and
drawdown guards; final coefficients refit all matured training observations.
The inherited parent HMM/policy uses the full outer-training snapshot throughout
internal calibration: this is conditional validation, not a fully nested parent
pipeline. Both evaluation eras are repeatedly inspected development data.

Recovery requires positive predicted net benefit but no old candle/volume/HMM
confirmation stack. Orders are cancelled if the next opening price moves more
than one signal-date ATR from the signal close. Recovery ownership delays HMM
exit authority until upward confirmation, while the new holding reviewer and
standing protection remain active. Original entries retain original exits.
Online forgetting is evaluated only in shadow, with matured labels; it never
changes trades. There is no new initial-risk budget or live loss-triggered reset.

## Results

Medians across individual risky-ETF strategies at 5 bp per side and 5 bp extra
stop slippage; excludes BIL. These are not portfolio metrics.

| Era | Model | Net cumulative return | Net CAGR | Net Sharpe |
|---|---|---:|---:|---:|
|2023–2026|A protection|11.39%|2.90%|0.402|
|2023–2026|B price|5.29%|1.37%|0.241|
|2023–2026|C price/volume|6.65%|1.72%|0.251|
|2020–2022|A protection|6.33%|2.07%|0.312|
|2020–2022|B price|4.20%|1.38%|0.202|
|2020–2022|C price/volume|4.20%|1.38%|0.182|

Both fail all 12 era/friction settings (5/10/20 bp, zero/one extra signal delay).
Each setting requires improved median Sharpe and lower-quartile CAGR plus 90%
of ETFs within 1pp CAGR/2pp drawdown of A. Primary preservation is 78.43% later
and 79.59% earlier for both challengers. Pool-quantile differences are not medians
of paired changes. Most ETFs are unchanged, so median paired return change is zero.

Training enables B/C for 22/21 of 51 risky ETFs later and 14/14 of 49 earlier.
C closes 704 recoveries later (355 winners), 544 earlier (221 winners). C improves
6 later returns and worsens 14; earlier it improves 5 and worsens 9. Prediction
quality and trading value remain unproven despite increased activity.

Later C improves DBA from +24.93% to +50.18% (drawdown 9.48% to 8.22%) and SLV
from +50.80% to +114.63% (drawdown 28.94% to 36.09%). These examples are descriptive,
not permission for hindsight asset selection. B destroys SOXX +76.82% to −52.36%;
C is disabled for SOXX and retains A. Different activation as well as features
prevents attributing that contrast solely to volume information.

## Mechanism failures and weakest cases

**WEAT later is the weakest C: −45.79%, versus A −15.98%.** Both final forecasts
are constants and margin zero. Holding value is −0.13182−.25×1.31171=−.45974;
recovery value is +.087 to +.139 after fees. It buys when flat and immediately
rejects the resulting position. All 315 completed trades last one session; 312
are recoveries. Fee drag is 834 bp/year, no stop fills, drawdown 45.92%.
Removing recovery still returns −22.09%; removing learned exits −36.73%.
[Full chart](../research/trained-review-20261028-v1/WEAT_late.png) and
[initial churn](../research/trained-review-20261028-v1/WEAT-churn.png).

**MCHI earlier is the weakest C: −34.96%, identical to A/B.** Both reviewers were
disabled by training. 26 completed trades, seven winners; drawdown 48.87%.
June 29–July 8, 2021 loses 8.75%. The active adjusted-price stop was $69.30;
prior lows did not reach it, then the scheduled thesis exit filled at the $67.42
opening gap. Initial risk distance 6.90% is not a guaranteed maximum loss.
[Full chart](../research/trained-review-20261028-v1/MCHI_early.png) and
[gap loss](../research/trained-review-20261028-v1/MCHI-loss.png).

**GLD is the clearest preservation failure:** +52.22% to +6.65%. Constant holding
value −.79972 is always below the −.5 exit threshold. All 35 completed trades
last one session; there are no recoveries. The model applies a pessimistic
training average, not evidence that the individual trade thesis deteriorated.
Drawdown improves from 15.13% to 3.48%, but participation and return collapse.

**Nominated intervals:** CPER March 4–September 4, 2025 remains +10.00% for all;
both reviewers disabled. IWM July 1–December 1, 2024 improves from −9.64% to
B +0.14% / C −1.25%. All seven C trades in that interval last one session; its
only recovery August 26–27 loses 1.46%. Full later IWM is A +4.83%, B −6.74%,
C −14.82%. The interval improvement is not evidence of robust rebound detection.

The recovery label assumes continued protection without subsequent learned exits;
the actual reviewer often exits next day. Independent models therefore score
different continuation policies and can contradict each other. HMM handoff does
not fix this learned-model conflict. The implementation follows its frozen rules,
but those rules do not enforce economically consistent decisions. Retain this
negative evidence rather than silently repairing and replacing the run.

## Components and learning diagnostics

Later median Sharpe: additional-exit-only .178, recovery-only .386 versus A .402.
Earlier: .328 and .247 versus A .312. The earlier exit-only primary passes, but
the effect fails across eras. SLV illustrates useful handoff: C +114.63% versus
+25.56% with immediate original-HMM authority; other problems remain.

C prediction loss medians (constant / fitted / shadow): later holding
4.489 / 4.586 / 7.310, recovery 5.501 / 5.720 / 7.761; earlier holding
5.335 / 5.556 / 6.834, recovery 5.363 / 5.495 / 6.595. Lower is better.
C fitted forecast IC medians holding/recovery .022/−.038 later, .021/.052 earlier;
only 23/20 and 23/14 nonconstant ETF forecasts have defined IC. Overlapping labels
are dependent. Shadow learning does not earn trading authority.

## Next research direction

Use a common definition of the value of holding versus cash, with explicit
switching costs, consistent continuation policy and an unchanged-state
entry/holding consistency check. Review should measure new evidence relative to
the original decision, not automatically turn a negative unconditional training
mean into an exit. Include an abstaining reviewer, evaluate final-refit behavior,
and use rolling nested training/calibration. Separate an independent entry-risk
budget from after-loss learning. Test improvements across the full pool, retaining
good-asset return/drawdown guards and weakest charts each era. These are proposed
changes for a new protocol; none has been tuned into this completed run.

## Verification and recipe

1,836 main cases plus 612 diagnostic cases; 612 exact parent controls and 612
exact disabled-review paths. Maximum independent ledger discrepancy 2.91e−14.
41 focused Python tests pass, including timing, gap stops, recovery handoff,
training guards, prefix invariance and matured shadow labels. Offline chart
checks cover 306 ETF/era/arm combinations, date ranges and isolated value points.
Four native Windows LEAN accounting fixtures (CPER later, IWM later, WEAT later,
MCHI earlier) match their independent whole-unit reference to $0. Synthetic
event clocks validate accounting, not intraday execution or reviewer inference.
Scientific figures are inspected separately; browser layout is not certified.

Recipe: `scripts/research_trained_review.py` prepare/fit/evaluate;
`scripts/analyze_trained_review.py`; `scripts/inspect_trained_review.py`;
`scripts/build_trained_review_report.py`; `scripts/validate_trained_review.py`;
`scripts/seal_trained_review.py`. Frozen fits, compact evidence, verified inputs,
QA receipt and final artifact hashes are retained.
