import json
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import pytest

from systematic_trading.portfolio.strategy_allocation import control_state, scope_for
from systematic_trading.research.strategy_catalog import defensive_cash_definition
from systematic_trading.research.strategy_lifecycle import (
    SCOPE, membership, effective_config, change_membership, require_monitored, calculation_ready, decorate_catalog,
)
from systematic_trading.storage.sqlite import SQLiteStore

KEY=defensive_cash_definition().key


@pytest.fixture
def setup(tmp_path):
    store=SQLiteStore(tmp_path/'state.db');store.initialize()
    config=tmp_path/'monitoring.json'
    config.write_text(json.dumps(dict(schema_version=2,monitored_strategy_ids=[KEY,control_state(store)['sota_key']])))
    return SimpleNamespace(strategy_monitoring_config_path=config),store


def change(setup, lifecycle, revision, event=None):
    return change_membership(*setup,key=KEY,lifecycle=lifecycle,expected_revision=revision,
        event_id=event or f'event-{revision}',operator='Test operator',reason='Test lifecycle')


def detail(generation=0):
    return dict(strategy_id=KEY,lifecycle='monitored',monitoring_generation=generation,
        app_tracking=True,end_date='2026-10-06')


def test_archive_restore_is_durable_and_requires_new_complete_generation(setup):
    settings,store=setup
    original=detail()
    assert calculation_ready(original,membership(*setup),'2026-10-06')
    change(setup,'archived',0)
    with pytest.raises(ValueError,match='restricted to monitored'):
        require_monitored(*setup,[KEY])
    assert KEY not in effective_config(*setup)['monitored_strategy_ids']
    restored=change(setup,'monitored',1)
    assert not calculation_ready(original,restored)
    assert not calculation_ready(detail(2),restored,'2026-10-07')
    assert calculation_ready(detail(2),restored,'2026-10-06')
    restarted=SQLiteStore(store.database_path)
    assert membership(settings,restarted)==restored
    assert len(restarted.strategy_control_events(SCOPE))==2


def test_retry_and_stale_update_never_overwrite_membership(setup):
    archived=change(setup,'archived',0)
    assert change(setup,'archived',0)==archived
    with pytest.raises(ValueError,match='membership changed'):
        change(setup,'monitored',0,'different')
    assert KEY not in membership(*setup)['monitored']


@pytest.mark.parametrize('role',['sota','funded','pending'])
def test_archive_guards_active_roles_and_pending_changes(setup,role):
    _,store=setup;state=deepcopy(control_state(store))
    if role=='sota':state['sota_key']=KEY
    if role=='funded':state['active']['allocations']=[dict(strategy_key=KEY,weight='0.1')]
    if role=='pending':state['pending']=dict(change=dict(allocations=[dict(strategy_key=KEY,weight='0.1')]))
    store.commit_strategy_control(scope_for(store),0,state,dict(event_id='role',request_hash='role'))
    with pytest.raises(ValueError,match='before archiving'):
        change(setup,'archived',0)
    assert membership(*setup)['revision']==0


def test_membership_guard_rejects_allocation_commit_reviewed_before_archive(setup):
    _,store=setup;state=control_state(store)
    change(setup,'archived',0)
    with pytest.raises(ValueError,match='membership or allocation changed'):
        store.commit_strategy_control(scope_for(store),0,state,dict(event_id='stale',request_hash='stale'),guard_revisions={SCOPE:0})
    assert control_state(store)['revision']==0


def test_catalog_immediately_pauses_and_marks_restore_catching_up(setup):
    change(setup,'archived',0)
    row=decorate_catalog(dict(strategies=[detail()]),*setup)['strategies'][0]
    assert row['lifecycle']=='archived' and row['calculation_status']=='Paused' and not row['allocation_ready']
    change(setup,'monitored',1)
    row=decorate_catalog(dict(strategies=[detail()]),*setup)['strategies'][0]
    assert row['calculation_status']=='Catching up' and not row['allocation_ready']
    missing=decorate_catalog(dict(strategies=[]),*setup)['strategies']
    assert next(r for r in missing if r['strategy_id']==KEY)['calculation_status']=='Catching up'


def test_catalog_reads_control_once_per_scope_without_hiding_later_changes(setup):
    from systematic_trading.web.strategy_catalog_view import CatalogControlView
    _,store=setup;reads=[]
    view=CatalogControlView(SimpleNamespace(latest_pnl_baseline=lambda:None,
        strategy_control_state=lambda scope:reads.append(scope) or store.strategy_control_state(scope)))
    decorate_catalog(dict(strategies=[detail(),dict(detail(),strategy_id='unknown')]),setup[0],view)
    assert len(reads)==len(set(reads))==2
    change(setup,'archived',0)
    fresh=decorate_catalog(dict(strategies=[detail()]),setup[0],CatalogControlView(store))
    assert fresh['strategies'][0]['lifecycle']=='archived'


def test_unknown_archive_cannot_pretend_to_have_a_replay(setup):
    with pytest.raises(ValueError,match='no supported replay'):
        change_membership(*setup,key='unknown',lifecycle='monitored',expected_revision=0,event_id='unknown',operator='Me',reason='Restore')


def test_monitoring_endpoint_restarts_app_work_and_rejects_stale_transition(setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from systematic_trading.web.strategy_control import router
    app=FastAPI();app.include_router(router)
    app.state.settings,app.state.store=setup
    refreshed=[]
    app.state.analytics_service=SimpleNamespace(request_refresh=lambda **kw:refreshed.append(kw))
    body=dict(strategy_key=KEY,lifecycle='archived',expected_revision=0,event_id='archive-ui',operator='Tester',reason='Pause')
    with TestClient(app) as client:
        response=client.post('/api/v1/portfolio/strategy-control/monitoring',json=body)
        assert response.status_code==200 and KEY not in response.json()['monitored']
        stale=dict(body,lifecycle='monitored',event_id='restore-ui')
        assert client.post('/api/v1/portfolio/strategy-control/monitoring',json=stale).status_code==409
        stale['expected_revision']=1
        response=client.post('/api/v1/portfolio/strategy-control/monitoring',json=stale)
        assert response.status_code==200 and KEY in response.json()['monitored']
    assert len(refreshed)==2
    assert not calculation_ready(detail(),membership(*setup))


def test_report_currency_and_archived_banner():
    from systematic_trading.backtest.reporting import render_backtest_report_html
    from systematic_trading.web.strategy_refresh import report_refresh_banner
    html=render_backtest_report_html(dict(accountingCurrency='USD'))
    assert 'Value USD' in html and 'return "USD "' in html and 'daily USD price returns' in html
    assert 'Value CNH' not in html and '__ACCOUNTING_CURRENCY__' not in html
    banner=report_refresh_banner(dict(published_at='now',version='v'),dict(research_job='tracked-strategies'),dict(lifecycle='archived',end_date='2026-10-01'))
    assert 'calculations paused' in banner and '2026-10-01' in banner and 'fetch(' not in banner


def test_usd_nav_requires_exact_observed_cnh_bridge():
    from test_allocation_performance import publication,epoch
    from systematic_trading.portfolio.allocation_performance import build_strategy_comparison
    analytics=publication({KEY:[('2026-10-01','100'),('2026-10-02','110')]})
    document=analytics.docs['strategy-serving'][0]
    row=json.loads(document['payload']);row['accounting_currency']='USD'
    document['payload']=json.dumps(row)
    timeline=[epoch('2026-10-01','v',{KEY:'1'})]
    assert not build_strategy_comparison(timeline,analytics,[])['strategy']
    row['cnh_nav_series']=[dict(trade_date='2026-10-01',nav_cnh='700'),dict(trade_date='2026-10-02',nav_cnh='700')]
    document['payload']=json.dumps(row)
    result=build_strategy_comparison(timeline,analytics,[])
    assert [Decimal(r['nav_cnh']) for r in result['strategy']]==[1000,1000]


def test_full_replay_includes_missed_trades_instead_of_marking_archived_holdings(tmp_path):
    from systematic_trading.research.momentum_replay import freeze_usd_bundle,run_usd_reference
    from systematic_trading.lean.contracts import write_json
    source=tmp_path/'inputs';(source/'source').mkdir(parents=True)
    write_json(source/'protocol.json',dict(initial_cash_usd='1000',limitations=[]))
    write_json(source/'input_manifest.json',{})
    days=['2026-01-02','2026-02-02','2026-03-02']
    decisions={d:dict(known_through=prior,targets=[dict(symbol='SPY',sleeve='test',target_weight=w,rationale='scheduled')])
        for d,prior,w in zip(days,['2025-12-31','2026-01-30','2026-02-27'],['.9','0','.5'])}
    quotes={'SPY':{d:dict(open=p,close=p,reference=p) for d,p in zip(days,['10','20','30'])}}
    paused=freeze_usd_bundle(tmp_path/'paused',source,{},dict(list(decisions.items())[:1]),{'SPY':{days[0]:quotes['SPY'][days[0]]}},days[:1],5)
    paused_result=run_usd_reference(paused)
    restored=freeze_usd_bundle(tmp_path/'restored',source,{},decisions,quotes,days,5)
    result=run_usd_reference(restored)
    assert len(result['nav'])==3 and {f['date'] for f in result['fills']}==set(days)
    assert result['fills'][1]['quantity']<0 and result['fills'][2]['quantity']>0
    assert Decimal(result['nav'][-1]['nav']) != Decimal(paused_result['nav'][-1]['cash'])+paused_result['final_positions']['SPY']*Decimal(30)
