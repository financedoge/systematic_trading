import json
from pathlib import Path
import numpy as np
import pytest

from systematic_trading.research import broadtrend as b, broadtrend_blend as mix
from systematic_trading.research.strategy_lifecycle import replay_supported
from systematic_trading.portfolio.strategy_allocation import allocation_contract_issue


def test_monitoring_is_supported_but_execution_is_not():
    d=b.definition()
    assert len(d.universe_members)==51
    assert replay_supported(d.key)
    assert allocation_contract_issue(d)
    assert b.model_pack()['training_end']=='2022-12-30'


def test_historical_exchange_closures_are_not_missing_observations():
    assert b.calendar('2004-06-10','2004-06-14')==['2004-06-10','2004-06-14']
    assert b.calendar('1994-01-17','1994-01-17')==['1994-01-17']


def test_pinned_model_tamper_fails(tmp_path,monkeypatch):
    path=tmp_path/'models.json';path.write_text('{}')
    monkeypatch.setattr(b,'PACK',path)
    with pytest.raises(ValueError,match='model pack changed'):b.model_pack()


def test_internal_etf_crossing_has_no_exchange_fee():
    cash=np.array([0.,0.]);units=np.array([.8,.2]);prices=np.ones(2)
    c,u,delta,fees=mix.rebalance(cash,units,prices,np.array([.7,.3]),np.ones(2),.01,np.array([0,0]))
    assert np.allclose(u,[.7,.3]);assert fees.sum()<1e-15
    assert np.allclose(delta,[-.1,.1]);assert c.sum()==0


def test_partial_cash_and_same_asset_net_cost_reconcile():
    c,u,d,f=mix.rebalance(np.array([1.,0.]),np.zeros(2),np.ones(2),np.array([.35,.3]),
        np.array([True,False]),.01,np.array([0,0]))
    assert c.sum()+u.sum()+f.sum()==pytest.approx(1)
    assert c[1]==pytest.approx(.3/(1+.0035))
    assert f.sum()==pytest.approx(.01*u.sum())


def test_sleeve_cash_not_reallocated_daily_and_future_is_irrelevant():
    days=np.array(['2024-01-31','2024-02-01','2024-02-02','2024-02-05','2024-02-06'])
    op=np.ones((5,2));cl=op.copy();cl[2:,0]=1.1;op[3:,0]=1.1
    desired=np.array([[True],[False],[False],[False],[False]])
    held=np.array([[False],[True],[False],[False],[False]])
    kwargs=dict(start=0,alpha=.7,cost_bp=0)
    z=mix.run(days,['A','B'],op,cl,np.tile([1.,0.],(5,1)),desired,held,['B'],**kwargs)
    assert z['cash'][2]==pytest.approx(.3/(.7*1.1+.3))
    assert z['group_capital'][2][0]!=pytest.approx(.7)
    # A later extreme quote cannot change an earlier fill or NAV.
    cl[-1]*=4
    q=mix.run(days,['A','B'],op,cl,np.tile([1.,0.],(5,1)),desired,held,['B'],**kwargs)
    assert np.array_equal(z['nav'][:-1],q['nav'][:-1])
    assert z['fills']==q['fills']


def test_existing_full_pool_reproduced_exactly():
    # Integration evidence uses the protected frozen model/data lineage.
    root=Path(__file__).resolve().parents[1];data={}
    for s in b.model_pack()['models']:
        with np.load(root/'var/research/range-breakout-20261018-v2/assets'/f'{s}.npz',allow_pickle=False) as z:data[s]=dict(z)
    result,arrays,_=b.replay(dict(data=data))
    with np.load(root/'var/research/trend-sleeve-portfolio-20261029-v1/shadows.npz',allow_pickle=False) as old:
        ix=[old['late_symbols'].tolist().index(s) for s in result['symbols']]
        assert np.array_equal(arrays['nav'],old['late_nav_c5d0'][:,ix])
        assert np.array_equal(arrays['desired'],old['late_desired_c5d0'][:,ix])
    assert result['nav'][-1]==pytest.approx(1.1750307172963841,abs=1e-14)
