"""Explain the exact fitted model and current executable allocation pipeline."""
from datetime import date
from dataclasses import replace

from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research import instruments_for_definition
from systematic_trading.research.flow_concentration import FlowConcentrationSpec, concentration_features
from systematic_trading.research.rolling_tracking import select_rolling_model, rolling_xgboost_spec
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.library import compute_signal_features, signal_library_rows


def tree_diagram(tree, features, number):
    from systematic_trading.research.strategy_diagram import label
    nodes, edges = [], []
    def visit(node, depth, left, right):
        x, y = (left+right)/2, 24+depth*100
        leaf = tree['left'][node] < 0
        lines = (['Leaf contribution', f"{tree['value'][node]:.6%}"] if leaf else
            [features[tree['feature'][node]], f"< {tree['threshold'][node]:.8g}"])
        width = max(150, max(len(s) for s in lines)*6.7+14)
        nodes.append(f'<rect x="{x-width/2}" y="{y}" width="{width}" height="65" rx="6" fill="#edf7f3" stroke="#9bb6c9"/>')
        nodes.append(label(lines, x-width/2+7, y+24, 11))
        if not leaf:
            for child, lo, hi, text in ((tree['left'][node], left, x, '<'), (tree['right'][node], x, right, '≥')):
                cx, cy = visit(child, depth+1, lo, hi)
                edges.append(f'<path d="M{x} {y+65} L{cx} {cy}" stroke="#65859b" fill="none"/>')
                edges.append(label([text], (x+cx)/2, (y+65+cy)/2, 12))
        return x, y
    visit(0, 0, 0, 1600)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 410" role="img" '
        f'aria-label="XGBoost tree {number}">'+''.join(edges+nodes)+'</svg>')


def rolling_model_report(definition, inputs, schedule, receipt, allocation, usd_models=None, economic_models=None):
    day = date.fromisoformat(allocation['target_session'])
    histories = {s: [PriceBar.model_validate(r) for r in rows if r['trade_date'] < str(day)]
        for s, rows in inputs['latest_bars'].items()}
    model = select_rolling_model(schedule, histories, day)
    fit = max(d for d in schedule if d <= allocation['target_known_through'])
    record = schedule[fit]
    context = SignalContext(as_of=day, instruments=instruments_for_definition(definition),
        bars_by_symbol=histories, trade_dates=[day])
    activity_spec = next((FlowConcentrationSpec.model_validate_json(o.parameters['spec'])
        for o in definition.overlays if o.kind == 'etf_activity'), None)
    activity = concentration_features(histories, activity_spec) if activity_spec else {}
    features = {s: compute_signal_features(symbol=s, context=context) for s in histories}
    forecasts = {s: model.predict(values) for s, values in features.items()}
    # Call the same target service for every prefix; each column is an actual
    # stage in the executable definition, not a hand-written approximation.
    stages = []
    for count in range(len(definition.overlays)+1):
        prefix = replace(definition, overlays=definition.overlays[:count])
        has_model = any(o.kind == 'rolling_model' for o in prefix.overlays)
        targets = targets_for_day(inputs['latest_bars'], day, definition=prefix,
            base_tree_models=schedule if has_model else None, usd_models=usd_models, economic_models=economic_models)
        stages.append(dict(name='Risk parity' if not count else definition.overlays[count-1].kind,
            weights={t.symbol: float(t.target_weight) for t in targets}))
    final_weights = {r['symbol']: r['target_weight'] for r in allocation['holdings']}
    if any(abs(w-final_weights[s]) > 1e-12 for s, w in stages[-1]['weights'].items()):
        raise ValueError('Explanatory allocation trace differs from executable targets')
    return dict(recipe=rolling_xgboost_spec(), fitAsOf=fit,
        training={k: v for k, v in record.items() if k != 'model'},
        modelSha256=digest(encode(record['model'])), receipt=receipt,
        features=[r for r in signal_library_rows() if r['featureId'] in model.feature_names],
        forecasts=[dict(symbol=s, forecast=forecasts[s], activity=activity.get(s), inputs=features[s])
            for s in sorted(forecasts, key=lambda s: (-forecasts[s], s))],
        allocationStages=stages,
        trees=[tree_diagram(t, model.feature_names, i+1) for i, t in enumerate(record['model']['trees'])],
        model=record['model'], batch=inputs['provenance']['batch'],
        explanation='Each fit uses asset-month observations whose feature dates fall in the preceding calendar year and whose next-month labels end strictly before the fit close. At least 100 complete observations are required. Feature lookbacks may extend 378 sessions before the observation. The last two external-score inputs are fixed neutral zeros. The forecast is the sum of 100 shrunken tree leaf contributions (base score zero); its cross-sectional rank drives a 16% tilt with a 6pp pre-normalization delta cap. Gross exposure is then restored. Lag-20 activity is applied later as a separate 15% tilt with a final 3pp bound relative to that stage input. Forecasts are scores, not calibrated expected profits.')
