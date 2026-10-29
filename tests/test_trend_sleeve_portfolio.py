import numpy as np
import pytest
from systematic_trading.research import trend_sleeve_portfolio as p


def test_rank_is_prefix_only_and_excludes_cash():
    rng=np.random.default_rng(1)
    nav=np.cumprod(1+np.vstack([np.zeros(4),rng.normal(.001,.01,(300,4))]),axis=0)
    nav[:,3]=1
    a,_=p.rank_accounts(nav,['A','B','C','CASH'],252)
    nav[253:]*=10
    b,_=p.rank_accounts(nav,['A','B','C','CASH'],252)
    assert a==b and len(a)==3


def test_ties_use_ticker():
    nav=np.exp(np.cumsum(np.sin(np.arange(300))*.01))[:,None]*np.ones((1,3))
    rows,_=p.rank_accounts(nav,['Z','A','M'],252)
    assert [r['symbol'] for r in rows]==['A','M','Z']


def test_risk_is_covariance_erc_and_floored():
    # Exactly orthogonal sample: covariance diagonal, ERC = inverse volatility.
    r=np.array([[1,1],[1,-1],[-1,1],[-1,-1]],float)*np.array([.01,.02])
    w,error=p.risk_weights(r)
    np.testing.assert_allclose(w,[2/3,1/3],atol=1e-6)
    assert error<1e-6
    w,_=p.risk_weights(r*0)
    np.testing.assert_allclose(w,[.5,.5],atol=1e-6)


def test_rebalance_nets_and_charges_once():
    cash,units,delta,fees=p.rebalance(np.array([.5,.5]),np.zeros(2),np.ones(2),np.array([.5,.5]),np.ones(2,bool),.001)
    assert units.sum()==pytest.approx(1/1.001)
    c,u,d,f=p.rebalance(cash,units,np.ones(2),np.array([.5,.5]),np.ones(2,bool),.001)
    assert np.max(abs(d))<1e-12 and f.sum()<1e-12
    c,u,d,f=p.rebalance(c,u,np.ones(2),np.array([.5,.5]),np.array([False,True]),.001)
    assert c.sum()+u.sum()+f.sum()==pytest.approx(units.sum())


def fixture(delay=0):
    days=np.array(['2024-01-31','2024-02-01','2024-02-02','2024-02-05','2024-02-06'])
    prices=np.array([[1,1],[1,1],[1,2],[1,3],[1,4]],float)
    held=np.array([[0,0],[1,0],[0,1],[0,1],[0,1]],bool)
    return days,prices,held


def test_cash_stays_in_sleeve_and_delayed_adoption():
    days,prices,held=fixture()
    z=p.run(days,['A','B'],prices,prices,np.ones_like(prices),held,held,
        start=0,source='all',clock='buyhold',cost_bp=0)
    # A exits; B enters with only its own .5 capital, not the pooled 1.
    np.testing.assert_allclose(z['nav'],[1,1,1,1.25,1.5])
    assert z['cash'][-1]==pytest.approx(1/3)
    assert z['contribution'].sum()==pytest.approx(.5)
    delayed=p.run(days,['A','B'],prices,prices,np.ones_like(prices),held,held,
        start=0,source='all',clock='buyhold',cost_bp=0,delay=1)
    assert delayed['fills'][0]['date']=='2024-02-02'
    assert not any(f['symbol']=='A' for f in delayed['fills']) # pending exit wins on joining


def test_dynamic_includes_cash_and_uses_adopted_target():
    a=p.theoretical(np.array([.5,.5]),[True,False])
    b=p.theoretical(np.array([.5,.5]),[False,False])
    assert p.target_distance(a,b)==1


def test_departure_has_no_reset_and_ledger_includes_gaps():
    days=np.array(['2024-01-31','2024-02-01','2024-02-29','2024-03-01','2024-03-04'])
    op=np.array([[1,1],[1,1],[1,2],[1,3],[1,4]],float)
    cl=op.copy();cl[1]=[1,1.5]
    targets=np.array([[0,1],[0,1],[1,0],[1,0],[1,0]],float)
    active=np.ones_like(op,bool)
    z=p.run(days,['A','B'],op,cl,cl,active,active,start=0,source='fixed',fixed_targets=targets,cost_bp=5)
    assert z['fills'][-1]['date']=='2024-03-01'
    assert z['nav'][-1]==pytest.approx(3*(.9995/1.0005)/1.0005)
    assert z['contribution'].sum()==pytest.approx(z['nav'][-1]-1)
    assert z['ledger_error']<1e-12


def test_portfolio_prefix_causality():
    rng=np.random.default_rng(2);T=400;M=20
    days=np.arange(np.datetime64('2020-01-01'),np.datetime64('2020-01-01')+T).astype(str)
    prices=np.exp(np.cumsum(rng.normal(.001,.02,(T,M)),axis=0))
    active=rng.random((T,M))>.3
    kw=dict(start=252,cost_bp=5,clock='dynamic')
    a=p.run(days,[str(i) for i in range(M)],prices,prices,prices,active,active,**kw)
    prices[350:]*=rng.uniform(.5,2,(50,M));active[350:]=False
    b=p.run(days,[str(i) for i in range(M)],prices,prices,prices,active,active,**kw)
    np.testing.assert_allclose(a['nav'][:98],b['nav'][:98],atol=0,rtol=0)
