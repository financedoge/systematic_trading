# Research State

## Data-governance hold — 2026-09-26

The frozen ETF inputs used in the recent studies contain adjustment/source
boundary inconsistencies against a consistently collected new Yahoo vintage.
For HYG on 2026-05-26, the old snapshot implies -1.6528% versus +0.3379% in the
new governed series (1.9907 percentage points). That boundary coincides with
`sqlite_price_bars` changing to `platform_market_data_store`; SPY and LQD also
differ there. EWH has a separate discrepancy on 2026-04-30. Preserve prior
results as reproducible evidence of the old inputs, but rerun baseline and
candidate comparisons on pinned governed data before any promotion decision.
The identity audit also found older CSVs containing multiple economic issuers
under reused tickers (including NET/WMS/TXG). Recent price agreement does not
validate their earlier eras. Policy v2 quarantines periods before the current
provider listing boundary, or a conservative preferred-source identity floor
when that metadata is absent. Historical constituent research must map dated
issuer episodes rather than apply the current ticker's identity retrospectively.
The first governed build was quarantined before publication; its joined rows
are not accepted inputs. Original historical sources remain available for review.

No new strategy is elevated. See `docs/price-governance-2026-09-26.md`.


## Latest evidence — 2026-09-26 ten-year constituent follow-up

Retain current SOTA. The earlier January 2023 signal cutoff was a completeness
limit, not a deliberate short evaluation window. New dated IVV holdings and
archived public stock histories support 2016-01-04–2026-09-24: 122 of 129 monthly
decisions pass the unchanged primary 95%-value/70%-names rule. The 2020 and 2022
stress periods now have constituent observations. Histories remain revised,
publication lags are assumed, and IVV is a same-index proxy only for SPY.

Twenty-two long LEAN runs use annual expanding base trees to avoid future-label
leakage from the deployed pre-2023 fitted model. Baseline CAGR/Sharpe is
9.64%/0.932; early signed activity 9.68%/0.936/IR +0.158 trails the matched price
control 9.69%/0.937/+0.190. Its gain is 3.4bps CAGR, with a confidence interval
including zero and family-adjusted p=0.813. Joint residual-tree IR is +0.218
versus baseline but only +0.039 versus the price-only tree; concentration is
negative (-0.232). Selection changes three decisions and loses slightly. Early
signed activity worsens 2022. The four-run actual frozen-model companion has a
recent signed-activity IR +0.429 versus SOTA, only +0.105 versus price control,
and no statistically established gain. No promotion or trading-policy change.

The Market Data page now exposes the previously hidden ClickHouse research
archive, including stock bars, dated holdings, features and results. Added
2,298,993 current-provider stock observations, 85,050 holding rows and 7,595,897
public archived observations with exact readback. Final long-study features,
models and labels total 16,352 records; results/contrasts total 366. All 26
successful native receipts are registered. Public-source overlaps are preserved
as separate histories, not inserted into the canonical production daily bars.

Guide and replay: `docs/constituent-tenyear-research-2026-09-26.md`. Remaining
work is ETF-specific identity/publication quality and prospective validation of
fixed candidates, not further tuning on this inspected sample. Full suite 616
passed/51 optional skips; research/LEAN/browser lint, charts and browser checks
passed. Existing IB Gateway health remained unavailable during dashboard startup;
broker settings, orders and approval policy were not changed.

## Production Research Rule

Research is now part of a controlled research-to-paper-to-live pipeline. New candidates must compare against the current SOTA, use point-in-time data, record reproducible artifacts, and pass the promotion gates in `docs/industrial-platform-plan.md` before paper or live use.

## Alpha Factory Direction

The next research operating model should treat each alpha or factor as a versioned, independently observable contributor rather than only storing monolithic strategy runs. Before risk-parity-style alpha weighting is promoted, add contracts for factor identity and lineage, point-in-time signal values, theoretical factor returns, realized portfolio contribution, turnover/cost/capacity, correlation and covariance estimates, allocation weights, and retirement or rollback state.

Portfolio attribution should remain layered: strategy backtest NAV versus actual account NAV measures implementation divergence; reference-fill versus actual-fill PnL measures execution quality; factor-level theoretical and realized contribution explains which alphas earned or lost the portfolio result. Factor weights must be reproducible artifacts with concentration, correlation, liquidity, and regime-stability limits, not an unconstrained inverse-volatility calculation.

Use `.agents/skills/continuous-research-loop.md` for recurring challenger research and `.agents/skills/strategy-promotion-control.md` for promotion decisions.

## Current SOTA

September 26 earlier-integration follow-up: **retain current SOTA**. Nineteen
native LEAN runs test the selected signed-activity/breadth signals in earlier
allocation, pool selection and a shallow residual tree, with matched price-only
controls. Post-2023 earlier signed allocation is effectively identical to late
(14.77% CAGR / Sharpe 1.299 / IR +0.262); price-only early remains stronger
(14.79% / 1.301 / +0.301). Signed selection changes no weights or trades: SPY is
already held on 39/44 qualified dates and the other five have neutral/negative
signed scores. Breadth selection changes one decision and loses return.
The joint tree actually branches on stock breadth/signed activity, but 2025-onward
CAGR 18.84% / Sharpe 1.467 / IR -0.876 trails SOTA 19.03% / 1.474 and the price-only
tree 18.89% / 1.471. Twenty monthly model decisions begin February 2025; 19 change
allocations. Models have just 23/35 training months; future labels are excluded
and runtime features contain no outcome records. All samples were previously
inspected, so chronological fits are not an untouched holdout. Earlier placement
does not repair missing delistings, assumed availability or a U.S.-proxy-only
universe. Sources, four models, training labels, results and native receipts are
archived; no promotion. Next: ETF-specific constituent panels and fresh data
before a broader selection test. See
[earlier-integration evidence](constituent-integration-research-2026-09-26.md).

September 26 constituent follow-up: **retain current SOTA**. Five fixed stock
signals, their equal-weight primary composite, a price-only control and declared
robustness checks completed 15 native LEAN runs with unchanged parity. Historical
ITOT stocks guide only the SPY sleeve; they are a broad U.S. proxy, not exact SPY
or foreign-ETF membership. Full-period (2019-10-01–2026-09-24) primary CAGR
8.49% / Sharpe 0.782 / IR -0.394 versus SOTA 8.52% / 0.784. Concentration
acceleration IR -0.507. The 95%-value/70%-name complete-history rule first passes
January 2023, leaving 44 eligible monthly decisions and 33 composite target
changes. There is no constituent evidence from COVID/2022. Post-2023 primary
IR -0.540; signed activity has sample IR +0.262 but lags the price-only control
(+0.299), and its family-adjusted p=0.831 does not support inclusion. Do not
flip signs or refit weights on this reused history. Costs, delay, size and coverage
checks do not rescue the primary. All feature/results evidence is in ClickHouse
and native runs are registered; historical availability remains uncertified.
See [results and the constituent research plan](constituent-signals-research-2026-09-26.md).
Next: actual ETF-specific identities/holdings and earlier delisted histories;
then separately declared downside breadth, internal dispersion, filing-time
fundamental breadth and genuine issuance-confirmed crowding. No new recurring
job or paper/live strategy change.

September 26 flow/concentration research: **retain current SOTA**. Nineteen native
LEAN runs (17 predeclared plus two labeled post-hoc stresses) compare the current
12-ETF stack with activity-share acceleration, direction/Hurst/HHI/volume
ablations, a literal exit gate and parameter neighbors. Over 2013-04-01 to
2026-09-24, the predeclared primary returned 9.06% annually / 0.919 Sharpe versus
SOTA 9.11% / 0.924. A 20-session neighbor returned 9.28% / 0.935 and survived
matched higher-cost and delay checks, but full-period family-adjusted p=0.354
and weak neighborhood consistency do not support promotion. Retain that fixed
variant for observation; it was selected after results. The literal gate held
64.8% cash and returned 2.90%. Historical actual net flows, shares outstanding,
holdings and certified point-in-time constituent-sector membership remain absent; activity is not net inflow.
All runs passed unchanged parity and remain research-only. See the
[research report and data plan](flow-concentration-research-2026-09-26.md) and
`D:/systematic_trading_data/lean/research/flow-concentration-20260926-v3/`.
These numbers are a fresh adjusted-CNH LEAN comparison, not a recertification of
the older canonical artifact below. Next: timestamped net-issuance data and an
untouched prospective observation period, not more optimization on these dates.

Sector-HHI follow-up: daily Yahoo price/volume history for all eleven sector
SPDRs and SPY is now frozen separately under
`D:/systematic_trading_data/research/sector-hhi-20260926-v1/` (research only).
The 1,823 common signal dates, 2019-01-02–2026-04-02, show weak SPY return
correlations with share-volume HHI (+0.075/+0.115/+0.093 at 20/60/120 sessions)
and almost zero correlations with its daily first/second differences.
Smoothing does not establish an acceleration effect; period and dollar-volume
checks weaken the level relationship. These are descriptive overlapping-label
plots, not a new LEAN backtest or a promotion. ETF activity is not full-sector
turnover or investor net flows; historical adjustment vintages remain
uncertified. See [plots, methods and findings](sector-hhi-correlations-2026-09-26.md).

Underlying-stock follow-up: the public-data pilot now uses 95 historical monthly
ITOT equity snapshots, 3,267 populated stock histories and sector aggregates of
the stocks' own volumes/returns. It has dated sector cohorts, a modeled 45-day
publication lag and explicit missing/identity coverage, rather than today's
constituents applied to all past dates. However, only 139 common signal dates
(2025-09-15–2026-04-02) pass the 95%-value/70%-name coverage rules and have all
forward horizons observed. Raw first/second differences remain near zero in
that sample; its length and overlapping labels preclude a stable market-wide
conclusion. The longer observed-subset sample has material missing/delisted
history. The stock/fund histories and computed aggregates are archived under
ClickHouse `sector-research/<dataset>/` source prefixes. Keep SOTA unchanged.
See [underlying-sector evidence and storage guide](underlying-sector-hhi-2026-09-26.md).

September 26 audit: historical results below are retained as prior research
artifacts, not re-certified after the timing/data corrections. Missing source
vintages, fixed-universe survivorship and legacy FX lineage remain limitations.
The pre-2023 tree is fitted; post-2023 has been used repeatedly for strategy
selection and is not an untouched holdout. The new LEAN adjusted-CNH-unit scenario
has separate economics and artifacts; it does not overwrite these numbers or
promote a replacement. See [audit findings](platform-audit-2026-09-26.md) and
[LEAN workflow](lean-backtesting.md).

Paper operations now include separately tagged initial-allocation and 2 percentage point drift-maintenance proposals. Monthly signal calculation is preserved; intraday TWAP timing and additional turnover are not represented in the existing monthly benchmark. Keep attribution separate and validate execution/cost effects before live promotion.

- Name: SOTA: price/volume top 6 + technical tree + relative/adaptive
- Promoted on: 2026-05-26
- Registry: `systematic_trading.research.current_sota_definition`
- Backtest hurdle: new multi-asset research candidates should compare against this SOTA by default, not against plain risk parity.
- Canonical artifact folder: `var/backtests/sota_current/`
- Model HTML: `var/backtests/sota_current/sota_model.html`
- Promotion source artifact: `var/backtests/monthly_allweather_sleeve_variant_floor_search_20260525/`
- Prior SOTA artifact: `var/backtests/sota_current/history/2026-05-17_sota_dynamic_sleeve_commodity_guard_55/`

## Model Summary

The SOTA now uses the expanded multi-asset ETF universe and static monthly rebalancing. It keeps inverse-volatility beta weights as the foundation, then applies the best stability-adjusted daily research stack:

- Base: monthly multi-asset ETF universe, 63-bar inverse-volatility risk parity, 45% max weight, 2% cash reserve.
- Pool filter: rank assets using 63/126/252-bar price momentum and 21/126-bar volume pressure; keep the top 6, require at least 4 selected assets, require positive 252-bar momentum, and reallocate residual weight.
- Technical tree: frozen pre-2023 regression tree, max depth 3, min leaf 25, trained on 1,572 in-sample asset-month observations with MACD, Bollinger, RSI, price trend, volume pressure, drawdown, valuation, and macro features. Tilt is 16%, with active changes capped at 6% per ETF.
- Relative momentum: 20/60-bar relative momentum overlay, 12% calm and 12% risk tilt, with active changes capped at 5% per ETF.
- Adaptive trend: 63/126/252-bar trend and volume/rebound/volatility-shock gates with weak, neutral, defensive, and rebound scaling.
- Benchmark: the canonical folder includes a benchmark-only run using the same multi-asset universe and static monthly scheduler.

Canonical results versus benchmark-only multi-asset risk parity, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Window | Ann. Return | Sharpe | Calmar | Max DD | Alpha vs Benchmark | Information Ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 9.10% | 0.95 | 0.65 | -14.11% | 134.60% | 0.63 |
| In-sample | 6.89% | 0.77 | 0.49 | -14.11% | 54.07% | 0.49 |
| Out-of-sample | 16.92% | 1.48 | 2.00 | -8.46% | 28.57% | 1.13 |

Stability note: this candidate was promoted because it is cleaner than the high-OOS all-weather sleeve after penalizing weak in-sample evidence. The OOS/IS Sharpe ratio is still high at about 1.92, so it should be treated as the current best production candidate rather than a final answer to the stability objective.

## Workflow Rule

Use `scripts/export_sota_artifacts.py` to regenerate the canonical SOTA folder after a promotion. Use the multi-asset research scripts for new challengers; use legacy `scripts/compare_trend_signal.py` only for old single-basket diagnostics or to quantify value added versus the original beta sleeve.

The comparison artifacts include model structure diagrams for the SOTA and candidate:

- Layer diagram: data, rebalance schedule, base beta sleeve, overlays, final targets.
- Decision tree: the gating and transformation logic used by each model.
- HTML reports shade the out-of-sample region and mark the split date when a split is provided.

## Short-Horizon Relative Momentum Tests

Artifacts:

- `var/backtests/relative_momentum_20_40_signal_2012/`
- `var/backtests/relative_momentum_20_60_signal_2012/`
- `var/backtests/relative_momentum_40_60_signal_2012/`
- `var/backtests/relative_momentum_20_40_60_trend_rank_2012/`
- `var/backtests/relative_momentum_20_60_tilt_grid_2012/`
- `var/backtests/relative_momentum_20_60_tilt20_2012/`

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Candidate | Full Alpha vs SOTA | In-Sample Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Relative momentum 20/40d, 12% tilt | -2.31% | -1.39% | 0.16% | -0.00 | 0.02% |
| Relative momentum 20/60d, 12% tilt | -0.09% | -0.42% | 0.36% | 0.00 | 0.05% |
| Relative momentum 40/60d, 12% tilt | -1.29% | -0.80% | 0.24% | -0.00 | 0.06% |
| Three-horizon trend rank 20/40/60d, 12% tilt | -0.89% | -0.30% | -0.09% | -0.00 | 0.06% |
| Relative momentum 20/60d, 20% tilt | 1.09% | -1.02% | 1.47% | 0.01 | 0.03% |

The 20/60d shorter-horizon pair became a prior registered SOTA and remains part of the current promoted stack at a more restrained 12% calm / 12% risk tilt. A 25-case tilt grid ranked 20% calm / 20% risk tilt first by OOS alpha. It still trailed the MSCI World proxy by 0.87% OOS, versus the prior 126/252d SOTA trailing URTH by 2.34% OOS, so future work should continue using URTH as an external benchmark check.

## Latest Country-Factor Research

Added `CountryCompositeFactorOverlay` for country ETF allocation research. It can blend:

- Price trend: 63/126/252-bar relative trend ranks.
- Volume pressure: up-volume share and signed volume acceleration.
- Mean reversion: 21-bar reversal and 63-bar moving-average deviation.
- Optional valuation score maps where positive means cheaper or more attractive.
- Optional macro-growth score maps where positive means stronger country growth.

Artifacts:

- Diversified price-trend candidate: `var/backtests/country_factor_trend_only_2012/`
- Balanced multi-factor candidate: `var/backtests/country_factor_signal_2012/`
- Aggressive US macro-prior candidate: `var/backtests/country_factor_macro_us_2012/`

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Candidate | Full Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: |
| Country factor, 63/126/252d trend only, 20% tilt | 0.10% | 1.19% | 0.01 | 0.00% |
| Balanced trend/volume/mean-reversion default | -0.87% | -0.54% | -0.01 | 0.08% |
| Aggressive US macro prior, 100% macro weight, 100% tilt | 213.16% | 27.62% | 0.17 | -4.15% |

MSCI World proxy check using URTH in CNH:

| Candidate | Full Alpha vs URTH | OOS Alpha vs URTH |
| --- | ---: | ---: |
| Country factor, 63/126/252d trend only, 20% tilt | -163.54% | -1.16% |
| Aggressive US macro prior, 100% macro weight, 100% tilt | 49.51% | 25.28% |

Promotion note: these country-factor candidates were not promoted. The diversified trend-only country factor is a credible challenger but only modestly improves out-of-sample and is weaker in-sample. The aggressive US macro-prior candidate beats URTH, but it is mostly a persistent US overweight and uses a static score map across history. Treat it as a benchmark-aware stress case until point-in-time macro and valuation tables are added to the SQLite data contract.

## Signal Library And Decision Tree

The code-backed signal library is in `systematic_trading.signals.library`; the human-readable table is `docs/signal-library.md`. Decision-tree runs also write `signal_library.md` and `decision_tree_training.json` in their output directory.

Decision-tree candidate:

- Artifacts: `var/backtests/decision_tree_signal_tilt20_2012/`
- Training sample: 655 in-sample asset-month rows, ending before the 2023-01-01 split.
- Features: 16 signal-library features from that run, covering trend, mean reversion, volume, risk regime, valuation score, and macro-growth score. The library now also includes the promoted 20/60d momentum features for future training runs.
- Model: max-depth 3 regression tree, min leaf 25, target is next-rebalance asset return minus cross-sectional basket mean.
- Learned first split: `macro_growth_score <= 0.5`, then short momentum, extended momentum, and volatility ratio.

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29:

| Candidate | Full Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: |
| Decision tree, depth 3, 20% tilt | 29.00% | 0.50% | 0.01 | 0.08% |

MSCI World proxy check using URTH in CNH:

| Candidate | Full Alpha vs URTH | OOS Alpha vs URTH |
| --- | ---: | ---: |
| Decision tree, depth 3, 20% tilt | -134.64% | -1.84% |

Promotion note: do not promote the decision tree yet. It helped versus the prior 126/252d SOTA OOS, but the OOS edge was small, the tree uses a static macro score map, and it still trails URTH. It is useful as an interpretable research candidate and a framework for point-in-time macro/valuation data once those tables exist.
