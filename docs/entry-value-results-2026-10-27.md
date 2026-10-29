# Directional states and online entry value — 27 October 2026

[Report, equations and every ETF chart](../research/entry-value-20261027-v1/index.html).

Completed the operator-approved next round: 52 later / 50 earlier ETFs,
three component arms and six friction settings, 1,836 cases. Both evaluation
eras have been inspected repeatedly and remain development evidence. No
portfolio overlay, monitoring, promotion, paper or live changes.

## Design and chronology

A exactly reproduces the previous original-detector fixed-policy control.
B replaces its fast-state detector with symmetric Gaussian emissions:
means (-a,0,a), shared directional variance v, bounded neutral variance vR.
a∈[.2,2], v∈[.01,4], vR∈[.000025,.01]. Hence log(fU/fD)=2ax/v,
strictly increasing with slope. Persistence can still oppose modest new
observations; this fixes directional tail semantics, not economic accuracy.

C adds discounted ridge forecasts of H-session next-open log return and
sampled open/close adverse movement. Buy eligibility requires predicted return
minus exact roundtrip log fee minus .25 predicted adverse movement >0.
It keeps learning from matured hypothetical outcomes while flat or invested.
It does not add forecast exits or a new loss boundary. Existing fixed entry,
rearm, thesis-invalidating exit and nonloosening protection remain.

Per ETF, refit both Kalman filters and symmetric HMM before final252 training
sessions. Derive H=clip(round(1/(1-AUU)),5,21) there and freeze. Forward validation
scores only outcomes matured by the cutoff. Four forecast candidates: full10
trend/price/raw-volume features or intercept-only, each with63/252-session
half-life. Select normalized return MSE+.5 adverse-movement MSE. Then refit final
HMM on all training using inherited full-training Kalman fits and replay training
to seed forecasting. This seed is fitted calibration; only prefix forecast
selection is chronological, not nested validation of the complete strategy.
Ridge prior4I, observation weight1/H, risk penalty.25 all predeclared. Scores and
ridge posterior means are not calibrated profitability probabilities.

Protocol: `3473303edc16cedb865ec771a3aa46003c64b722dd683b400cbafc5b12a83406`.
Published audited batch:
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`.
Adjusted prices; audited raw volume only in full-feature forecasts. Parent
execution text retained a descriptive-volume sentence; the explicit forecast
specification controls C. Recorded clarification also explains unused inherited
HMM/training_end metadata in prefix_models: actual prefix_end and new prefix
fits govern forecasts. A dependency test proves inherited HMM changes cannot
affect these features or eligibility. Frozen models/results were not changed.

## Primary results

5bp per side, next open; medians exclude BIL.

| Metric | Later A | Later B | Later C | Earlier A | Earlier B | Earlier C |
|---|---:|---:|---:|---:|---:|---:|
| Sharpe | .419 | .392 | -.007 | .276 | .322 | .000 |
| CAGR | 4.18% | 3.13% | -.09% | 2.43% | 2.40% | .00% |
| Preservation vs A | 100% | 47.1% | 27.5% | 100% | 65.3% | 44.9% |
| Exposure | 48.5% | 47.1% | 10.3% | 52.5% | 50.1% | 8.5% |
| Daily correlation | .643 | .655 | .374 | .579 | .573 | .288 |
| Annual cost bp | 45.0 | 56.9 | 13.3 | 43.4 | 55.1 | 10.0 |

Both B and C fail all12 era/friction acceptance cases. Acceptance requires
better median Sharpe/lower-quartile CAGR and ≥90% within1pp CAGR/2pp DD versus A.
Cash-only paths use the inherited Sharpe0 convention, not estimated trading skill.
Lower turnover/exposure/correlation alone is not success.

Training selects intercept-only46/51 later and45/49 earlier. Thus C largely
forecasts recent average outcomes rather than an individual setup's prospects.
Median forecast IC -.086/-.091. The selected full models beat same-memory
intercept return MSE on0/5 later and1/4 earlier ETFs; median MSE ratios1.034/1.072.
H mostly9–11 sessions. Overlapping labels and repeated inspection preclude formal
significance claims. Return MSE is descriptive and is not the combined training
selection objective.

| Net cumulative return | A | B | C |
|---|---:|---:|---:|
| GLD later | 57.14% | 58.40% | 37.31% |
| GLD earlier | -6.87% | 7.38% | 21.57% |
| WEAT later | -32.51% | -18.44% | 0.00% |
| TLT later | -12.48% | -21.14% | -1.43% |
| INDA later | -.57% | 1.76% | 4.03% |
| MCHI later | 41.30% | 26.88% | 0.00% |
| CPER later | 34.96% | -13.88% | -31.51% |
| IWM earlier | -13.13% | -25.11% | -17.53% |

Actual preceding adaptive incumbent is distinct: GLD85.87% later/-12.74% earlier.
No direct upgrade is established by comparing against fixed A alone.

## Failure inspection

**CPER, weakest later C:** -31.51%, Sharpe-.776, DD31.94%, four completed
trades/one winner, exposure2.94%. The252-session mean becomes permissive after
appreciation. It rejects B's Feb22–May23,2024 +23.27% entry, then C buys May22
and loses5.44% by May30. Its decisive July24–31,2025 trade loses24.96%:
entry36.13, exit27.14. SignalJuly23 forecast return.817%, adverse2.744%,
utility+.031%. July29 up probability50.0% is not enough for the retained exit.
July30 down99.9998%, close28.24 below active protection33.49; next open27.14.
Initial stop distance7.41% was not a guaranteed loss cap. Most damage was already
present at detection, and next-open execution added a3.90% close/open decline.

[Issuer filing](https://www.sec.gov/Archives/edgar/data/1479247/000110465925108406/usci-20250930x10q.htm)
describes the copper repricing around the July30 tariff announcement. This is
post-event context, not a signal or price input. Exact ETF prices are from the
pinned audited history. The intercept forecast stays positive through the shock
because labels arrive with delay; it cannot replace immediate protection.
[Incident figure](../research/entry-value-20261027-v1/CPER-incident.png),
[dated trace](../research/entry-value-20261027-v1/CPER-incident.json).

**IWM, weakest earlier C:** -17.53%, Sharpe-1.010, DD19.41%, six trades/all
losing, exposure7.67%. Rejects B's Nov9,2020–Feb1,2021 +17.89% entry; then
admits losing Feb/Mar/Apr2021 setups once its252-session mean turns positive.
March12–24 loses5.32%; April29–May11 loses6.99%. This is stale forecast memory
and entry delay, not the repaired unequal-tail semantic flaw.
[Incident figure](../research/entry-value-20261027-v1/IWM-incident.png).

TLT rejects Nov3,2023's +8.94% B trade (forecast-1.03%, utility-1.67%).
It delays Aug2,2024's B entry until Aug23, reducing same-exit gain1.53%→.30%.
WEAT never trades later, including missing B's Apr24–Jun6,2024 +8.24% rebound.
MCHI never trades later either. No claim that cash avoidance solves rebound
capture. Intercept forecasts selected for these cases cannot use current
trend/volume evidence to distinguish an emerging rebound from past down drift.

## Decision and next direction

Reject both strategy replacements. Retain symmetric directional evidence as a
model-design constraint. Preserve all previous reports and incumbent authority.

Next hypothesis: at eligible setups, forecast continuation before causal
invalidation, with event labels aligned to the intended exit policy. Compare
against a simple recent-outcome control, use chronological blocks and adequate
event counts, and score calibration/decision value at entry opportunities.
Generic daily mean-return MSE encourages a lagging mean estimator and does not
establish entry discrimination. The current fixed H outcome also differs from
the actual variable holding period. Do not tune to the inspected CPER/IWM dates.

Keep independent risk sizing/boundaries a separate component; closer daily
stops cannot guarantee protection against sudden repricing. Intraday fill
claims require audited intraday data and realistic gap/slippage contracts.
No extra HMM layer is justified yet by these results.

## Verification

40 focused tests: directional tails/filter prefix, label clock, forecast prefix,
fee/risk gates, execution lag, nonloosening stops, inherited-HMM independence
and reactivation after negative history without actual trades.612 controls
exactly reproduce frozen A;1,836 independent ledgers max error6.22e-15.
Native INDA d0, GLD d1, CPER d0 match application reference NAV to$0.00;
fractional vs whole-unit terminal returns differ as disclosed. Maximum path
gap.002500 relative NAV. Native checks frozen signals/accounting, not fitting.
306 chart combinations/date controls checked offline; static charts and math
proof inspected. Browser layout not certified.

Chart hash: `a4cb893f7f886206181b19ef11dcdaac280db212bbf0e6361fc3c59f4341d33d`.
