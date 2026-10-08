"""Frozen-capacity per-ETF economic response models; no execution authority."""
from decimal import Decimal as D, ROUND_DOWN
import math

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.economic_leading_features import LEADING
from systematic_trading.research.construction_controls import gross

CONTEXT_FEATURES = ['PAYEMS', 'IPMAN', 'CPIAUCSL_3m_annualized', 'CPIAUCSL_12m',
                    'CPILFESL_3m_annualized', 'CPILFESL_12m']
GROUPS = dict(leading=LEADING, matched=LEADING, combined=LEADING+CONTEXT_FEATURES)
SPEC = dict(version='economic-asset-response-v2', features=GROUPS,
    target='Next scheduled rebalance open / current rebalance open - 1; published dividend/split-adjusted USD prices',
    training='Expanding monthly rows from 2016; minimum 36 complete labels; label endpoint no later than prior completed close; original vintage for each row',
    tree=dict(max_depth=2, min_samples_leaf=12, criterion='squared_error', random_state=20261007),
    linear='Ridge alpha=1; training-only StandardScaler; identical rows and labels as the paired tree',
    prediction='Per-ETF forecast increment relative to its own mean return over the same training sample',
    tilt='1.10 if increment >0.25% and absolute forecast positive; 0.90 if increment < -0.25%; otherwise 1.00',
    sizing='Preserve exact capped-parent gross and positive membership; redistribute normalized tilt only within 45% per-ETF capacity; parent cash remains cash',
    missing='Leading uses leading-ready rows; matched and combined use identical leading-plus-context-ready rows and decisions; unavailable or <36 labels abstains to parent',
    sensitivities='Descriptive conditional prediction at each training-feature 75th versus 25th percentile, all other query features fixed; not identified causal shocks',
    search='No parameter, threshold, feature, window or universe search')


def ready(state, group):
    if group not in GROUPS:
        raise ValueError('Unregistered economic feature group')
    return state['leading_ready'] and (group == 'leading' or state['context_ready'])


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


def tilt(targets, fitted, kind):
    total = gross(targets); cap = D('.45')
    if any(t.target_weight > cap for t in targets):
        raise ValueError('Economic experiment requires the capped parent control')
    if kind not in {'tree','linear'} or type(fitted.get('ready')) is not bool:
        raise ValueError('Invalid economic model result')
    if not fitted['ready'] or not total:
        return list(targets)
    scores = {}
    for t in targets:
        if not t.target_weight:
            continue
        model = fitted['models'][t.symbol]
        increment, absolute = D(str(model[kind+'_increment'])), D(str(model[kind+'_forecast']))
        if not increment.is_finite() or not absolute.is_finite():
            raise ValueError('Invalid economic forecast')
        multiplier = D('1.10') if increment > D('.0025') and absolute > 0 else D('.90') if increment < D('-.0025') else D(1)
        scores[t.symbol] = t.target_weight*multiplier
    assigned, remaining, available = {}, total, dict(scores)
    while available:
        denom = sum(available.values(), D(0))
        proposed = {s:remaining*w/denom for s,w in available.items()}
        limited = [s for s,w in proposed.items() if w > cap]
        if not limited:
            assigned.update(proposed)
            break
        for s in limited:
            assigned[s] = cap; remaining -= cap; del available[s]
    # Canonicalize insignificant arithmetic noise before reconciling the budget.
    # Twenty-four places are far below the replay's 1e-8 target tolerance. All
    # other weights then sum exactly, independent of capped-dictionary order.
    assigned = {s:w.quantize(D('1e-24'),rounding=ROUND_DOWN) for s,w in assigned.items()}
    if any(w <= 0 for w in assigned.values()):
        raise ValueError('Target too small for canonical allocation precision')
    residual = total-sum(assigned.values(),D(0))
    if residual:
        eligible = [s for s,w in assigned.items() if D(0) <= w+residual <= cap]
        if not eligible:
            raise ValueError('No capacity to reconcile target rounding')
        assigned[sorted(eligible)[0]] += residual
    result = [t.model_copy(update=dict(target_weight=assigned.get(t.symbol,D(0)),
        rationale=t.rationale+f' {fitted["group"]} {kind} economic response; same gross and membership; 45% final cap.')) for t in targets]
    if gross(result) != total or any(t.target_weight > cap for t in result):
        raise ValueError('Economic tilt violated its allocation contract')
    return result
