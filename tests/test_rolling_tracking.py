from copy import deepcopy
from datetime import date
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from systematic_trading.lean.fixtures import make_fixture_bundle
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research.flow_concentration import FlowConcentrationSpec
from systematic_trading.research.rolling_tracking import (
    rolling_xgboost_spec, monthly_fit_dates, monthly_training_records, read_model_artifacts,
)
from systematic_trading.research.rolling_report import rolling_model_report
from systematic_trading.research.strategy_catalog import (
    rolling_xgboost_1y_definition, current_sota_definition,
)
from systematic_trading.research import instruments_for_definition
from systematic_trading.research.strategy_diagram import decision_diagrams
from systematic_trading.signals.library import signal_feature_ids
from systematic_trading.lean.contracts import sha256, write_json


@pytest.fixture(scope='module')
def bars(tmp_path_factory):
    root = tmp_path_factory.mktemp('rolling-tracking')/'fixture'
    make_fixture_bundle(root)
    return json.loads((root/'bars.json').read_text())


def model_record(cutoff='2024-10-31'):
    return dict(fit_as_of=cutoff, window_years=1, window_start=cutoff.replace('2024', '2023'),
        min_feature_date='2024-01-31', max_feature_date='2024-08-30', max_label_end='2024-09-30',
        training_samples=120, training_months=10, training_sha256='fixture',
        details=dict(settings=rolling_xgboost_spec()['parameters']),
        model=dict(schema_version=1, kind='xgboost', max_depth=3, feature_names=signal_feature_ids(),
            trees=[dict(left=[1, -1, -1], right=[2, -1, -1], feature=[0, 0, 0],
                threshold=[.025, 0, 0], value=[0, -.001, .001]) for _ in range(100)]))


def test_combined_definition_reproduces_research_model_plus_lag20_and_rejects_missing_fit(bars):
    definition = rolling_xgboost_1y_definition()
    schedule = {'2024-10-31': model_record()}
    day = date(2024, 11, 1)
    actual = targets_for_day(bars, day, definition=definition, base_tree_models=schedule)
    expected = targets_for_day(bars, day, base_tree_models=schedule, flow_overlay=FlowConcentrationSpec(difference_lag=20))
    assert [t.target_weight for t in actual] == [t.target_weight for t in expected]
    assert definition.state == 'tracked' and definition.promoted_on is None
    assert current_sota_definition().overlays[1].kind == 'decision_tree'
    with pytest.raises(ValueError, match='entire history'):
        targets_for_day(bars, day, definition=definition)
    with pytest.raises(ValueError, match='Missing monthly'):
        targets_for_day(bars, date(2024, 12, 2), definition=definition, base_tree_models=schedule)
    changed = deepcopy(schedule)
    changed['2024-10-31']['model']['kind'] = 'forest'
    with pytest.raises(ValueError, match='recipe'):
        targets_for_day(bars, day, definition=definition, base_tree_models=changed)
    changed = deepcopy(schedule)
    changed['2024-10-31']['max_label_end'] = '2024-10-31'
    with pytest.raises(ValueError, match='future labels'):
        targets_for_day(bars, day, definition=definition, base_tree_models=changed)


def test_indicative_targets_keep_same_monthly_fit_and_ignore_future_bars(bars):
    definition = rolling_xgboost_1y_definition()
    schedule = {'2024-10-31': model_record()}
    day = date(2024, 11, 20)
    actual = targets_for_day(bars, day, definition=definition, base_tree_models=schedule)
    prior = {s: [r for r in rows if r['trade_date'] < str(day)] for s, rows in bars.items()}
    assert targets_for_day(prior, day, definition=definition, base_tree_models=schedule) == actual
    schedule['2024-11-29'] = dict(model_record(), fit_as_of='2024-11-29')
    assert targets_for_day(prior, day, definition=definition, base_tree_models=schedule) == actual


def test_fit_dates_only_advance_at_month_end_and_records_do_not_use_future_prices(bars):
    truncate = lambda end: {s: [r for r in rows if r['trade_date'] <= end] for s, rows in bars.items()}
    assert monthly_fit_dates(truncate('2024-11-27'), '2024-11-01') == ['2024-10-31']
    assert monthly_fit_dates(truncate('2024-11-29'), '2024-11-01') == ['2024-10-31', '2024-11-29']
    symbols = list(instruments_for_definition(current_sota_definition()))
    older = monthly_training_records(truncate('2024-11-27'), symbols)
    newer = monthly_training_records(bars, symbols)
    assert older and newer[:len(older)] == older
    assert [r['symbol'] for r in older[:12]] == symbols
    for row in older:
        assert row['known_through'] < row['signal_session'] <= row['label_end'] < '2024-11-27'


def test_cached_artifacts_verify_content_and_request(tmp_path):
    attempt = tmp_path/'attempts'/'one'
    attempt.mkdir(parents=True)
    write_json(tmp_path/'request.json', {'version':1})
    write_json(attempt/'schedule.json', {'2024-10-31':model_record()})
    write_json(attempt/'receipt.json', dict(status='succeeded', request_sha256=sha256(tmp_path/'request.json'),
        files={'schedule.json':sha256(attempt/'schedule.json')}))
    write_json(tmp_path/'complete.json', dict(attempt='attempts/one', receipt_sha256=sha256(attempt/'receipt.json')))
    assert read_model_artifacts(tmp_path)[0]['2024-10-31']['training_samples'] == 120
    (attempt/'schedule.json').write_text('{}')
    with pytest.raises(ValueError, match='artifact changed'):
        read_model_artifacts(tmp_path)


def test_report_explains_actual_targets_features_all_trees_and_activity(bars):
    definition = rolling_xgboost_1y_definition()
    schedule = {'2024-10-31': model_record()}
    targets = targets_for_day(bars, date(2024, 11, 1), definition=definition, base_tree_models=schedule)
    allocation = dict(target_session='2024-11-01', target_known_through='2024-10-31',
        holdings=[dict(symbol=t.symbol, target_weight=float(t.target_weight)) for t in targets])
    report = rolling_model_report(definition, dict(latest_bars=bars, provenance={'batch':'fixture'}),
        schedule, {}, allocation)
    assert len(report['trees']) == 100 and len(report['features']) == 26
    assert len(report['allocationStages']) == 6 and len(report['forecasts']) == 12
    assert all(r['activity']['known_through'] == '2024-10-31' for r in report['forecasts'])
    text = ' '.join(d['svg'] for d in decision_diagrams(definition))
    assert 'XGBoost' in text and 'second difference, lag 20' in text
    assert 'deployed frozen tree' not in text


def test_per_fit_cache_reuses_only_identical_training_inputs(tmp_path, monkeypatch):
    from systematic_trading.research import rolling_training
    from systematic_trading.signals.library import signal_feature_ids
    records = [dict(symbol=str(i), known_through='2024-01-31', label_end='2024-02-29',
        inputs={f: .1 for f in signal_feature_ids()}, relative_return=.01) for i in range(120)]
    path = tmp_path/'records.json'
    write_json(path, records)
    calls = []
    monkeypatch.setattr(rolling_training, 'fit_record', lambda *a, **kw: calls.append(a) or model_record())
    rolling_training.initialize(str(path), str(tmp_path), {'test':'code'}, {'test':'version'})
    assert rolling_training.fit('2024-10-31')[2] is False
    assert rolling_training.fit('2024-10-31')[2] is True
    assert len(calls) == 1
    rolling_training.RECORDS[0]['relative_return'] = .02
    assert rolling_training.fit('2024-10-31')[2] is False
    assert len(calls) == 2


def test_inference_does_not_load_live_storage_or_training_dependencies():
    script = '''
import sys
class NoOperationalImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('systematic_trading.live', 'systematic_trading.storage',
            'systematic_trading.execution', 'psycopg', 'xgboost', 'sklearn')):
            raise ImportError('Forbidden inference dependency: '+fullname)
sys.meta_path.insert(0, NoOperationalImports())
from datetime import date
from types import SimpleNamespace
from systematic_trading.research.rolling_tracking import select_rolling_model
try:
    select_rolling_model({}, {'SPY':[SimpleNamespace(trade_date=date(2024,10,31))]}, date(2024,11,1))
except ValueError as exc:
    assert 'Missing monthly' in str(exc)
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    subprocess.run([sys.executable, '-c', script], env=env, check=True, capture_output=True, text=True)
