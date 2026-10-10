"""Shared target computation for the reference and LEAN, using only prior bars."""
from datetime import date
from decimal import Decimal

from systematic_trading.backtest.stored import _target_schedule
from systematic_trading.domain.market import PriceBar
from systematic_trading.research import instruments_for_definition, instantiate_overlays
from systematic_trading.research.strategy_catalog import legacy_sota_definition
from systematic_trading.research.flow_concentration import (
    FlowConcentrationSpec, concentration_features, apply_concentration_targets,
)
from systematic_trading.research.constituent_signals import (
    ConstituentOverlaySpec, selected_score, apply_constituent_targets,
)


def targets_for_day(rows: dict, day: date, *, benchmark: bool = False, lookback_bars: int = 63,
                    flow_overlay: FlowConcentrationSpec | None = None, flow_state: dict | None = None,
                    constituent_overlay: ConstituentOverlaySpec | None = None, constituent_features: dict | None = None,
                    base_tree_models: dict | None = None, fixed_model_from: str | None = None,
                    definition=None, usd_models=None, economic_models=None, raw_rows=None):
    if constituent_overlay is not None and (benchmark or flow_overlay is not None or constituent_features is None):
        raise ValueError('Constituent overlay needs frozen features and an unmodified SOTA base')
    if benchmark and flow_overlay is not None:
        raise ValueError('Flow overlay requires the SOTA base')
    # Schema-v1 implicit 'sota' bundles retain their original recipe. New SOTA
    # runs use the explicit, versioned registered definition and USD inputs.
    definition = definition or legacy_sota_definition()
    instruments = instruments_for_definition(definition)
    histories = {
        symbol: [PriceBar.model_validate(row) for row in values if date.fromisoformat(row['trade_date']) < day]
        for symbol, values in rows.items()
    }
    if min(len(bars) for bars in histories.values()) < 253:
        raise ValueError(f'Insufficient warmup before {day}; 253 prior observations required')
    overlays = list(instantiate_overlays(definition))
    for overlay, spec in zip(overlays, definition.overlays, strict=True):
        if spec.kind == 'usd_ridge':
            overlay.schedule = usd_models
        elif spec.kind == 'economic_ridge':
            overlay.schedule = economic_models
        elif spec.kind == 'financial_rank_selection':
            overlay.schedule = economic_models
            overlay.rolling_schedule = base_tree_models
        elif spec.kind == 'audited_etf_activity':
            if raw_rows is None:
                raise ValueError('Audited raw activity input required for this strategy')
            overlay.raw = {s:[PriceBar.model_validate(r) for r in values if date.fromisoformat(r['trade_date']) < day]
                           for s,values in raw_rows.items()}
    rolling = [o for o, s in zip(overlays, definition.overlays, strict=True) if s.kind == 'rolling_model']
    if rolling and (base_tree_models is None or fixed_model_from is not None):
        raise ValueError('Rolling strategy requires a model schedule for the entire history')
    if base_tree_models is not None and (fixed_model_from is None or str(day) < fixed_model_from):
        if benchmark:
            raise ValueError('A benchmark cannot use a tree schedule')
        from systematic_trading.research.chronological_tree import select_base_tree
        trees = [o for o, s in zip(overlays, definition.overlays, strict=True) if s.kind in ('decision_tree', 'rolling_model')]
        selection_only = not trees and any(s.kind == 'financial_rank_selection' for s in definition.overlays)
        if len(trees) != 1 and not selection_only:
            raise ValueError('Dated base-tree schedule requires exactly one decision-tree overlay')
        if rolling:
            from systematic_trading.research.rolling_tracking import select_rolling_model
            trees[0].model = select_rolling_model(base_tree_models, histories, day)
        elif not selection_only:
            trees[0].model = select_base_tree(base_tree_models, str(histories['SPY'][-1].trade_date))
    targets = _target_schedule(
        instruments=instruments, bars_by_symbol=histories, trade_dates=[day],
        rebalance_frequency='daily', lookback_bars=lookback_bars, max_weight=Decimal('0.45'),
        cash_reserve_weight=Decimal('0.02'), sleeve_name=definition.sleeve_name,
        target_overlays=() if benchmark else overlays,
    )[day]
    if flow_overlay is not None:
        return apply_concentration_targets(targets, concentration_features(histories, flow_overlay),
                                           flow_overlay, flow_state)
    if constituent_overlay is not None:
        known = str(histories['SPY'][-1].trade_date)
        score = selected_score(constituent_features, day, known, constituent_overlay)
        if constituent_overlay.stage == 'late':
            return apply_constituent_targets(targets, score, constituent_overlay)
        row = constituent_features.get(str(constituent_overlay.holdings_lag_days), {}).get(known)
        if row is None or row.get('scores') is None or row['value_coverage'] < constituent_overlay.min_value_coverage or row['name_coverage'] < constituent_overlay.min_name_coverage:
            return targets
        from systematic_trading.research.constituent_integration import integration_overlays, constrain_to_base
        overlays = integration_overlays(overlays, constituent_overlay, score, constituent_features, known, row)
        if overlays is None:
            return targets
        candidate = _target_schedule(
            instruments=instruments, bars_by_symbol=histories, trade_dates=[day],
            rebalance_frequency='daily', lookback_bars=lookback_bars, max_weight=Decimal('0.45'),
            cash_reserve_weight=Decimal('0.02'), sleeve_name=definition.sleeve_name, target_overlays=overlays,
        )[day]
        return constrain_to_base(targets, candidate, constituent_overlay.active_cap)
    return targets
