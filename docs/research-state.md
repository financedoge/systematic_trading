# Research State

## Current SOTA

- Name: SOTA: risk parity + relative momentum 126/252d regime
- Promoted on: 2026-05-05
- Registry: `systematic_trading.research.current_sota_definition`
- Backtest hurdle: new research candidates should compare against this SOTA by default, not against plain risk parity.

## Model Summary

The SOTA keeps the monthly risk-parity beta sleeve as the foundation, then applies a regime-gated relative momentum overlay:

- Base: 63-bar inverse-volatility risk parity, 45% max weight, 2% cash reserve.
- Score: 45% medium-term momentum over 126 bars plus 55% long-term momentum over 252 bars.
- Regime: risk regime if average basket drawdown is at or below -8% or volatility ratio is at or above 1.35.
- Tilt: 12% in calm regimes and 12% in risk regimes.
- Risk control: cap active weight changes at 7% per ETF, then rescale to preserve the original invested weight.

## Workflow Rule

Use `scripts/compare_trend_signal.py` with the default `--baseline-model sota` for new research. Use `--baseline-model risk-parity` only for legacy diagnostics or to quantify the value added versus the original beta sleeve.

The comparison artifacts include model structure diagrams for the SOTA and candidate:

- Layer diagram: data, rebalance schedule, base beta sleeve, overlays, final targets.
- Decision tree: the gating and transformation logic used by each model.
