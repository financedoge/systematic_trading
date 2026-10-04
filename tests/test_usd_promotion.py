from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research import instruments_for_definition
from systematic_trading.research.strategy_catalog import (
    current_sota_definition, legacy_sota_definition, etf_activity_lag20_definition,
    rolling_xgboost_1y_definition, usd_strategy_definition, registered_strategy_definition,
)
from systematic_trading.research.usd_data import load_usd
from systematic_trading.research.usd_tracking import VERSION, usd_prediction, published_live_schedule


def panel():
    days = [date(2023,1,1)+timedelta(days=i) for i in range(670)]
    days = [d for d in days if d.weekday()<5 and d <= date(2024,10,31)]
    histories = {}
    for j,s in enumerate(instruments_for_definition(current_sota_definition())):
        histories[s] = [PriceBar(symbol=s, trade_date=d, open=100+i*.1+j, high=110+i*.1+j,
            low=90+i*.1+j, close=100+i*.1+j+(i%7)*.2, volume=100000+i*50) for i,d in enumerate(days)]
    models = {s:dict(features=['S','L','vol63','USD21','USD63'], coefficients=[0,0,0,j*.01,0],
        means=[0]*5, scales=[1]*5, intercept=0, training_months=60, max_label_end='2024-09-30') for j,s in enumerate(histories)}
    snapshot = dict(known_through='2024-10-31', vintage_date='2024-10-30', observation_date='2024-10-25', features=dict(USD21=.02,USD63=.04))
    return histories, dict(version=VERSION, models={'2024-10-31':dict(models=models, fit_close='2024-10-31')}, snapshots=[snapshot])


def test_new_versions_preserve_parents_and_usd_is_after_xgboost_and_activity():
    for parent in [legacy_sota_definition(), etf_activity_lag20_definition(), rolling_xgboost_1y_definition()]:
        promoted = usd_strategy_definition(parent)
        assert promoted.overlays[:-1] == parent.overlays
        assert promoted.overlays[-1].kind == 'usd_ridge'
        assert registered_strategy_definition(parent.key) == parent
        assert registered_strategy_definition(promoted.key) == promoted
    assert current_sota_definition().promoted_on == '2026-10-02'


def test_complete_strategy_uses_usd_once_and_ignores_future_prices():
    from systematic_trading.research.usd_momentum_model import apply_usd_predictions
    histories, schedule = panel()
    rows = {s:[r.model_dump(mode='json') for r in h] for s,h in histories.items()}
    day = date(2024,11,1)
    parent = targets_for_day(rows, day, definition=legacy_sota_definition())
    prediction = usd_prediction(schedule, histories, day)
    expected = apply_usd_predictions(parent, prediction['predictions'])
    actual = targets_for_day(rows, day, definition=current_sota_definition(), usd_models=schedule)
    assert [t.target_weight for t in actual] == [t.target_weight for t in expected]
    for s in rows:
        rows[s].append(dict(rows[s][-1], trade_date=str(day), close='999999'))
    assert targets_for_day(rows, day, definition=current_sota_definition(), usd_models=schedule) == actual
    assert sum(t.target_weight for t in actual) == pytest.approx(sum(t.target_weight for t in parent), abs=Decimal('1e-20'))


def test_missing_month_stale_vintage_and_uncompleted_labels_fail_closed():
    histories, schedule = panel()
    day = date(2024,11,1)
    with pytest.raises(ValueError, match='schedule required'):
        usd_prediction(None, histories, day)
    bad = deepcopy(schedule)
    bad['models']['2024-09-30'] = bad['models'].pop('2024-10-31')
    with pytest.raises(ValueError, match='monthly USD model'):
        usd_prediction(bad, histories, day)
    bad = deepcopy(schedule); bad['snapshots'][0]['vintage_date'] = '2024-10-31'
    with pytest.raises(ValueError, match='snapshot'):
        usd_prediction(bad, histories, day)
    bad = deepcopy(schedule); bad['snapshots'][0]['observation_date'] = '2024-10-01'
    with pytest.raises(ValueError, match='Stale USD'):
        usd_prediction(bad, histories, day)
    bad = deepcopy(schedule); next(iter(bad['models']['2024-10-31']['models'].values()))['max_label_end'] = '2024-10-31'
    with pytest.raises(ValueError, match='training cutoff'):
        usd_prediction(bad, histories, day)


def test_paper_completed_close_targets_match_shared_backtest():
    from systematic_trading.live.sota import _sota_targets_as_of
    from systematic_trading.research import instantiate_overlays
    histories, schedule = panel()
    definition = current_sota_definition()
    overlays = instantiate_overlays(definition)
    overlays[-1].schedule = schedule
    actual, _ = _sota_targets_as_of(instruments=instruments_for_definition(definition),
        bars_by_symbol=histories, trade_dates=[r.trade_date for r in histories['SPY']],
        decision_date=date(2024,10,31), sleeve_name=definition.sleeve_name, overlays=overlays,
        lookback_bars=63, max_weight=Decimal('.45'), cash_reserve_weight=Decimal('.02'))
    expected = targets_for_day({s:[r.model_dump(mode='json') for r in rows] for s,rows in histories.items()},
        date(2024,11,1), definition=definition, usd_models=schedule)
    assert actual == expected


def test_published_input_hashes_and_execution_batch_binding(tmp_path, monkeypatch):
    histories, schedule = panel()
    write_json(tmp_path/'snapshots.json', [dict(schedule['snapshots'][0], limitations=[])])
    write_json(tmp_path/'manifest.json', {'snapshots.json':sha256(tmp_path/'snapshots.json')})
    pub = dict(version=sha256(tmp_path/'manifest.json'), provenance=json.dumps(dict(root=str(tmp_path))))
    fake = SimpleNamespace(latest=lambda _:pub)
    assert len(load_usd(fake)[0]) == 1
    (tmp_path/'snapshots.json').write_text('[]')
    with pytest.raises(ValueError, match='input changed'):
        load_usd(fake)
    write_json(tmp_path/'model.json', schedule)
    receipt = dict(path=str(tmp_path/'model.json'), sha256=sha256(tmp_path/'model.json'))
    report = dict(strategyDefinition=current_sota_definition().to_dict(), usdModel=dict(receipt=receipt,batch='usd-batch'))
    pub = dict(version='calculation', provenance=json.dumps(dict(inputs=dict(batch='price-batch'))))
    fake = SimpleNamespace(document=lambda *args:({'payload':json.dumps(report)},pub))
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    monkeypatch.setattr(AnalyticsStore,'from_settings',lambda _:fake)
    assert published_live_schedule(None,current_sota_definition(),'price-batch')[0] == schedule
    with pytest.raises(ValueError,match='inputs differ'):
        published_live_schedule(None,current_sota_definition(),'other-price-batch')
    (tmp_path/'model.json').write_text('{}')
    with pytest.raises(ValueError,match='hash mismatch'):
        published_live_schedule(None,current_sota_definition(),'price-batch')


def test_usd_market_endpoint_serves_committed_data_and_reports_missing_publication():
    from systematic_trading.web.usd_data import router
    app = FastAPI();app.include_router(router)
    app.state.analytics = SimpleNamespace(document=lambda *args: None)
    with TestClient(app) as client:
        assert client.get('/api/v1/market-data/usd/history').status_code == 503
        app.state.analytics.document = lambda *args: ({'payload':json.dumps(dict(series='DTWEXBGS',observations=[dict(date='2024-01-01',value=None)]))},dict(version='hash',published_at='2024-01-02'))
        result = client.get('/api/v1/market-data/usd/history').json()
        assert result['batch'] == 'hash' and result['observations'][0]['value'] is None
