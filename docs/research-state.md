# Research State

## Current SOTA

- Name: SOTA: risk parity + relative momentum 20/60d 20% tilt
- Promoted on: 2026-05-05
- Registry: `systematic_trading.research.current_sota_definition`
- Backtest hurdle: new research candidates should compare against this SOTA by default, not against plain risk parity.
- Artifact: `var/backtests/relative_momentum_20_60_tilt20_2012/`

## Model Summary

The SOTA keeps the monthly risk-parity beta sleeve as the foundation, then applies a shorter-horizon regime-gated relative momentum overlay:

- Base: 63-bar inverse-volatility risk parity, 45% max weight, 2% cash reserve.
- Score: 45% short-term momentum over 20 bars plus 55% medium-term momentum over 60 bars.
- Regime: risk regime if average basket drawdown is at or below -8% or volatility ratio is at or above 1.35.
- Tilt: 20% in calm regimes and 20% in risk regimes.
- Risk control: cap active weight changes at 7% per ETF, then rescale to preserve the original invested weight.

## Workflow Rule

Use `scripts/compare_trend_signal.py` with the default `--baseline-model sota` for new research. Use `--baseline-model risk-parity` only for legacy diagnostics or to quantify the value added versus the original beta sleeve.

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

The 20/60d shorter-horizon pair is now the registered SOTA because future iterations should benchmark against this version. A 25-case tilt grid ranked 20% calm / 20% risk tilt first by OOS alpha. It still trails the MSCI World proxy by 0.87% OOS, versus the prior 126/252d SOTA trailing URTH by 2.34% OOS, so future work should continue using URTH as an external benchmark check.

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
