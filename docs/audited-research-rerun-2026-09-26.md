# Audited-history strategy and concentration rerun

Retain the current SOTA. Correcting the prices and enforcing supported raw activity removes the previous small advantage from signed constituent activity. Moving that signal earlier into allocation, selection or a residual decision tree does not establish an improvement. The fixed ETF lag-20 activity variant remains worth observing, but it is not a new SOTA.

All 24 predeclared native LEAN runs passed unchanged fill/NAV parity and artifact checks. The long comparison covers **2016-01-04–2026-09-24**, 2,697 sessions. It reconstructs the baseline recipe with annual expanding fits using completed labels, rather than applying a model trained later to earlier dates. Four companion runs use the actual deployed frozen model from **2023-01-03** onward. No trading policy, live routing, production model or promotion was changed.

## Results

Net CNH adjusted-unit returns, zero-hurdle Sharpe; IR is daily active return divided by tracking error, annualized against the matched baseline.

| Long-period variant | CAGR | Sharpe | IR | Changed monthly decisions |
| --- | ---: | ---: | ---: | ---: |
| Audited baseline | 9.84% | 0.956 | — | 0 |
| Signed constituent activity, late allocation | 9.82% | 0.955 | -0.165 | 18 |
| Signed constituent activity, early allocation | 9.82% | 0.955 | -0.172 | 18 |
| Price control, early allocation | 9.81% | 0.954 | -0.223 | 24 |
| Constituent breadth, early allocation | 9.84% | 0.957 | +0.051 | 22 |
| Signed activity in selection | 9.84% | 0.956 | undefined: identical | 0 |
| Joint constituent/price residual tree | 9.83% | 0.956 | -0.052 | 6 |
| Price-only residual tree | 9.84% | 0.957 | +0.224 | 7 |
| Constituent concentration acceleration | 9.80% | 0.953 | -0.289 | 16 |
| ETF activity, original primary parameters | 9.79% | 0.951 | -0.096 | 127 |
| ETF activity, previously selected lag-20 | 9.99% | 0.966 | +0.285 | 125 |

The baseline maximum drawdown is -15.05%; lag-20 is -14.25%. The signed signal's early-versus-late IR is -0.085: embedding it earlier did not help. Signed activity marginally beats its early price control (IR +0.124), but both trail the baseline. Adding constituent inputs to the residual price tree also detracts (IR -0.187). Those trees first act on 2026-02-02 and have only eight eligible model decisions, far too little for a durable tree conclusion.

For the deployed frozen-model comparison, baseline CAGR/Sharpe are **14.94% / 1.330**, early signed **14.90% / 1.328** (IR -0.182), and lag-20 **15.30% / 1.347** (IR +0.616). These are the shorter 2023–2026 runs, not the long-period values above.

The predeclared higher-cost and one-session-delay checks cover the baseline, early signed and early price control. Signed activity remains negative: IR -0.236 with 45 bps combined modeled costs and -0.180 with delayed execution. This rerun did not include new lag-20 cost/delay companions; earlier stress results used the previous price inputs and cannot certify the audited candidate.

The lag-20 long-period arithmetic excess is approximately **0.150 percentage points per year**, with a 63-session paired-block 95% interval of **-0.114 to +0.416 points** and family-adjusted one-sided p=**0.574**. Its IR is +0.048 in 2016–2019, +0.070 in 2020–2022 and +0.669 since 2023. This is a small, period-dependent observation, with prior parameter selection and reused history. Breadth and the price-only tree also have intervals crossing zero; none warrants promotion.

Analytical friction-matched buy-and-hold context: SPY 15.58% CAGR / 0.889 Sharpe / -32.77% drawdown; URTH 13.34% / 0.803 / -33.02%; AOR 8.57% / 0.785 / -21.66%. These are separate calculations on audited prices, not additional native LEAN runs or equivalent-risk portfolios.

## What the audit changed

Audited stock activity qualifies on **32 of 129 monthly dates**, versus 122 previously. The first qualified daily feature is **2023-07-17**, and the first qualified monthly strategy decision is **2023-08-01**. Earlier constituent overlays stay neutral. The 10.7-year portfolio test therefore is **not 10.7 years of usable constituent-signal evidence**.

The unchanged rules require at least 95% of holdings value, 70% of names, compatible dated identities, and all 211 backward observations with supported raw close/raw volume and adjusted close. In January 2016, usable value coverage is 78.90%: 8.68% is lost to identity/duplicate checks, 9.49% to unsupported raw prices, 0.78% to unsupported raw volume and 2.16% to incomplete adjusted history. January 2023 coverage is still 94.24%. The audit does not fill these gaps or reconstruct uncertain spin-off/identity episodes merely to extend a backtest.

A fixed diagnostic keeps the old stock features while replacing ETF prices and refitting causal baseline trees: early signed then returns 9.87% / 0.960, IR +0.171. Replacing those stock features and their eligibility with the audited version changes it to 9.82% / 0.955, IR -0.172. This separates the ETF correction from the combined stock-basis/coverage change; it does not isolate coverage from every other feature correction. The old-feature run was frozen solely as a legacy diagnostic and is not an approved input route for future research.

## HHI scatter plots

For each decision date, use its dated IVV constituent cohort and historical sectors. Aggregate supported **raw close × raw volume** by sector, form sector shares and compute HHI as the sum of squared shares. Raw-share-volume HHI is also retained as a sensitivity check, but depends on nominal share units and splits. Neither measure directly observes net subscriptions or money entering the market.

Daily first and second differences use backward differences. Smoothed panels use causal EMA(10), then `(E[t]−E[t−10])/10` and `(E[t]−2E[t−10]+E[t−20])/100`, calculated on the same backward-complete cohort. These are finite differences, not Hurst estimates. No new thresholds were optimized from these scatter plots.

There are **551 common signal dates, 2023-07-17–2026-04-02**, with all three future horizons observed. The 19 scatter grids cover SPY, the fixed constituent basket, dollar/share activity and all 11 sectors. Basket/sector labels use the signal-date cohort and holding-value weights; a missing selected endpoint invalidates a label, without reweighting survivors.

Pearson correlation of smoothed dollar-activity concentration with SPY's subsequent adjusted return:

| Feature | 20 sessions | 60 sessions | 120 sessions |
| --- | ---: | ---: | ---: |
| HHI level | -0.113 | -0.064 | -0.162 |
| First difference | +0.131 | +0.007 | +0.079 |
| Second difference | +0.132 | +0.051 | +0.068 |

Unsmoothed first/second differences have correlations between +0.002 and +0.013. The fixed-stock-basket results closely resemble SPY: smoothed acceleration is +0.129/+0.050/+0.069. The 20-session smoothed relationship is modest, not zero, but it does not demonstrate a profitable allocation rule. Non-overlapping offset correlations change sign; at 120 sessions no offset has the required ten observations. Paired 240-observation intervals, rank correlations and matched old/new-price comparisons are saved. These intervals are exploratory: only about 2.3 such blocks fit the qualified sample, outcomes overlap, many plots are inspected and none is an untouched holdout.

## Data contract and reproducibility

- Governing batch: `69755461f6f8088675229e9aff0f7ee8cbc2cf5a8083e126e58252e7f22dd5e3`, in `D:/systematic_trading_data/research/governed-prices-20260926-v2`.
- Research root: `D:/systematic_trading_data/lean/research/audited-rerun-20260926-v1`; frozen protocol: `config/audited-research-rerun-v1.json`.
- Rebuilt 880 constituent histories and the 12 strategy ETF series from that batch; input hashes and ClickHouse publication/row counts verified. Dated holdings are unchanged, with assumed 45/60-day publication lags. Unknown actual vintages remain unknown. IVV is an S&P 500 proxy, not a complete market census.
- ETF backtests retain the original adjusted-OHLC/source-volume convention; the ETF activity score is an adjusted-unit proxy. Stock activity uses audited raw prices and raw volume; forward returns use adjusted close. Legacy FX is unchanged with at most seven-day prior carry and remains an explicitly uncertified input class. No duplicate cash dividends are added to adjusted-unit returns.
- Frozen source, annual models, features, labels, data reads and native receipts are hash-bound. Results include all declared variants, 63/126-session block checks and matched comparisons. The coverage-based post-August-2023 slice is descriptive and was added during review, not treated as a new holdout.
- ClickHouse feature publication: 10,937 observations / 7 documents. Result publication: 925 observations / 13 documents, including the coverage decomposition; exact payload SHA256 readback verified. All 24 native runs are registered in PostgreSQL. The app's Raw Data archive exposes the combined 11,862 observations.
- Open `charts.html`, `strategy_results.png`, `spy_dollar_smoothed.png` and `basket_dollar_smoothed.png` in the research root. Raw observations, SVG exports, full statistics and hashes accompany them. Do not modify these frozen artifacts.

Next research should first resolve the historical raw-price/identity gaps in a new audited batch. Keep the coverage thresholds fixed. For lag-20, freeze prospective observation and audited-input cost/delay tests before considering promotion; for constituents, require an effect beyond price-only controls and adequate qualified history before deeper model integration. All future price research must start from audited continuous series as recorded in `AGENTS.md`.
