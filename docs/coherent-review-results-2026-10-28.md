# Shared forecast and evidence-change review

Completed the full supported ETF experiment. The new decision rules remove the
previous unchanged-evidence reversal conflict, but neither reviewer improves the
pool sufficiently to replace the standing-protection control. XLU is a promising
case for further research, not a selected tradable exception.
[Interactive report, formulas and every ETF chart](../research/coherent-review-20261028-v1/index.html).
No portfolio overlay, promotion, monitoring, broker or live changes.

## Frozen design

Protocol SHA256
`0d6536c40954294011db18ae7aae33ec5f65302204d2c869f8356ff055a4c459`.
Published audited batch
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`;
verified adjusted OHLC and raw share volume. No provider archives or online prices.
Auditing does not establish historical publication vintages. Both evaluation
periods have been repeatedly inspected and are development evidence.

Three main arms: A unchanged standing protection; B shared price forecast;
C shared price/volume forecast. Each ETF separately fits one normalized return
target, used in both holding and recovery decisions:

`a_t = max(ATR20_t / close_t, 0.0001)`;
`Y_t = (open_(t+2) / open_(t+1) - 1) / a_t`.

The label matures at open t+2. This is an underlying one-session forecast, not
a Bellman action value or actual stop-clipped trade return. The horizon is fixed
for this consistency experiment, not established as the right trend timescale.
Price inputs are daily/three-day returns, distance to EMA10, EMA10-minus-EMA60,
and close location, with ATR scaling. C adds log relative raw volume, signed
volume pressure and volume/close-location interaction. Full equations are in
the report. Position state, entry price and HMM states are absent from features.

Use at most 756 matured training origins after 252 warmup sessions. Three
expanding validation folds refit their own scaler and constant/ridge 1/10/100
models. Purge labels whose maturity reaches the validation boundary. Minimum
mean validation MSE selects the model; constant and stronger shrinkage win ties.
Enable only a nonconstant model improving MSE by more than 0.5%, with improvement
in at least two folds. Otherwise the reviewer abstains. Refit the selected model
on all matured training observations. This reviewer calibration is independent
of the parent HMM, whose inherited selection is not made fully nested by this work.

With shared score u, extra exits require `u < -0.05` and
`u < entry_signal_score - 0.10`. Recovery requires predicted return after
round-trip fees above +0.05 ATR units and `u > sale_close_score + 0.10`.
Margins were fixed before evaluation. Ordinary HMM entries keep priority;
negative forecasts alone do not veto them. Recovery considers 1–20 sessions
after sale; an opening deviation exceeding one signal-date ATR cancels the buy.
Recovery ownership defers HMM exits until upward confirmation, including while
a delayed recovery buy is pending. Protection and learned exits remain active.
No online coefficient changes, resets or permanent pauses were introduced.

## Results

Medians across risky single-ETF strategies, excluding BIL, at 5 bp each side plus
5 bp stop slippage. These are not portfolio metrics. Later: January 3, 2023 to
October 16, 2026; earlier: January 2, 2020 to December 30, 2022.

| Period | Model | Net cumulative return | Net CAGR | Net Sharpe |
|---|---|---:|---:|---:|
|Later|A protection|11.39%|2.90%|0.402|
|Later|B price|11.39%|2.90%|0.397|
|Later|C price/volume|11.39%|2.90%|0.402|
|Earlier|A / B / C|6.33%|2.07%|0.312|

Both challengers fail all 12 era/friction settings: 5/10/20 bp per side and
zero/one extra session delay. Acceptance requires higher median Sharpe and
lower-quartile CAGR plus 90% of ETFs within 1pp CAGR/2pp drawdown of A. Median
equality mostly reflects abstention, not successful active review. Training
enables later B only for LEMB/XLU, later C only for ITA/MBB, earlier B only for
XLU, and earlier C for none. All five enabled fits have evaluation forecast MSE
worse than the constant benchmark, despite their small training gains.

### XLU: useful case, incomplete evidence

| Period | A return | B return | A Sharpe | B Sharpe | A max drawdown | B max drawdown |
|---|---:|---:|---:|---:|---:|---:|
|Later|24.27%|48.55%|0.587|1.024|15.59%|8.46%|
|Earlier|23.01%|35.41%|0.595|0.711|12.86%|13.69%|

B recovery trades October 10–December 22, 2023 and February 5–April 12, 2024
earn 9.25% and 7.21%. Return advantages remain positive in all 12 cost/delay
cases, but later 20 bp plus extra delay leaves only 0.30pp advantage. Earlier
10 bp without extra delay leaves only 0.09pp return advantage while Sharpe
worsens 0.058 and drawdown worsens 6.07pp. Costs change recovery eligibility,
so this is not a simple fee subtraction. Forecast IC is +0.015 later and
−0.023 earlier; MSE worsens the constant in both. This supports examining the
trades, not a claim of proven predictive alpha. C component ablations cannot
attribute XLU's B gain because the C reviewer is disabled for XLU.
[Recovery inspection](../research/coherent-review-20261028-v1/XLU-recovery.png).

### ITA: a one-session warning can cut a longer winner

Later C reduces return from 38.48% to 19.72%, despite reducing drawdown from
17.74% to 12.53%. Nine of twelve recoveries win, but the full outcome worsens.
The October 12, 2023 entry returns 10.56% under A, sold January 10, 2024;
C sells October 20 for −2.31%. C exit-only returns 9.87%, recovery-only 45.76%,
no-change gate 23.77%, no-handoff 9.75%, weekly review 26.85%. None justifies
selecting a component after inspection. LEMB B and MBB C also worsen in every
cost/delay setting. Coherent rules do not prove that changed daily evidence
invalidates a longer trade thesis.

### Preserved assets and weakest cases

WEAT later returns −15.98% and GLD +52.22%, identical to A, compared with the
previous trained review's −45.79% and +6.65%. Both new reviewers abstain. This
prevents the old conflict without demonstrating better active market recognition.
CPER March 4–September 4, 2025 remains +10.00%; IWM July 1–December 1, 2024
remains −9.64%. Review is disabled in both cases.

Weakest risky C by net cumulative return:

- **CORN later: −22.73%, Sharpe −0.521, drawdown 29.56%.** All arms identical;
  reviewers disabled. Seventeen completed trades, five wins. July 19–31, 2023
  loses 6.27% as the apparent fast rebound fails inside a slow downtrend.
  [Full chart](../research/coherent-review-20261028-v1/CORN_late.png) and
  [loss inspection](../research/coherent-review-20261028-v1/CORN-loss.png).
- **MCHI earlier: −34.96%, Sharpe −0.685, drawdown 48.87%.** All arms identical;
  reviewers disabled. Twenty-six trades, seven wins. June 29–July 8, 2021
  loses 8.75%, including an opening gap through the active adjusted $69.30 stop
  to a scheduled exit fill at $67.42. Stop distance does not cap gap losses.
  [Full chart](../research/coherent-review-20261028-v1/MCHI_early.png) and
  [loss inspection](../research/coherent-review-20261028-v1/MCHI-loss.png).

## Next research question

Retain the original research reference. Preserve shared forecasts, abstention
and changed-evidence requirements as consistency safeguards. Test whether a
trade-thesis horizon or time-to-invalidation target can distinguish a temporary
pullback from a failed reversal, against this one-session control. Labels and
continuation policy must agree, and learning must use only matured observations.
Keep full-pool, cost/delay and good-asset preservation checks; show weakest
cases each round. No post-evaluation tuning was performed in this run.

## Verification and recipe

1,836 main plus 816 diagnostic cases on 52/50 ETFs. 612 exact parent controls,
612 exact disabled-review paths, maximum independent ledger discrepancy
5.55e−15. Forty-two focused Python tests pass: 39 model tests and three artifact
contracts. Offline interaction checks cover 306 ETF/era/model combinations,
OHLC readouts, exact dates, two-click selection, interval NAV, trades and events.
Representative figures and mathematical equations were visually inspected;
browser layout is not certified.

Native Windows LEAN accounting fixtures for CPER/IWM/CORN later and MCHI
earlier match their whole-unit reference to $0. These use synthetic fill/mark
event calendars and validate accounting, not market execution or reviewer inference.

Recipe: `scripts/research_coherent_review.py` prepare/fit/evaluate;
`scripts/analyze_coherent_review.py`; `scripts/inspect_coherent_review.py`;
`scripts/build_coherent_review_report.py`; `scripts/validate_coherent_review.py`;
`scripts/seal_coherent_review.py`. Retain frozen fits, compact findings, QA and
artifact hashes. Frozen engine, runner and model tests were unchanged after prepare.
