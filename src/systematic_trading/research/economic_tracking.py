"""Application-owned frozen CR recipe, with exact economic publication lineage."""
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path

from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.recorders.economics import EconomicInputs, load_catalog, NY
from systematic_trading.research.economic_leading_features import LEADING, CONTEXT, panel
from systematic_trading.research.economic_response import SPEC, fit_predict, tilt
from systematic_trading.research.momentum_signals import decision_sessions

KEY = 'research_economic_context_ridge_v1'
PARAMETERS = dict(version=SPEC['version'], group='combined', kind='linear', prospectiveStart='2026-10-08')
_FIT = None


def economic_inputs(analytics, bars, start):
    """Only this recipe's inputs invalidate its calculation, not unrelated feeds."""
    from systematic_trading.live.trading_calendar import next_us_trading_day
    days = [r['trade_date'] for r in bars['SPY']]
    decisions = decision_sessions(days, start, 'monthly')
    known = {d: days[days.index(d)-1] for d in decisions}
    known[str(next_us_trading_day(date.fromisoformat(days[-1])))] = days[-1]
    _, pin = load_catalog(analytics)
    reader = EconomicInputs(**pin)
    vintages = {str(date.fromisoformat(k)-timedelta(days=1)) for k in known.values()}
    entries = [r for r in reader.catalog['snapshots'] if r['series'] in LEADING+CONTEXT and r['vintage'] in vintages]
    # Verify all admitted inputs before inspecting optional readiness.
    for entry in entries:
        reader.snapshot(entry['series'], entry['vintage'])
    identity = dict(entries=entries, known=known, parameters=PARAMETERS)
    return dict(pin=pin, entries=entries, known=known, monthly_decisions=decisions,
        provenance=dict(subset_sha256=digest(encode(identity)), series=LEADING+CONTEXT,
            availability='archive_daily before prospectiveStart; actual first_seen thereafter', parameters=PARAMETERS))


def feature_states(inputs):
    from systematic_trading.live.trading_calendar import us_equity_market_close
    reader = EconomicInputs(**inputs['pin'])
    result = {}
    available = {(r['series'],r['vintage']) for r in inputs['entries']}
    for day, known in inputs['known'].items():
        vintage = str(date.fromisoformat(known)-timedelta(days=1))
        cutoff = datetime.combine(date.fromisoformat(known), us_equity_market_close(date.fromisoformat(known)), NY)
        missing = [s for s in LEADING+CONTEXT if (s,vintage) not in available]
        if missing:
            result[day] = dict(vintage=vintage, known_at=cutoff.isoformat(), features={}, sources={},
                leading_ready=False, context_ready=False, unavailable=[dict(series=s,reason='unpublished_exact_vintage') for s in missing])
            continue
        state = panel(reader, vintage, cutoff)
        if day >= PARAMETERS['prospectiveStart']:
            state['availability'] = 'first_seen'
            for s in LEADING+CONTEXT:
                snap = reader.snapshot(s,vintage)
                if datetime.fromisoformat(snap['first_seen_at']) >= cutoff:
                    state['sources'].pop(s,None)
                    for key in list(state['features']):
                        if key == s or key.startswith(s+'_'):
                            del state['features'][key]
                    state['unavailable'].append(dict(series=s,reason='not_captured_before_decision'))
            state['leading_ready'] = all(s in state['sources'] for s in LEADING)
            state['context_ready'] = all(s in state['sources'] for s in CONTEXT)
        result[day] = state
    return result


def fit_init(states, opens, known):
    global _FIT
    _FIT = (states,opens,known)


def fit_day(day):
    states,opens,known = _FIT
    # The optional indicative query is after the last completed close and cannot
    # close the final training label. All earlier endpoints are scheduled opens.
    fitted = fit_predict(day,known[day],states,opens,'combined')
    fitted['unavailable'] = states[day]['unavailable']
    fitted['availability'] = states[day].get('availability','archive_daily')
    return day,fitted


def prepare_schedule(inputs, bars):
    states = feature_states(inputs)
    opens = {s:{r['trade_date']:r['open'] for r in rows} for s,rows in bars.items()}
    for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[variable] = '1'
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 1, initializer=fit_init,
            initargs=(states,opens,inputs['known'])) as pool:
        models = dict(pool.map(fit_day, sorted(states)))
    return dict(parameters=PARAMETERS, pin=inputs['pin'], provenance=inputs['provenance'],
        sources=inputs['entries'], features=states, models=models, workers=os.cpu_count() or 1)


def prediction(schedule, histories, day):
    if not schedule or schedule.get('parameters') != PARAMETERS:
        raise ValueError('Published economic CR model schedule required')
    day = str(day)
    if day not in schedule['models']:
        raise ValueError('Exact economic decision missing; await application catch-up')
    model = schedule['models'][day]
    known = str(histories['SPY'][-1].trade_date)
    if model['known_through'] != known or known >= day or (model['last_label_end'] and model['last_label_end'] > known):
        raise ValueError('Economic model and decision cutoffs differ')
    if model['ready'] and set(model['models']) != set(histories):
        raise ValueError('Economic model universe changed; a new recipe is required')
    return model


class EconomicRidgeOverlay:
    name = 'Leading + payroll/inflation context linear model'

    def __init__(self, schedule=None):
        self.schedule = schedule

    def apply(self, targets, context):
        return tilt(targets, prediction(self.schedule,context.bars_by_symbol,context.as_of), 'linear')


def published_live_schedule(settings, definition, price_batch):
    """Prepared proposals use the exact same verified schedule as monitoring."""
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    analytics = AnalyticsStore.from_settings(settings)
    document = analytics.document('tracked-strategies/calculations','report/'+definition.key)
    if not document or not price_batch:
        raise ValueError('Published economic strategy calculation required')
    report = json.loads(document[0]['payload'])
    provenance = json.loads(document[1]['provenance'])
    if provenance['inputs']['batch'] != price_batch or report['strategyDefinition'] != definition.to_dict():
        raise ValueError('Economic model and governed decision inputs differ; await refresh')
    receipt = report['economicModel']['receipt']
    path = Path(receipt['path'])
    if sha256(path) != receipt['sha256']:
        raise ValueError('Published economic model hash mismatch')
    schedule = json.loads(path.read_text(encoding='utf-8'))
    # Original publication remains pinned even after a recorder catalog extension.
    EconomicInputs(**schedule['pin'])
    return schedule, dict(receipt=receipt, input_provenance=schedule['provenance'],
        economic_pin=schedule['pin'], calculation_revision=document[1]['version'])
