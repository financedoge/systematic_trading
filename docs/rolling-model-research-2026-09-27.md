# Rolling model research — September 27, 2026

Status: **Complete: 41 native LEAN runs passed parity; retain current SOTA.** The user requested one- and
two-year rolling training windows, decision trees, forests and XGBoost, and
authorized extended background runs. They subsequently requested parallel fits
using all CPU cores. The finite application research job owns the calculations.

## Findings

The one-year forest and XGBoost improve this historical comparison against the
deployed tree. Evidence that *rolling retraining itself* adds value is much
weaker: their frozen pre-2023 counterparts perform almost as well.

January 3, 2023–September 24, 2026, net of 5bps simulated transaction fees:

| Model | CAGR | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: |
| Deployed frozen SOTA | 14.94% | 1.330 | -8.49% |
| Rolling tree, 1 year | 15.21% | 1.332 | -8.56% |
| Rolling tree, 2 years | 15.12% | 1.322 | -8.67% |
| Rolling forest, 1 year | 15.75% | 1.372 | -8.50% |
| Rolling forest, 2 years | 15.42% | 1.343 | -8.46% |
| Rolling XGBoost, 1 year | 15.88% | 1.381 | -8.40% |
| Rolling XGBoost, 2 years | 15.36% | 1.343 | -8.55% |
| Frozen forest | 15.68% | 1.356 | -8.39% |
| Frozen XGBoost | 15.72% | 1.365 | -8.44% |
| SOTA with tree removed | 15.49% | 1.360 | -8.50% |

One-year XGBoost beats deployed SOTA by 0.944 annual percentage points, but beats
frozen XGBoost by only 0.159 points. One-year forest adds 0.809 points over SOTA,
but only 0.063 over frozen forest. Two-year ensembles underperform their frozen
family controls. Paired 63-session rolling-versus-frozen intervals include zero:
XGBoost annual arithmetic excess -0.337 to +0.609pp, adjusted p=0.529; forest
-0.402 to +0.509pp, p=0.692. The 126-session check agrees with that uncertainty.

Versus deployed SOTA, the primary one-year forest/XGBoost comparisons have
63-session family-adjusted p=0.020/0.014 and 126-session p=0.041/0.025. These are
conditional exploratory statistics on repeatedly inspected historical data.
Against tree-free SOTA, one-year XGBoost's six-candidate adjusted p is 0.074.
Changing/removing the existing tree explains much of the apparent improvement.

Cost, delay and seed checks preserve the one-year ensemble gains versus SOTA.
XGBoost CAGR spans 15.77–15.88% across three seeds; forest spans 15.75–15.98%.
XGBoost's gain remains +0.934pp with the high-cost scenario and +0.728pp with an
extra execution-day delay. Gains are concentrated in 2025–2026. Long-history
CAGR is 9.63% for reconstructed SOTA, 9.97% for one-year forest and 9.94% for
one-year XGBoost; long family-adjusted p=0.068/0.108. All variants lag in 2020;
one-year XGBoost also slightly lags in 2022. No uniformly better strategy is
established.

Decision: retain current SOTA and its tracking/execution definitions. One-year
forest and XGBoost are promising research candidates; compare their fixed
rolling and frozen recipes prospectively before promotion. Do not add them to
tracked strategies without the complete app-owned strategy/report contract.

Full charts/report: `D:/systematic_trading_data/lean/research/rolling-models-20260927-v1/report.html`.
Detailed metrics: `metrics.csv`; causal fits and all intervals: `summary.json`.

## Fixed experiment

The protocol is `config/rolling-model-research-v1.json`. All settings were fixed
before performance results. The study has 41 native LEAN runs:

- Six primary variants: CART, random forest and XGBoost, each using a trailing
  one- or two-calendar-year window and a fresh fit at every monthly rebalance.
- Actual deployed frozen SOTA, frozen pre-2023 forest/XGBoost, tree-free SOTA and
  matched risk parity controls. Each starts with CNH 1,000,000 on January 3, 2023.
- Six long variants, tracked SOTA reconstruction and risk parity from January 4,
  2016, covering COVID and 2022. The reconstructed comparator uses annual causal
  trees before 2023 and the actual frozen deployed tree thereafter.
- Higher cost (25bps fees plus 20bps slippage) and one-session delayed execution
  for every primary variant and the same frozen SOTA comparator: 14 runs.
- Forest and XGBoost variants repeated with seeds 17 and 97: eight runs.

The main window ends September 24, 2026. This endpoint matches the pinned
historical FX file; it is not a claim that later prices are missing. Audited URTH
buy-and-hold provides additional benchmark context.

## Causal training and model contracts

The 26 existing SOTA features and next-month relative-return target are retained.
Valuation and macro inputs remain their existing zero placeholders. Features
are physically restricted to bars before the decision's execution session.
Historical warmup can precede the training window; retained training *origins*
must fall inside the trailing calendar-year window. Labels must end strictly
before the fit close, excluding the outcome that ends at that same close.
Missing/nonfinite feature observations are excluded without imputation.

The label is adjusted USD close-to-close monthly return minus the equal-weight
cross-sectional ETF return, consistent with the existing model's convention.
The main test replaces only the bounded 16% tree ranking tilt. The ETF universe,
top-six selection, inverse-volatility allocation, relative momentum and adaptive
trend overlays, cash reserve and execution assumptions remain fixed.

CART uses the existing depth-three/minimum-leaf-25 implementation. Random forest
uses 100 trees, depth three, leaf size 25 and 75% feature sampling. XGBoost uses
100 rounds, depth three, learning rate 0.03, child weight 25, lambda 10, row
sampling 80% and feature sampling 75%. No search or evaluation-based early
stopping is performed. Random state is recorded for every fit.

Training uses optional pinned scikit-learn 1.8.0/XGBoost 3.2.0 dependencies on D:.
Portable frozen trees preserve float32 input/split semantics and are checked
against native library predictions. LEAN inference needs no new dependencies.
Models record the window, actual training dates/sample count, training-row hash,
parameters and prediction equivalence error. No future fitted tree fallback is
allowed. An insufficient or invalid schedule fails closed.

## Audited data and limitations

Batch `69755461f6f8088675229e9aff0f7ee8cbc2cf5a8083e126e58252e7f22dd5e3`
must be committed in ClickHouse; every used local publication file is hash
verified. Every ETF must have the complete observed session calendar. Inputs
use audited dividend/split-adjusted OHLC and the existing audited split-adjusted
source volume convention. Activity features are adjusted proxies, not raw-dollar
turnover or actual net flows. Provider archives are not read as research inputs.

Chronological fitting prevents future outcome leakage conditional on these
histories. Revised historical price vintages, fixed-universe survivorship and
legacy USD/CNH FX remain uncertified. The inspected sample is not an untouched
holdout. Simulation uses adjusted CNH units and next-open fills with instantaneous
settlement; no claim is made about intraday TWAP, capacity or actual account PnL.

## Evaluation and evidence

Report CAGR, zero-hurdle Sharpe, drawdown, turnover, fees, concentration, decision
changes and active information ratio; show each calendar year and stress period.
Use paired 63/126-session bootstrap blocks, 5,000 resamples and max-t adjustment
across all six primary candidates. Report both seed checks and all matched cost
and delay outcomes. Keep positive point estimates distinct from stable evidence.

Frozen source, input manifest, models, fitted-row hashes and complete per-trial
decisions/fills/NAV are retained under:

`D:/systematic_trading_data/lean/research/rolling-models-20260927-v1/`

The completed job wrote `summary.json`, `metrics.csv`, `report.md`, `report.html`,
`performance.png`, `robustness.png` and `rolling_increment.png`. Native receipts entered the append-only
PostgreSQL research registry. NAV, metrics and report documents publish to
ClickHouse with exact readback: 52,749 NAV/metric observations and six documents,
with 41 registered native receipts. `analysis_manifest.json` hashes report and
chart artifacts. Tracking membership and promotion/execution
authority are separate and are not changed by this experiment.

## Execution and recovery

`scripts/run_rolling_model_research.py` prepares, fits and runs the fixed matrix.
Independent monthly fits use all 16 logical cores, one numerical-library thread
per process. Eight simulation processes each use the existing two-CPU isolated
LEAN container. Source dependencies are loaded through the explicit research
`PYTHONPATH`; the production virtual environment was not modified.

Run from the repository with the optional `rolling-research` dependencies:

```powershell
$env:PYTHONPATH = 'D:/systematic_trading_data/research/rolling-model-deps;D:/projects/systematic_trading/src'
.\.venv\Scripts\python.exe scripts/run_rolling_model_research.py --phase all --workers 8
.\.venv\Scripts\python.exe scripts/analyze_rolling_model_research.py --root D:/systematic_trading_data/lean/research/rolling-models-20260927-v1 --publish
```

Completed schedules and successful runs are hash-verified and reused. A failed
or interrupted run is retained for inspection rather than silently overwritten.
The initial threaded target-generation attempt was stopped while switching to
process parallelism; its eight unfinished receipts are retained separately in
`interrupted_thread_runs/`. Their complete input bundles are reused for a fresh
run. The preflight also corrected two frozen-control model fit dates to the last
available session close; earlier unused schedules are retained under
`model_preflight_rejected/`. Neither adjustment used performance results.

One native long-SOTA attempt stalled at its first time step with near-idle CPU;
its failed receipt is retained in `stalled_native_runs/`. Retrying the identical
verified bundle completed in 60.7 seconds and passed all parity tolerances.
All finite workers completed; no recurring agent calculation was installed.

Focused model/LEAN/tracked regression: 45 passed, one optional integration skip.
Extended causal/feature/strategy checks: 67 passed, one optional integration skip.
Native portable-prediction tests use unseen inputs as well as training rows.
Ruff checks pass. All 41 native runs passed parity, and all three figures were
visually inspected. No broker or approval-policy mutation occurred.

Sources: [forest parameters](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.RandomForestRegressor.html),
[XGBoost Python documentation](https://xgboost.readthedocs.io/en/stable/python/python_intro.html).
