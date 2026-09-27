"""Versioned rolling candidate contract and application-owned model artifacts."""
from __future__ import annotations

from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.signals.decision_tree import DecisionTreeSignalOverlay


def rolling_xgboost_spec():
    return dict(version='rolling-xgboost-1y-v1', family='xgboost', window_years=1,
        seed=20260927, refit='monthly', embargo='label_end_strictly_before_fit_close',
        target='next_month_adjusted_usd_return_minus_cross_section_mean',
        parameters=dict(n_estimators=100, max_depth=3, learning_rate=.03, min_child_weight=25,
            subsample=.8, colsample_bytree=.75, reg_lambda=10, reg_alpha=0,
            objective='reg:squarederror', tree_method='hist', base_score=0, random_state=20260927, n_jobs=1))


def definition_training_spec(definition):
    found = [json.loads(o.parameters['spec']) for o in definition.overlays if o.kind == 'rolling_model']
    if not found:
        return None
    if len(found) != 1 or found[0] != rolling_xgboost_spec():
        raise ValueError('Unsupported rolling training recipe; register a new version explicitly')
    return found[0]


class RollingModelOverlay(DecisionTreeSignalOverlay):
    """Use unchanged tree rank/sizing only after a causal model is bound."""
    def __init__(self, *, tilt, max_active_weight):
        from systematic_trading.signals.library import max_signal_lookback_bars
        self.model = None
        self.tilt, self.max_active_weight = tilt, max_active_weight
        self.valuation_scores, self.macro_scores = {}, {}
        self.lookback_bars = max_signal_lookback_bars()
        self.threshold = 0
        self.name = 'rolling-xgboost-1y-rank-tilt'

    def apply(self, targets, context):
        if self.model is None:
            raise ValueError('Rolling strategy requires a validated monthly fitted model')
        return super().apply(targets, context)


def monthly_training_records(bars, symbols):
    """Same ordered asset-month observations as the fixed rolling study."""
    from systematic_trading.domain.market import PriceBar
    from systematic_trading.signals.base import SignalContext
    from systematic_trading.signals.library import compute_signal_features
    if set(symbols) != set(bars):
        raise ValueError('Training universe/order differs from the versioned strategy')
    typed = {s: [PriceBar.model_validate(r) for r in bars[s]] for s in symbols}
    days = [r['trade_date'] for r in bars['SPY']]
    if any([r['trade_date'] for r in bars[s]] != days for s in symbols):
        raise ValueError('Training histories have different calendars')
    starts = [d for i, d in enumerate(days) if i >= 379 and d[:7] != days[i-1][:7]]
    prices = {s: {r['trade_date']: float(r['close']) for r in bars[s]} for s in symbols}
    records = []
    for start, end in zip(starts, starts[1:]):
        known, label_end = days[days.index(start)-1], days[days.index(end)-1]
        context = SignalContext(as_of=date.fromisoformat(start), instruments={}, trade_dates=[],
            bars_by_symbol={s: [r for r in typed[s] if str(r.trade_date) <= known] for s in symbols})
        returns = {s: prices[s][label_end]/prices[s][known]-1 for s in symbols}
        mean = sum(returns.values())/len(returns)
        records += [dict(symbol=s, signal_session=start, known_through=known, label_end=label_end,
            inputs=compute_signal_features(symbol=s, context=context), relative_return=returns[s]-mean,
            role='training_only') for s in symbols]
    return records


def monthly_fit_dates(bars, start):
    from systematic_trading.live.trading_calendar import is_us_trading_day
    days = [r['trade_date'] for r in bars['SPY']]
    dates = [days[i-1] for i, d in enumerate(days) if i and d >= start and d[:7] != days[i-1][:7]]
    following = date.fromisoformat(days[-1])+timedelta(days=1)
    while not is_us_trading_day(following):
        following += timedelta(days=1)
    if str(following) >= start and str(following)[:7] != days[-1][:7]:
        dates.append(days[-1])
    if not dates:
        raise ValueError('No scheduled monthly fit before the latest signal')
    return dates


def select_rolling_model(schedule, histories, day):
    """Require the previous-month close from the already verified input calendar.

    Bundle/input validation owns calendar coverage. Inference must remain free
    of live-package imports and their database/broker dependencies inside LEAN.
    """
    from systematic_trading.research.chronological_tree import select_base_tree
    prior = [r.trade_date for r in histories['SPY'] if r.trade_date < day.replace(day=1)]
    if not prior:
        raise ValueError('Missing previous-month calendar history')
    cutoff = max(prior)
    known = str(histories['SPY'][-1].trade_date)
    item = schedule.get(str(cutoff))
    if str(cutoff) > known or item is None:
        raise ValueError('Missing monthly rolling model fitted at '+str(cutoff))
    recipe = rolling_xgboost_spec()
    if (item.get('window_years') != 1 or item['model'].get('kind') != 'xgboost'
            or item['details'].get('settings') != recipe['parameters']):
        raise ValueError('Rolling fitted model differs from the registered recipe')
    return select_base_tree({str(cutoff): item}, known)


def read_model_artifacts(root):
    pointer = json.loads((root/'complete.json').read_text(encoding='utf8'))
    attempt = (root/pointer['attempt']).resolve()
    if not attempt.is_relative_to(root.resolve()) or sha256(attempt/'receipt.json') != pointer['receipt_sha256']:
        raise ValueError('Changed rolling training receipt')
    receipt = json.loads((attempt/'receipt.json').read_text(encoding='utf8'))
    if receipt['status'] != 'succeeded' or sha256(root/'request.json') != receipt['request_sha256']:
        raise ValueError('Rolling training inputs/receipt changed')
    for name, expected in receipt['files'].items():
        path = (attempt/name).resolve()
        if not path.is_relative_to(attempt) or sha256(path) != expected:
            raise ValueError('Rolling fitted artifact changed: '+name)
    return json.loads((attempt/'schedule.json').read_text(encoding='utf8')), dict(receipt, artifact_path=str(attempt))


def prepare_model_schedule(settings, inputs, definition, start, code_hashes):
    recipe = definition_training_spec(definition)
    if recipe is None:
        return None, None
    from systematic_trading.research import instruments_for_definition
    request = dict(recipe=recipe, start=start, symbols=list(instruments_for_definition(definition)),
        bars=inputs['latest_bars'], batch=inputs['provenance']['batch'], code_hashes=code_hashes)
    revision = digest(encode(request))
    root = settings.data_dir/'tracked_models'/revision
    if not root.exists():
        root.mkdir(parents=True)
        write_json(root/'request.json', request)
    elif json.loads((root/'request.json').read_text(encoding='utf8')) != request:
        raise ValueError('Rolling training request changed')
    if (root/'complete.json').exists():
        return read_model_artifacts(root)
    attempt = root/'attempts'/uuid4().hex
    attempt.mkdir(parents=True)
    runtime_keys = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'COMSPEC', 'TEMP', 'TMP', 'LANG', 'LC_ALL'}
    environment = {k: v for k, v in os.environ.items() if k.upper() in runtime_keys}
    environment.update(PYTHONPATH=str(Path(__file__).resolve().parents[2]), PYTHONDONTWRITEBYTECODE='1',
        PYTHONUTF8='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    with (attempt/'training.log').open('w', encoding='utf8') as log:
        subprocess.run([sys.executable, '-B', '-m', 'systematic_trading.research.rolling_training',
            str(root.resolve()), str(attempt.resolve())], env=environment, cwd=attempt, stdout=log,
            stderr=subprocess.STDOUT, timeout=900, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    write_json(root/'complete.tmp', dict(attempt=str(attempt.relative_to(root)), receipt_sha256=sha256(attempt/'receipt.json')))
    (root/'complete.tmp').replace(root/'complete.json')
    return read_model_artifacts(root)
