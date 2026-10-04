"""Application-owned U1 models and the shared, causal final allocation overlay."""
from datetime import date, timedelta
import math
from statistics import stdev

from systematic_trading.domain.market import PriceBar
from systematic_trading.research.momentum_signals import horizon_rank
from systematic_trading.research.usd_momentum_model import ridge_predict, apply_usd_predictions

VERSION = "usd-ridge-u1-v1"
FIRST_FIT = "2024-03-28"


def price_features(histories, usd):
    # Identical to the registered S=A6, L=A7 and sample volatility definitions.
    a, b = horizon_rank(histories, 0, 5), horizon_rank(histories, 0, 10)
    c, d = horizon_rank(histories, 21, 42), horizon_rank(histories, 21, 63)
    result = {}
    for symbol, rows in histories.items():
        prices = [float(r.close) for r in rows[-64:]]
        if len(prices) != 64:
            raise ValueError("Incomplete USD price feature history")
        vol = stdev([y/x-1 for x, y in zip(prices, prices[1:])])*math.sqrt(252)
        result[symbol] = dict(S=float((a[symbol]+b[symbol])/2),
            L=float((c[symbol]+d[symbol])/2), vol63=vol, **usd)
    return result


def select_snapshot(snapshots, known):
    candidates = [r for r in snapshots if r['known_through'] == known and r['vintage_date'] < known]
    if len(candidates) != 1:
        raise ValueError("Missing or ambiguous published USD snapshot for " + known)
    row = candidates[0]
    if (date.fromisoformat(known)-date.fromisoformat(row['observation_date'])).days > 14:
        raise ValueError("Stale USD index observation")
    return row


def prepare_usd_schedule(bars, snapshots):
    """Refit at monthly closes; freeze coefficients and all audited USD dependencies."""
    from systematic_trading.live.trading_calendar import next_us_trading_day
    histories = {s: [PriceBar.model_validate(r) for r in rows] for s, rows in bars.items()}
    days = [str(r.trade_date) for r in histories['SPY']]
    if any([str(r.trade_date) for r in rows] != days for rows in histories.values()):
        raise ValueError("USD feature calendars differ")
    closes = [d for d in days if next_us_trading_day(date.fromisoformat(d)).month != date.fromisoformat(d).month]
    features, training = {}, []
    for known in closes:
        if known < '2019-02-28':
            continue
        snap = select_snapshot(snapshots, known)
        i = days.index(known)+1
        features[known] = price_features({s: rows[:i] for s, rows in histories.items()}, snap['features'])
    for known, end in zip(closes, closes[1:]):
        if known not in features:
            continue
        a, b = days.index(known), days.index(end)
        returns = {s: float(rows[b].close/rows[a].close)-1 for s, rows in histories.items()}
        mean = sum(returns.values())/len(returns)
        training.extend(dict(symbol=s, known_through=known, label_end=end,
            label=returns[s]-mean, features=features[known][s]) for s in histories)
    models = {}
    for known, current in features.items():
        fit = ridge_predict(training, current, known, True)
        if fit is not None:
            models[known] = fit
        elif known >= FIRST_FIT:
            raise ValueError("USD model has fewer than 60 completed months at " + known)
    # Latest indicative targets require their own prior-day snapshot, including mid-month.
    select_snapshot(snapshots, days[-1])
    return dict(version=VERSION, models=models, snapshots=snapshots,
        training_records=training, features=features,
        policy="60 completed months; label_end strictly before fit close; per-ETF standardized ridge alpha=1; monthly refits")


def usd_prediction(schedule, histories, as_of):
    known = str(histories['SPY'][-1].trade_date)
    if known < FIRST_FIT:
        return None
    if not schedule or schedule.get('version') != VERSION:
        raise ValueError("Published USD model schedule required")
    # A monthly decision uses the prior close. Between decisions use that month's fitted model.
    prior_month = str(as_of)[:7]
    cutoffs = [str(r.trade_date) for r in histories['SPY'] if str(r.trade_date)[:7] < prior_month]
    if not cutoffs or max(cutoffs) not in schedule['models']:
        raise ValueError("No causal monthly USD model")
    fit_close = max(cutoffs)
    if (date.fromisoformat(known)-date.fromisoformat(fit_close)) > timedelta(days=35):
        raise ValueError("Stale monthly USD model")
    fit = schedule['models'][fit_close]
    snap = select_snapshot(schedule['snapshots'], known)
    current = price_features(histories, snap['features'])
    predictions = {}
    if set(current) != set(fit['models']):
        raise ValueError("USD model universe differs")
    for symbol, model in fit['models'].items():
        if model['max_label_end'] >= fit_close or model['training_months'] < 60:
            raise ValueError("USD model violates training cutoff")
        value = model['intercept'] + sum((current[symbol][k]-mu)/scale*beta
            for k, mu, scale, beta in zip(model['features'], model['means'], model['scales'], model['coefficients'], strict=True))
        if not math.isfinite(value):
            raise ValueError("Invalid USD prediction")
        predictions[symbol] = value
    return dict(predictions=predictions, fit_close=fit_close, snapshot=snap, features=current, model=fit)


class UsdRidgeOverlay:
    name = "USD broad-index ridge allocation"

    def __init__(self, schedule=None):
        self.schedule = schedule

    def apply(self, targets, context):
        result = usd_prediction(self.schedule, context.bars_by_symbol, context.as_of)
        if result is None:
            return list(targets)
        return apply_usd_predictions(list(targets), result['predictions'])


def published_live_schedule(settings, definition, price_batch):
    """Execution consumes the same committed, pinned model as strategy monitoring."""
    import json
    from pathlib import Path
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.lean.contracts import sha256
    if not price_batch:
        raise ValueError('USD SOTA requires published audited decision inputs')
    analytics = AnalyticsStore.from_settings(settings)
    document = analytics.document('tracked-strategies/calculations', 'report/'+definition.key)
    if not document:
        raise ValueError('Current SOTA USD calculation has not been published')
    report = json.loads(document[0]['payload'])
    provenance = json.loads(document[1]['provenance'])
    if provenance['inputs']['batch'] != price_batch or report['strategyDefinition'] != definition.to_dict():
        raise ValueError('SOTA USD model and audited decision inputs differ; await application refresh')
    receipt = report['usdModel']['receipt']
    path = Path(receipt['path'])
    if sha256(path) != receipt['sha256']:
        raise ValueError('Published USD model hash mismatch')
    return json.loads(path.read_text(encoding='utf8')), dict(receipt=receipt,
        usd_batch=report['usdModel']['batch'], calculation_revision=document[1]['version'])
