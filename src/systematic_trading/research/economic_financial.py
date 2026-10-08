"""Finite financial-condition challengers; independent of the monitored recipe."""
from datetime import date, datetime
from decimal import Decimal as D
import math

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.recorders.economics import NY
from systematic_trading.research.economic_leading_features import panel as original_panel
from systematic_trading.research.economic_response import GROUPS as ORIGINAL_GROUPS, SPEC as ORIGINAL_SPEC

SERIES = ['T10Y3M','T10Y2Y','NFCICREDIT','DRTSCILM','DRTSCIS']
FEATURES = ['T10Y3M','T10Y2Y','NFCICREDIT','NFCICREDIT_change',
            'DRTSCILM','DRTSCILM_change','DRTSCIS','DRTSCIS_change']
GROUPS = dict(financial=FEATURES, matched=ORIGINAL_GROUPS['combined'],
              augmented=ORIGINAL_GROUPS['combined']+FEATURES)
SPEC = dict(ORIGINAL_SPEC, version='economic-financial-response-v1',features=GROUPS,
    missing='Financial requires all five new series. Matched and augmented require the original eleven plus all five, with identical training rows and current availability. Missing values abstain to P3.',
    search='Two predefined feature combinations, paired ridge and depth-two trees; no parameter or ETF selection search')
FEATURE_SPEC = dict(version='economic-financial-features-v1', series=SERIES, features=FEATURES,
    transformations='Treasury slopes: latest recorded endpoint level in percentage points. NFCI: latest level and four-week difference. Both SLOOS series: latest net tightening percentage and one-quarter difference. No rounding, fill or smoothing. Explicitly missing endpoints/windows abstain.',
    interpretation='Treasury slope is not a recession probability. NFCI credit is a revised standardized composite, not a bond spread. SLOOS is lending supply; quarter start is not publication time.',
    availability='Exact published prior-calendar-day archive before prior trading close; explicit retrospective archive_daily assumption. First capture remains October 2026.',
    combinations='Financial only (8 features); original leading/context plus financial (21 features). Matched original-context control isolates added information from sample and decision availability.')


def panel(reader, vintage, known_at):
    state = original_panel(reader,vintage,known_at)
    for s in SERIES:
        snap = reader.snapshot(s,vintage)
        if known_at <= datetime.fromisoformat(snap['archive_available_at']):
            raise ValueError('Economic vintage unavailable at decision time')
        count = 1 if s.startswith('T10Y') else 5 if s=='NFCICREDIT' else 2
        rows = snap['observations'][-count:]
        age = (known_at.astimezone(NY).date()-date.fromisoformat(snap['last'])).days
        if not snap['usable'] or age > snap['series']['max_age_days']:
            reason = 'stale_or_missing_endpoint'
        elif len(rows)!=count or any(r['value'] is None for r in rows):
            reason = 'incomplete_window'
        else:
            values = [D(r['value']) for r in rows]
            if not all(v.is_finite() and D(str(snap['series']['min']))<=v<=D(str(snap['series']['max'])) for v in values):
                raise ValueError('Invalid published financial value')
            features = {s:str(values[-1])}
            if count>1: features[s+'_change'] = str(values[-1]-values[0])
            state['features'].update(features)
            state['sources'][s] = dict(vintage=vintage,features=features,endpoint=rows[-1]['date'],
                required_window_start=rows[0]['date'],required_observations=count)
            continue
        state['unavailable'].append(dict(series=s,reason=reason,endpoint=snap['last'],age_days=age))
    state['financial_ready'] = all(s in state['sources'] for s in SERIES)
    return state


def ready(state, group):
    if group not in GROUPS:
        raise ValueError('Unregistered financial feature group')
    return state['financial_ready'] and (group=='financial' or (state['leading_ready'] and state['context_ready']))


def vector(state, group):
    values = [float(state['features'][key]) for key in GROUPS[group]]
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Nonfinite economic input')
    return values


def training_rows(day, known, states, opens, group):
    rows = []
    days = sorted(states)
    for start, end in zip(days, days[1:]):
        # Never read unknown prices or feature values, even just to impute them.
        if start >= day or end > known:
            continue
        state = states[start]
        if not ready(state, group):
            continue
        if state['known_at'][:10] >= start or state['vintage'] >= start:
            raise ValueError('Historical economic availability violation')
        labels = {}
        for symbol, values in opens.items():
            before, after = D(values[start]), D(values[end])
            if not before.is_finite() or not after.is_finite() or min(before, after) <= 0:
                raise ValueError('Invalid audited label prices')
            labels[symbol] = float(after/before-1)
        rows.append(dict(start=start, end=end, vintage=state['vintage'], x=vector(state, group), y=labels))
    return rows


def fit_predict(day, known, states, opens, group):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeRegressor
    from systematic_trading.research.economic_models import predict_tree
    rows = training_rows(day, known, states, opens, group)
    state = states[day]
    if state['known_at'][:10] > known or state['known_at'][:10] >= day or state['vintage'] >= day:
        raise ValueError('Current economic availability violation')
    result = dict(version=SPEC['version'], group=group, features=GROUPS[group], decision=day,
        known_through=known, training_rows=len(rows), training_labels=rows,
        training_sha256=digest(encode(rows)), sample_sha256=digest(encode([{k:r[k] for k in ('start','end','vintage','y')} for r in rows])),
        last_label_end=rows[-1]['end'] if rows else None, ready=False, models={},
        reason='current economics unavailable' if not ready(state,group) else 'insufficient completed labels')
    if not ready(state,group) or len(rows) < 36:
        return result
    x = np.array([r['x'] for r in rows]); query = np.array([vector(state,group)])
    scaler = StandardScaler().fit(x)
    quartiles = np.quantile(x, [.25,.75], axis=0)
    result['feature_quartiles'] = quartiles.tolist()
    for symbol in sorted(opens):
        y = np.array([r['y'][symbol] for r in rows]); mean = float(y.mean()); centered = y-mean
        tree = DecisionTreeRegressor(**SPEC['tree']).fit(x,centered)
        linear = Ridge(alpha=1).fit(scaler.transform(x),centered)
        tree_increment, linear_increment = float(tree.predict(query)[0]), float(linear.predict(scaler.transform(query))[0])
        frozen = dict(left=tree.tree_.children_left.tolist(),right=tree.tree_.children_right.tolist(),
            feature=tree.tree_.feature.tolist(),threshold=tree.tree_.threshold.tolist(),
            value=tree.tree_.value[:,0,0].tolist(),samples=tree.tree_.n_node_samples.tolist())
        if abs(predict_tree(frozen,query[0].astype(np.float32))-tree_increment)>1e-12:
            raise ValueError('Frozen tree differs from fitted prediction')
        sensitivity = {}
        for i,key in enumerate(GROUPS[group]):
            probe = np.repeat(query,2,axis=0); probe[:,i] = quartiles[:,i]
            t,l = tree.predict(probe),linear.predict(scaler.transform(probe))
            sensitivity[key] = dict(tree=float(t[1]-t[0]),linear=float(l[1]-l[0]))
        result['models'][symbol] = dict(mean_return=mean,tree_increment=tree_increment,linear_increment=linear_increment,
            tree_forecast=mean+tree_increment,linear_forecast=mean+linear_increment,tree=frozen,
            linear=dict(coefficients=linear.coef_.tolist(),intercept=float(linear.intercept_),
                feature_means=scaler.mean_.tolist(),feature_scales=scaler.scale_.tolist()),sensitivities=sensitivity)
    result.update(ready=True, reason='Original vintages and completed labels only', query=vector(state,group))
    return result
