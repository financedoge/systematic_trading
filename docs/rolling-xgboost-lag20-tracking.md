# Rolling one-year XGBoost with ETF activity lag-20

The application tracks `research_rolling_xgboost_1y_lag20_v1` as a complete candidate alongside SOTA and ETF activity lag-20. The original rolling-model study did **not** include activity. This candidate replaces SOTA's regression-tree tilt with monthly rolling XGBoost and applies the existing lag-20 activity overlay after the other SOTA steps.

Open the strategy workspace at `/strategies`, or the full report at `/api/v1/strategies/research_rolling_xgboost_1y_lag20_v1/report`.

## Strategy specification

1. Use the published audited, dividend/split-adjusted histories for SPY, VGK, EWJ, EWH, EWY, MCHI, IEF, TLT, LQD, HYG, GLD and DBC. Preserve the versioned universe order during training. Return labels use USD ETF prices; portfolio accounting uses supported USD/CNH observations.
2. On the first trading session each month, calculate targets using data through the previous session. Start with 63-session inverse-volatility weights, a 45% base cap and 2% cash reserve.
3. Apply the existing price/volume top-six filter, with its trend eligibility and minimum-four fallback.
4. Select the XGBoost fit from the prior month's final trading session. Use the model forecast ranks for the unchanged 16% relative tilt and 6 percentage point **pre-normalization** delta cap, then restore the stage's original gross exposure. This is the same sizing contract tested in the rolling study.
5. Apply SOTA's 20/60 relative momentum and adaptive trend overlays.
6. Apply ETF activity lag-20: relative adjusted-close × source-volume activity, prior 63-session normalization, EMA 10, lag-20 second difference, prior 126-session noise, z threshold ±0.5. Positive activity requires positive slope, 20-session return and signed volume. Use a 15% relative tilt, final ±3 percentage point bounds, preserve gross exposure and existing selections. Hurst filtering is disabled. An inherited weight above 45% cannot increase through this overlay.
7. Simulate next-session opening fills in whole CNH-adjusted units, sells before buys, cash constraints and 5 bps fees. Mark held quantities daily. Latest indicative targets are recalculated from fresh completed prices using the current monthly model; they do not cause interim rebalances.

Activity is a separate allocation overlay, not an extra learned XGBoost input. Its proxy does not measure net subscriptions/redemptions or audited raw turnover.

## Monthly fitting and causal bounds

The registered recipe is `rolling-xgboost-1y-v1`: 100 trees, depth 3, learning rate 0.03, minimum child weight 25, row subsampling 0.8, column subsampling 0.75, L2 penalty 10, L1 penalty 0, squared-error objective, histogram method, zero base score and fixed seed 20260927. XGBoost 3.2.0 and scikit-learn 1.8.0 are pinned; the receipt also records NumPy's version. Install `.[rolling-research]` in the application environment when enabling this candidate on another host.

Training observations are monthly ETF observations, not daily returns. Feature dates must fall within one trailing calendar year and labels must finish **strictly before** the fit close. The label is the next month's adjusted USD return minus that month's cross-sectional ETF mean. The embargo excludes the just-finished month at its own closing fit. At least 100 complete observations are required, usually 120–132 observations across 10–11 months. Indicator lookbacks can extend 378 sessions before a training observation; this does not expand the set of fitted outcomes beyond the one-year window.

The 26 inputs match the original experiment: momentum, relative momentum, moving-average position/reversion, MACD, Bollinger measures, RSI, up-volume/signed-volume measures, volatility ratio and drawdown. External valuation and macro scores are neutral zeros. The full report lists each definition and every ETF's current input values. App-generated training records were compared exactly with all 1,884 records in the original audited experiment.

The analytics service launches an isolated application training process. Independent fits use all logical cores with one numerical-library thread per fit. Portable frozen tree inference is validated against native XGBoost and runs inside LEAN without installing training libraries there. Identical individual fits are cached by their actual training inputs, cutoff, recipe, source hashes and library versions. A new price publication can update current features without fitting the same month again. Changed historical inputs create separate fitted evidence. Missing monthly models, wrong recipes, future labels and changed artifacts fail closed.

## Full strategy page

The shared SOTA report includes:

- NAV, drawdowns, yearly/quarterly/monthly metrics, holdings, contribution and combined signal attribution.
- Matched risk parity, URTH, SOTA, lag-20 with the frozen SOTA tree, and rolling XGBoost without activity as selectable benchmarks. The last two isolate the contribution of each candidate change.
- Daily value and held weights, last scheduled targets, indicative latest targets, data-through dates and next rebalance.
- Current model training window, completed-label cutoff, sample count, immutable hashes, dependency versions, training parameters and downloadable fitted model.
- Current forecasts and activity signals; exact allocation weights after every executable strategy step.
- Full strategy flow and all 100 fitted trees with feature thresholds, branch directions, leaf contributions, tree selection and zoom.

The forecast sums shrunken leaf contributions, using XGBoost's strict `<` comparisons and float32 behavior. It is a ranking score, not a calibrated profit forecast.

## Evidence and operation

The app owns fitting, signal calculation, rebalances, portfolio accounting and publication. **Refresh calculations** queues that service. Immutable requests, attempts, training data, fitted schedules and receipts live under `var/tracked_models/`; native bundles, source snapshots and parity receipts live under `var/tracked_strategies/<revision>/`. All monitored candidates and their controls publish atomically to ClickHouse; successful native receipts are registered in PostgreSQL. Failed calculations retain the prior complete publication.

The chart starts in 2016. SOTA and activity-only controls use causal annual trees before 2023 and the deployed frozen tree from 2023; rolling XGBoost refits monthly throughout. The 2023 boundary is a retrospective comparison boundary. The candidate was chosen after reviewing historical results; prospective tracking starts **2026-09-28**. The earlier 15.88% post-2023 CAGR belongs to XGBoost **without** activity and must not be attributed to the combined candidate.

Historical price vintages remain revised rather than certified historical-publication snapshots. Legacy FX through September 24 remains uncertified; later FX requires observed and validated USD/CNH evidence. Missing observations are not filled or replaced. New prices must pass audit and publication before they enter these calculations.

Tracking grants no promotion or execution authority. SOTA remains selected for the existing paper workflow. Promotion still requires separate prospective and robustness evidence, risk limits and operator approval.

## Initial publication — September 27, 2026

All five native LEAN runs passed Python target/fill/cash/NAV parity. The 129 app-fitted models and 1,884 training records exactly match the original experiment; the XGBoost-only control reproduces its entire historical NAV through September 24. SOTA and activity-only economic outputs are exactly unchanged from their previous app publication.

| Monitored strategy | Annualized return | Sharpe | Maximum drawdown |
| --- | ---: | ---: | ---: |
| SOTA | 9.656% | 0.9492 | -15.055% |
| ETF activity lag-20 | 9.799% | 0.9583 | -14.253% |
| Rolling 1y XGBoost + ETF activity lag-20 | 10.093% | 0.9675 | -15.336% |

These are descriptive results from the 2015-12-31 initial-capital anchor through 2026-09-25, using the shared report's calendar-year annualization. The combined candidate finishes at CNH 2,807,393.56 from CNH 1 million. It improves historical return while having a deeper maximum drawdown than either existing tracked strategy. No prospective observations exist yet.

The initial current model is dated 2026-08-31: window starts 2025-08-31, 120 observations over 10 months, latest completed label 2026-07-31. Current targets use prices through September 25; the next scheduled rebalance is October 1. All 16 cores were used for the historical fits (10.3 seconds for the final preparation).

ClickHouse publication `0d277ed7bb486f16db29250a9eddc0782bd073d625ac1f24e10b5232e5c5873c` contains 8,100 observations and seven documents; five successful native receipts are registered in PostgreSQL. Native artifacts are in `var/tracked_strategies/<publication>/`. Acceptance evidence is `var/research/rolling-tracking-acceptance.json`.

Validation: full suite 686 passed / 51 optional skips; final affected checks 41 passed / one optional skip. Both rendered JavaScript blocks parse. Browser checks cover registry navigation, held/scheduled/indicative weights, forecast and feature tables, all 100 selectable trees, tree/flow zoom, benchmark switching and a completed app refresh without a new tracked calculation. No browser console errors. Paper approval policy is unchanged.

An initial native attempt exposed a live-package import that required a database driver inside LEAN. Model selection now uses the already validated input calendar without operational imports. A regression test blocks live, execution, storage and training dependencies during inference. The rejected calculation revision remains intact as audit evidence; it was never published as the candidate.
