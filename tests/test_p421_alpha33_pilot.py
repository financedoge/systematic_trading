"""Guard the new field qualification, coverage and causal ranking contracts."""
import importlib.util
import gzip
import json
from pathlib import Path
import sys

import numpy as np
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))


def module(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


capture=module('capture_p421_alpha33')
audit=module('qualify_p421_alpha33')
backtest=module('backtest_p421_alpha33')


def test_filed_identifier_array_and_unsupported_country():
    assert capture.holding_cusip(dict(cusip='000000000',identifiers=[dict(type='isin',value='US0378331005')]))=='037833100'
    assert capture.holding_cusip(dict(cusip='000000000',identifiers=[dict(type='isin',value='GB0005405286')])) is None
    assert capture.holding_cusip(dict(cusip='000000000',identifiers=[])) is None


def test_missing_large_position_cannot_disappear_from_denominator():
    holdings=[dict(permno=1,value_usd=90),dict(permno=None,value_usd=10)]
    score,coverage=backtest.aggregate(holdings,{1:.8})
    assert np.isnan(score)
    assert coverage['value_fraction']==.9
    assert coverage['name_fraction']==.5


def test_fund_aggregation_uses_filed_value_and_fixed_gates():
    holdings=[dict(permno=1,value_usd=70),dict(permno=2,value_usd=27),dict(permno=None,value_usd=3)]
    score,c=backtest.aggregate(holdings,{1:1.,2:.5})
    assert c['value_fraction']==.97
    assert np.isnan(score)  # Name coverage is only 2/3, not 70%.
    score,c=backtest.aggregate(holdings,{1:1.,2:.5},min_names=.6)
    assert score==pytest.approx(83.5/97)


def valid_price():
    return (dict(raw_open=100,raw_close=102,adjusted_open=50,adjusted_close=51),
        dict(dlyopen=100,dlyclose=102,dlyprcflg='TR',cusip='03783310'),dict(cusip='03783310'))


def test_field_scoped_audit_does_not_consume_unqualified_volume():
    row,crsp,identity=valid_price()
    row.update(raw_volume=None,quality_flags=['volume_conflict'])
    assert audit.price_check(row,crsp,identity) is None


@pytest.mark.parametrize('change,expected',[
    ({'dlyprcflg':'BA'},'non_trade_close'),({'cusip':'99999999'},'dated_cusip_disagreement'),
    ({'dlyopen':102},'independent_price_disagreement'),({'dlyclose':None},'missing_price'),
    ({'dlyopen':-100},'nonpositive_price')])
def test_unqualified_price_stays_missing(change,expected):
    row,crsp,identity=valid_price()
    crsp.update(change)
    assert audit.price_check(row,crsp,identity)==expected


def test_inconsistent_adjustment_factor_rejected():
    row,crsp,identity=valid_price()
    row['adjusted_open']=49
    assert audit.price_check(row,crsp,identity)=='adjustment_factor_inconsistent'


def test_identity_interval_boundaries():
    r=dict(secinfostartdt='2025-03-01',secinfoenddt='2025-03-31')
    assert not audit.in_window(r,'2025-02-28')
    assert audit.in_window(r,'2025-03-01')
    assert audit.in_window(r,'2025-03-31')
    assert not audit.in_window(r,'2025-04-01')


def test_scoped_reader_matches_canonical_and_spaced_json_without_future_rows(tmp_path):
    path=tmp_path/'bars.jsonl.gz'
    rows=[dict(trade_date='2025-02-27',value=1),dict(trade_date='2025-02-28',value=2),
        dict(trade_date='2025-03-03',value=3),dict(trade_date='2025-03-04',value=4)]
    with gzip.open(path,'wt') as stream:
        for i,row in enumerate(rows):
            stream.write(json.dumps(row,separators=(',',':') if i%2 else (', ',': '))+'\n')
    class Reader:
        def checked(self,name):
            assert name=='bars/TEST.jsonl.gz'
            return path
    assert audit.window_rows(Reader(),'TEST','2025-02-28','2025-03-03')==rows[1:3]
    with gzip.open(path,'at') as stream:
        stream.write(json.dumps(rows[1])+'\n')
    with pytest.raises(ValueError,match='Duplicate or unsorted'):
        audit.window_rows(Reader(),'TEST','2025-02-28','2025-03-03')


def test_raw_intraday_ratio_matches_common_adjustment_factor():
    raw_open=np.array([10.,200.,50.])
    raw_close=np.array([11.,195.,51.])
    factors=np.array([.25,.98,2.])
    np.testing.assert_allclose(raw_open/raw_close-1,(raw_open*factors)/(raw_close*factors)-1,atol=1e-14)


def test_data_expansion_does_not_reselect_strategy_parameters():
    root=SCRIPTS.parent/'research'
    old=json.loads((root/'p421-alpha33-pilot-20261107-v1/protocol.json').read_text())
    new=json.loads((root/'p421-alpha33-pilot-20261108-v2/protocol.json').read_text())
    for key in ('evaluation','holdings_date','formula','rank_universe','aggregation','coverage','models',
                'construction','policies','primary_policy','timing','costs_bps','delays','controls','selection'):
        assert new[key]==old[key],key


def test_replay_signal_executes_only_after_observation():
    from systematic_trading.domain.market import Instrument
    a=dict(symbols=np.array(['SPY']),days=np.array(['2025-02-28','2025-03-03','2025-03-04']),
        close=np.array([[100.],[101.],[102.]]),open=np.array([[99.],[100.],[101.]]),
        urth_open=np.array([99.,100.,101.]),urth_close=np.array([100.,101.,102.]))
    recipe=dict(universeMembers=[Instrument(symbol=s,name=s,asset_class='etf',exchange='NYSE',quote_currency='USD',country='US',sector='test').model_dump(mode='json') for s in ['SPY','URTH']])
    engine=backtest.PilotReplay(a,recipe,'2025-03-03')
    weights=np.array([[.98,0],[.2,0],[0,0]])
    normal=engine.decisions(weights,[0],0)
    delayed=engine.decisions(weights,[0],1)
    assert [str(d) for d in normal]==['2025-03-03']
    assert [str(d) for d in delayed]==['2025-03-04']
    assert float(next(iter(normal.values()))[0].target_weight)==.98
