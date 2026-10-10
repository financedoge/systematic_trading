"""App-owned FR25 selection, original-vintage features and expanding model fits."""
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timedelta
import os

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.recorders.economics import EconomicInputs, load_catalog, NY
from systematic_trading.research.economic_financial import SERIES, FEATURES, panel, fit_predict
from systematic_trading.research.momentum_signals import decision_sessions
from systematic_trading.research.selection_blend import SelectionBlend

KEY = 'research_fr25_14_v1'
PARAMETERS = dict(version='fr25-financial-selection-v1', group='financial', blend='R25',
    prospectiveStart='2026-10-10', ridgeAlpha='1', minimumLabels=36,
    forecast='total_return', momentumWeight='0.75', financialWeight='0.25', xgbWeight='0')
_FIT = None


def economic_inputs(analytics, bars, start):
    from systematic_trading.live.trading_calendar import next_us_trading_day
    days = [r['trade_date'] for r in bars['SPY']]
    decisions = decision_sessions(days, start, 'monthly')
    known = {d: days[days.index(d)-1] for d in decisions}
    known[str(next_us_trading_day(date.fromisoformat(days[-1])))] = days[-1]
    _, pin = load_catalog(analytics)
    reader = EconomicInputs(**pin)
    vintages = {str(date.fromisoformat(k)-timedelta(days=1)) for k in known.values()}
    entries = [r for r in reader.catalog['snapshots'] if r['series'] in SERIES and r['vintage'] in vintages]
    for entry in entries:
        reader.snapshot(entry['series'], entry['vintage'])
    identity = dict(entries=entries, known=known, parameters=PARAMETERS)
    return dict(pin=pin, entries=entries, known=known, monthly_decisions=decisions,
        provenance=dict(subset_sha256=digest(encode(identity)), series=SERIES, features=FEATURES,
            availability='archive_daily before prospectiveStart; actual first_seen thereafter', parameters=PARAMETERS))


def feature_states(inputs):
    from systematic_trading.live.trading_calendar import us_equity_market_close
    reader = EconomicInputs(**inputs['pin'])
    result = {}
    available = {(r['series'], r['vintage']) for r in inputs['entries']}
    for day, known in inputs['known'].items():
        vintage = str(date.fromisoformat(known)-timedelta(days=1))
        cutoff = datetime.combine(date.fromisoformat(known), us_equity_market_close(date.fromisoformat(known)), NY)
        missing = [s for s in SERIES if (s, vintage) not in available]
        if missing:
            result[day] = dict(vintage=vintage, known_at=cutoff.isoformat(), features={}, sources={},
                leading_ready=False, context_ready=False, financial_ready=False,
                unavailable=[dict(series=s, reason='unpublished_exact_vintage') for s in missing])
            continue
        state = panel(reader, vintage, cutoff, include_context=False)
        if day >= PARAMETERS['prospectiveStart']:
            state['availability'] = 'first_seen'
            for s in SERIES:
                if datetime.fromisoformat(reader.snapshot(s, vintage)['first_seen_at']) >= cutoff:
                    state['sources'].pop(s, None)
                    for key in list(state['features']):
                        if key == s or key.startswith(s+'_'):
                            del state['features'][key]
                    state['unavailable'].append(dict(series=s, reason='not_captured_before_decision'))
            state['financial_ready'] = all(s in state['sources'] for s in SERIES)
        result[day] = state
    return result


def fit_init(states, opens, known):
    global _FIT
    _FIT = (states, opens, known)


def fit_day(day):
    states, opens, known = _FIT
    fitted = fit_predict(day, known[day], states, opens, 'financial')
    fitted['unavailable'] = states[day]['unavailable']
    fitted['availability'] = states[day].get('availability', 'archive_daily')
    return day, fitted


def prepare_schedule(inputs, bars):
    states = feature_states(inputs)
    opens = {s: {r['trade_date']: r['open'] for r in rows} for s, rows in bars.items()}
    for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[variable] = '1'
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 1, initializer=fit_init,
            initargs=(states, opens, inputs['known'])) as pool:
        models = dict(pool.map(fit_day, sorted(states)))
    return dict(parameters=PARAMETERS, pin=inputs['pin'], provenance=inputs['provenance'],
        sources=inputs['entries'], features=states, models=models, workers=os.cpu_count() or 1)


def prediction(schedule, histories, day):
    if not schedule or schedule.get('parameters') != PARAMETERS:
        raise ValueError('Published FR25 financial schedule required')
    day = str(day)
    if day not in schedule['models']:
        raise ValueError('Exact FR25 decision missing; await application catch-up')
    model = schedule['models'][day]
    known = str(histories['SPY'][-1].trade_date)
    if model['known_through'] != known or known >= day or (model['last_label_end'] and model['last_label_end'] > known):
        raise ValueError('FR25 model and decision cutoffs differ')
    if model['ready'] and set(model['models']) != set(histories):
        raise ValueError('FR25 model universe changed')
    return model


class FinancialRankSelection(SelectionBlend):
    """Frozen 75% M1 / 25% financial total-forecast ranks before eligibility/top six."""
    def __init__(self, parent):
        super().__init__(parent, dict(blend='R25', group='financial'), {}, {})
        self.schedule = None
        self.rolling_schedule = None

    def apply(self, targets, context):
        from systematic_trading.research.rolling_tracking import select_rolling_model
        from systematic_trading.signals.library import compute_signal_features
        self.ridge = prediction(self.schedule, context.bars_by_symbol, context.as_of)
        model = select_rolling_model(self.rolling_schedule, context.bars_by_symbol, context.as_of)
        self.xgb = {s: model.predict(compute_signal_features(symbol=s, context=context))
                    for s in context.bars_by_symbol}
        return super().apply(targets, context)


def enrich_report(report, definition, inputs, economic, schedule, receipt, rolling, days):
    from systematic_trading.domain.market import PriceBar
    from systematic_trading.research import instantiate_overlays, instruments_for_definition
    from systematic_trading.signals.base import SignalContext
    from systematic_trading.backtest.stored import _target_schedule
    from decimal import Decimal
    allocation = report['currentAllocation']
    day = date.fromisoformat(allocation['target_session'])
    histories = {s:[PriceBar.model_validate(r) for r in rows if r['trade_date'] < str(day)]
                 for s,rows in inputs['latest_bars'].items()}
    current = prediction(schedule, histories, day)
    selector = instantiate_overlays(definition)[0]
    selector.schedule, selector.rolling_schedule = schedule, rolling
    # Use the same actual pre-selection base targets as the executable service.
    instruments = instruments_for_definition(definition)
    base = _target_schedule(instruments=instruments,bars_by_symbol=histories,trade_dates=[day],
        rebalance_frequency='daily',lookback_bars=63,max_weight=Decimal('.45'),cash_reserve_weight=Decimal('.02'),
        sleeve_name=definition.sleeve_name,target_overlays=[])[day]
    selector.apply(base,SignalContext(as_of=day,instruments=instruments,bars_by_symbol=histories,trade_dates=[day]))
    selected = set(selector.observation['selected'])
    eligible = set(selector.observation['eligible'])
    ranks = [dict(symbol=s,**r,eligible=s in eligible,selected=s in selected)
             for s,r in sorted(selector.rank_table.items(),key=lambda row:(-Decimal(row[1]['combined']),row[0]))]
    report['economicModel'] = dict(title='Financial Ridge · Asset Selection',parameters=PARAMETERS,
        receipt=receipt,pin=schedule['pin'],latest=current,provenance=schedule['provenance'],
        historical_ready=sum(r['ready'] for d,r in schedule['models'].items() if d in economic['decisions']),
        historical_decisions=len(economic['decisions']),selectionRanks=ranks,
        status='Financial ranks available for selection' if current['ready'] else 'Financial model abstains; original M1 selection applies',
        abstention='Original M1 ranking, eligibility and defensive fallback apply; downstream sizing and the final cap remain.',
        explanation='FR25: 75% M1 rank + 25% financial total-return forecast rank. M1 itself is 75% momentum / 25% volume. '
            'Five financial series produce eight features; per-ETF standardized expanding ridge, alpha 1, minimum 36 completed monthly labels. '
            'Midranks across all 14 candidates, positive 126-session gate, top six/minimum four, alphabetic ties. '
            'XGBoost has zero selection weight and retains its existing downstream sizing role. Missing financial data revert the whole selector to M1.')
    report['modelRegime']='FR25: M1/financial rank selection; monthly XGBoost sizing, relative/adaptive trend, raw activity, USD ridge and final 45% cap'
    report['monitoring'].update(prospectiveStart=PARAMETERS['prospectiveStart'],
        prospectiveObservations=sum(d>=PARAMETERS['prospectiveStart'] for d in days))
    report['warnings']=[w for w in report['warnings'] if not w.startswith('45% is a base cap') and not w.startswith('M1/14 was selected')]
    report['warnings'] += ['FR25 was selected retrospectively. Practical effect-size checks passed, but no multiple-comparison-adjusted return superiority was established. Recent substitutions concentrate gains. Monitoring grants no funding or execution authority.',
        'Final ETF targets capped at 45%; excess remains cash. Held weights may drift between monthly rebalances.',
        'Historical financial inputs assume prior-day ALFRED archive availability; from October 10, 2026 actual app capture must precede the decision cutoff. Missing or late inputs abstain; retrospective histories are not prospective evidence.']
    if not current['ready']:
        report['warnings'].append(report['economicModel']['status']+': '+current['reason'])
