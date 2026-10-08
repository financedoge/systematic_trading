import json
from decimal import Decimal as D

import pytest

from systematic_trading.portfolio.allocation_performance import build_strategy_comparison
from test_analytics_projection import MemoryAnalytics


def publication(series):
    analytics = MemoryAnalytics()
    analytics.publish('strategy-serving', 'verified-v1', [], [dict(point_key='detail/'+key, payload=json.dumps(dict(
        strategy_id=key, app_tracking=True, input_provenance=dict(batch='audited', governed_files={'prices':'hash'}),
        nav_series=[dict(trade_date=d, nav_cnh=v) for d, v in values], warnings=['FX availability limitation'])))
        for key, values in series.items()])
    return analytics


def epoch(start, version, weights, opening='1000'):
    return dict(effective_close=start, version=version, label=version, opening_nav_cnh=opening,
                allocations=[dict(strategy_key=k, weight=w) for k,w in weights.items()])


def test_switch_compounds_ratios_at_exact_boundary_and_actual_rebase_excludes_jump():
    analytics = publication({'A':[('2026-10-01','100'),('2026-10-02','110'),('2026-10-05','5')],
                             'B':[('2026-10-01','500'),('2026-10-02','200'),('2026-10-05','240')]})
    timeline = [epoch('2026-10-01','first',{'A':'1'}),epoch('2026-10-02','second',{'B':'1'})]
    result = build_strategy_comparison(timeline, analytics, [('2026-10-01',D(1000)),('2026-10-02',D(900)),('2026-10-05',D(950))])
    assert [D(p['nav_cnh']) for p in result['strategy']] == [1000,1100,1320]
    assert [D(p['nav_cnh']) for p in result['actual_rebased']] == [1000,1100,900,1080]
    assert [D(p['index']) for p in result['actual_rebased']] == [100,110,110,132]
    assert result['actual_rebased'][2]['break_before']
    assert result['strategy'][1]['allocation_version'] == 'first'
    assert result['strategy'][1]['switch_anchor']
    assert result['strategy'][1]['period_start'] == '2026-10-01'
    assert [D(p['theoretical_return']) for p in result['periods']] == [D('.1'),D('.2')]
    assert D(result['periods'][1]['theoretical_pnl_cnh']) == 180
    assert D(result['periods'][1]['actual_pnl_cnh']) == 50
    assert result['sources']['A']['publication'] == 'verified-v1'
    assert len(result['sources']['A']['document_sha256']) == 64


def test_mixed_capital_and_cash_use_weighted_nav_ratios_not_average_raw_nav_or_daily_reset():
    analytics = publication({'A':[('2026-10-01','10'),('2026-10-02','20'),('2026-10-05','10')],
                             'B':[('2026-10-01','1000'),('2026-10-02','1000'),('2026-10-05','2000')]})
    result = build_strategy_comparison([epoch('2026-10-01','mix',{'A':'.6','B':'.3'})],analytics,[])
    assert [D(p['nav_cnh']) for p in result['strategy']] == [1000,1600,1300]


def test_switch_with_only_opening_value_has_zero_return_not_missing_or_future_return():
    result = build_strategy_comparison([epoch('2026-10-02','first',{'A':'1'})],
        publication({'A':[('2026-10-02','987654')]}),[])
    assert len(result['strategy']) == 1
    assert result['periods'][0]['theoretical_return'] == '0'
    assert result['periods'][0]['through'] == '2026-10-02'
    assert D(result['periods'][0]['theoretical_pnl_cnh']) == 0
    assert result['periods'][0]['actual_return'] is None


def test_missing_boundary_never_uses_next_day_or_another_strategy():
    analytics = publication({'A':[('2026-10-01','100'),('2026-10-02','110')],
                             'B':[('2026-10-05','200')]})
    result = build_strategy_comparison([epoch('2026-10-01','a',{'A':'1'}),epoch('2026-10-02','b',{'B':'1'})],analytics,[])
    assert len(result['strategy']) == 2
    assert result['periods'][1]['theoretical_return'] is None
    assert any('Missing exact switch-date' in w for w in result['warnings'])


def test_missing_component_session_stops_period_and_only_actual_mode_can_resume():
    analytics = publication({'A':[('2026-10-01','100'),('2026-10-05','110')],
                             'B':[('2026-10-05','200'),('2026-10-06','240')]})
    result = build_strategy_comparison([epoch('2026-10-01','a',{'A':'1'}),epoch('2026-10-05','b',{'B':'1'},'800')],analytics,[])
    assert [p['trade_date'] for p in result['strategy']] == ['2026-10-01']
    assert [D(p['nav_cnh']) for p in result['actual_rebased']] == [1000,800,960]
    assert result['actual_rebased'][1]['return_break']
    assert any('Missing published strategy NAV on 2026-10-02' in w for w in result['warnings'])


def test_missing_actual_switch_value_never_reuses_earlier_account_mark():
    result = build_strategy_comparison([epoch('2026-10-02','a',{'A':'1'},None)],
        publication({'A':[('2026-10-02','100')]}),[('2026-10-01',D(1000))])
    assert not result['strategy'] and not result['actual_rebased']
    assert any('no observed account NAV' in w for w in result['warnings'])


def test_cumulative_comparison_reanchors_after_unverified_history_at_observed_account_nav():
    analytics = publication({'legacy':[('2026-09-24','100')],
                             'verified':[('2026-10-01','500'),('2026-10-02','510')]})
    timeline = [epoch('2026-09-24','unavailable',{'missing':'1'}),
                epoch('2026-10-01','verified',{'verified':'1'},'999')]
    result = build_strategy_comparison(timeline, analytics,
        [('2026-10-01',D(2000)),('2026-10-02',D(2100))])
    assert result['comparison_start_date'] == '2026-10-01'
    assert D(result['base_nav_cnh']) == 2000
    assert [D(p['nav_cnh']) for p in result['strategy']] == [2000,2040]
    assert D(result['strategy'][0]['index']) == 100
    assert any('earlier allocation history is excluded' in w for w in result['warnings'])


def test_opening_value_cannot_recover_continuous_series_after_history_gap():
    analytics = publication({'verified':[('2026-10-01','500'),('2026-10-02','510')]})
    timeline = [epoch('2026-09-24','unavailable',{'missing':'1'}),
                epoch('2026-10-01','verified',{'verified':'1'},'999')]
    result = build_strategy_comparison(timeline, analytics, [])
    assert result['comparison_start_date'] is None
    assert result['base_nav_cnh'] is None
    assert result['strategy'] == []


@pytest.mark.parametrize('value',['NaN','Infinity','0','-1','bad'])
def test_invalid_published_values_are_rejected(value):
    with pytest.raises(ValueError,match='Invalid or duplicate'):
        build_strategy_comparison([epoch('2026-10-02','a',{'A':'1'})],
            publication({'A':[('2026-10-02',value)]}),[])


def test_archive_without_governed_app_lineage_is_not_used():
    analytics = publication({'A':[('2026-10-02','100')]})
    detail = json.loads(analytics.docs['strategy-serving'][0]['payload'])
    detail['app_tracking'] = False
    analytics.docs['strategy-serving'][0]['payload'] = json.dumps(detail)
    result = build_strategy_comparison([epoch('2026-10-02','a',{'A':'1'})],analytics,[])
    assert not result['strategy']
    assert any('no app-calculated, audited' in w for w in result['warnings'])


def test_publication_race_is_rejected():
    analytics = publication({'A':[('2026-10-02','100')]})
    original = analytics.document
    def racing(*args):
        document, metadata = original(*args)
        return document, dict(metadata,version='changed')
    analytics.document = racing
    with pytest.raises(ValueError,match='publication changed'):
        build_strategy_comparison([epoch('2026-10-02','a',{'A':'1'})],analytics,[])


def test_dashboard_uses_strategy_nav_not_empty_reference_and_exposes_zero_opening_return(dashboard):
    from test_dashboard_performance import performance, snapshot
    client, _, root = dashboard
    key = 'A'
    client.app.state.strategy_analytics = publication({key:[('2026-10-02','200')]})
    client.app.state.allocation_analytics = dict(timeline=[epoch('2026-10-02','a',{key:'1'})],reference=[],warnings=[])
    snapshot(root,'switch.json',day='2026-10-02',captured='2026-10-02T21:00:00Z',cash='900')
    result = performance(client)
    assert D(result['strategy_total_return']) == 0
    assert result['strategy_comparison_start_date'] == '2026-10-02'
    assert D(result['strategy'][0]['nav_cnh']) == 900
    assert result['theoretical_contract']
    assert len(result['strategy_actual_rebased']) == 1


from test_dashboard_performance import dashboard  # noqa: E402


def test_legacy_recovery_uses_executed_identity_and_clips_later_reset(monkeypatch):
    from datetime import datetime, UTC
    from types import SimpleNamespace as N
    from systematic_trading.portfolio.allocation_performance import comparison_timeline
    from systematic_trading.portfolio.context import PortfolioContext
    from systematic_trading.research import strategy_catalog
    monkeypatch.setattr(strategy_catalog, 'registered_strategy_definition', lambda k:N(sleeve_name=k.replace('_','-'),name=k))
    monkeypatch.setattr('systematic_trading.portfolio.context.portfolio_context', lambda _: PortfolioContext(
        account_id='DU1', cutoff_at=datetime(2026,9,25,tzinfo=UTC)))
    def proposal(key, id):
        return N(proposal_id=id, sleeve=key.replace('_','-'),input_provenance={})
    def record(id, at, account='DU1'):
        return N(proposal_id=id,execution_sync_issue=None,execution_fills=[N(account=account,filled_at=datetime.fromisoformat(at))])
    store=N(list_proposals=lambda:[proposal('old','p1'),proposal('usd','p2'),proposal('unfilled','p3')],
        list_broker_order_records=lambda:[record('p1','2026-09-25T13:40:00+00:00'),record('p2','2026-10-02T15:00:00+00:00')])
    explicit=[epoch('2026-10-02','new',{'rolling':'1'})]
    result=comparison_timeline(store,explicit,[('2026-09-24',D(1000))])
    assert [r['effective_close'] for r in result] == ['2026-09-24','2026-10-01','2026-10-02']
    assert [r['allocations'][0]['strategy_key'] for r in result] == ['old','usd','rolling']
    assert 'intraday' in result[0]['warning']
    later=comparison_timeline(store,result,[('2026-10-05',D(900))])
    assert len(later)==1 and later[0]['effective_close']=='2026-10-05'
    assert result[-1]['effective_close']=='2026-10-02', 'Never mutate allocation authority'


def test_named_parent_benchmark_uses_pinned_app_report_and_audited_lineage():
    analytics=publication({'parent_usd_v1':[('2026-10-01',100),('2026-10-02',110)]})
    detail=json.loads(analytics.docs['strategy-serving'][0]['payload'])
    analytics.publish('tracked-strategies/calculations','calculation-v1',[],[
        dict(point_key='detail/parent_usd_v1',payload=json.dumps(detail)),
        dict(point_key='report/parent_usd_v1',payload=json.dumps(dict(chart=[
            dict(date='2026-10-01',nav=900,benchmarks={'parent':{'nav':100}}),
            dict(date='2026-10-02',nav=999,benchmarks={'parent':{'nav':102}})])))])
    result=build_strategy_comparison([epoch('2026-10-01','old',{'parent':'1'})],analytics,[])
    assert D(result['strategy'][-1]['nav_cnh'])==1020
    assert result['sources']['parent']['benchmark_key']=='parent'
    detail['input_provenance']={}
    analytics.docs['tracked-strategies/calculations'][0]['payload']=json.dumps(detail)
    assert not build_strategy_comparison([epoch('2026-10-01','old',{'parent':'1'})],analytics,[])['strategy']
