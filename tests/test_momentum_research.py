from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal as D
import json

import pytest

from systematic_trading.domain.market import PriceBar
from systematic_trading.research.momentum_protocol import protocol
from systematic_trading.research.momentum_signals import horizon_rank, feature_frame, Membership, decision_sessions
from systematic_trading.research.momentum_replay import run_usd_reference, verify_usd_bundle
from systematic_trading.lean.contracts import write_json, sha256


def histories():
    result={s:[] for s in ('SPY','VGK','EWJ','EWH','EWY','MCHI','IEF','TLT')}
    for j,(s,rows) in enumerate(result.items()):
        for i in range(300):
            p=D(100)+D(i*(j+1))/100+D(i%7)/100
            rows.append(PriceBar(trade_date=date(2023,1,1)+timedelta(days=i),open=p,high=p,low=p,close=p,volume=10000+i*(j+1)))
    return result


def test_horizons_are_exact_and_older_signal_ignores_recent_month():
    bars=histories()
    old=horizon_rank(bars,21,63)
    for rows in bars.values():
        for i in range(1,22):
            rows[-i]=rows[-i].model_copy(update={'close':D(999999)})
    assert horizon_rank(bars,21,63)==old
    assert horizon_rank(bars,0,5)!=horizon_rank(histories(),0,5)
    with pytest.raises(ValueError):horizon_rank(bars,5,5)


def test_feature_prefix_invariance_and_mirrored_gates():
    bars=histories();day=date(2023,10,1)
    first=feature_frame(bars,day)
    for rows in bars.values():
        for i,row in enumerate(rows):
            if row.trade_date>=day:
                rows[i]=row.model_copy(update={'close':D(999999),'volume':1})
    assert feature_frame(bars,day)==first
    assert first['short_weights']['B1']+first['short_weights']['B2']==1
    assert first['short_weights']['B3']+first['short_weights']['B4']==1
    for s in bars:
        assert abs((D(first['scores']['B1'][s])+D(first['scores']['B2'][s]))/2-D(first['scores']['A8'][s]))<D('1e-25')


def frame(day,order,eligible=None):
    # .2 gaps make D exactly top six; a seventh can remain via slow exit.
    scores={s:str(D(1)-D(i)/5) for i,s in enumerate(order)}
    return dict(known_through=f'2024-01-{day:02d}',eligible=eligible or order,scores={'parent':scores})


def test_membership_symmetry_daily_confirmation_and_floor_override():
    slow_exit,slow_entry=Membership('C1'),Membership('C2')
    old=list('ABCDEFGH');new=list('GABCDEFH')
    for state in (slow_exit,slow_entry):
        selected,diag=state.update(frame(1,old),True)
        assert selected==set('ABCDEF') and diag['seed']
    a,da=slow_exit.update(frame(2,new),True)
    b,db=slow_entry.update(frame(2,new),True)
    assert a==set('ABCDEFG')
    assert b==set('ABCDEG') and db['floor_overrides']==['G']
    for day in (3,4,5):
        slow_exit.update(frame(day,new),False)
    a,_=slow_exit.update(frame(6,new),True)
    assert a==set('ABCDEG')
    with pytest.raises(ValueError):slow_exit.update(frame(6,new),True)


def test_membership_eligibility_reset_and_seed():
    state=Membership('C1')
    state.update(frame(1,list('ABCDEFGH')),True)
    selected,diag=state.update(frame(2,list('ABCDEFGH'),list('ABC')),False)
    assert selected is None and diag['fallback'] and not state.seeded
    selected,diag=state.update(frame(3,list('ABCDEFGH'),list('ABCD')),True)
    assert selected==set('ABCD') and diag['seed']


def test_weekly_clock_uses_available_sessions_across_holiday_and_year():
    days=['2023-12-29','2024-01-02','2024-01-03','2024-01-05','2024-01-08','2024-01-12','2024-01-16']
    assert decision_sessions(days,'2024-01-02','weekly')==['2024-01-02','2024-01-08','2024-01-16']
    assert decision_sessions(days,'2024-01-02','monthly')==['2024-01-02']


def test_registration_is_finite_with_reserved_missing_and_transfer_slots():
    p=protocol()
    assert len(p['recipes'])==26 and p['family_size']==58
    assert len({c['id'] for c in p['comparisons']})==58
    assert sum(c['id'].startswith('transfer') for c in p['comparisons'])==6


def usd_fixture(tmp_path):
    write_json(tmp_path/'spec.json',dict(contract='momentum-usd-adjusted-units-v1',accounting_currency='USD',promotion_eligible=False,
        initial_cash_usd='1000',transaction_cost_bps='10'))
    write_json(tmp_path/'sessions.json',['2024-01-02','2024-01-03'])
    write_json(tmp_path/'quotes.json',{'SPY':{'2024-01-02':dict(open='110',close='120',reference='100'),
                                          '2024-01-03':dict(open='100',close='100',reference='120')}})
    write_json(tmp_path/'decisions.json',{'2024-01-02':dict(signal_session='2024-01-02',known_through='2023-12-29',
        targets=[dict(symbol='SPY',sleeve='fixture',target_weight='0.5',rationale='fixture')])})
    write_json(tmp_path/'manifest.json',{p.name:sha256(p) for p in tmp_path.iterdir()})


def test_usd_cash_fees_prior_sizing_and_next_open_fills(tmp_path):
    usd_fixture(tmp_path)
    result=run_usd_reference(tmp_path)
    assert result['accounting_currency']=='USD'
    assert result['fills']==[dict(date='2024-01-02',symbol='SPY',quantity=5,price='110',fee='0.55')]
    assert D(result['nav'][0]['cash'])==D('449.45')
    assert D(result['nav'][0]['nav'])==D('1049.45')
    assert D(result['nav'][1]['nav'])==D('949.45')
    (tmp_path/'quotes.json').write_text('{}')
    with pytest.raises(ValueError,match='changed'):verify_usd_bundle(tmp_path)
