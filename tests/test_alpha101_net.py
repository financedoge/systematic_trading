"""Finite research: causal alpha computation, missing scores, cap and selection."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_alpha101_net as s
from systematic_trading.research.alpha101 import History, value


@pytest.mark.parametrize('seed',[1,5,12])
def test_short_suffix_matches_full_history_and_future_mutation(seed):
    rng=np.random.default_rng(seed);n=270
    close=100*np.exp(np.cumsum(rng.normal(0,.01,n)))
    fields=dict(open=close*.998,high=close*1.02,low=close*.98,close=close,
                volume=rng.integers(1_000_000,5_000_000,n).astype(float),raw_close=close*1.1)
    days=np.array([str(i) for i in range(n)])
    actual=s.alpha_column(('TEST',days,fields))
    for i in (252,260,269):
        h=History('TEST',str(days[i]),**{k:v[:i+1] for k,v in fields.items()})
        for j,name in enumerate(s.ALPHAS):
            expected=value(name,h)
            if expected is None:assert np.isnan(actual[i,j])
            else:assert actual[i,j]==pytest.approx(expected,abs=1e-10)
    changed={k:v.copy() for k,v in fields.items()}
    for v in changed.values():v[261:]*=3
    assert np.allclose(s.alpha_column(('TEST',days,changed))[:261],actual[:261],equal_nan=True)


def test_mapping_missing_constant_cap_and_ties():
    symbols=list('ABCDEFGH');score=np.arange(8,dtype=float);vol=np.ones(8);eligible=np.ones(8,bool)
    assert not s.portfolio(np.ones(8),vol,eligible,symbols).any()
    assert not s.portfolio(np.array([1,2,3,4,5,np.nan,np.nan,np.nan]),vol,eligible,symbols).any()
    vol[-1]=.001
    w=s.portfolio(score,vol,eligible,symbols)
    assert w.max()<=.45 and w.sum()<.98 and np.count_nonzero(w)==6
    score[:]=0;score[-1]=1
    w=s.portfolio(score,np.ones(8),eligible,symbols)
    assert set(np.array(symbols)[w>0])==set('ABCDEH')
    assert s.portfolio(np.ones(8),np.ones(8),eligible,symbols,unranked=True).sum()==pytest.approx(.98)


def test_selection_uses_only_calibration():
    rows=[]
    for a in [*('alpha'+x for x in s.ALPHAS),'momentum','unranked']:
        for p in s.POLICIES:
            sharpe=2 if a=='alpha26' and p=='monthly' else 1
            rows.append(dict(arm=a+'-'+p,cost_bp=5,delay=0,windows={
                'calibration':dict(sharpe=sharpe,cagr=.1,max_drawdown=.1),
                'later':dict(sharpe=100 if a=='alpha54' else -10)}))
    assert s.select(rows)['selected']=='alpha26-monthly'
    assert s.select(rows)['eligible_vs_controls']


def test_raw_volume_missing_disables_26_without_price_substitution():
    x=np.linspace(100,110,260)
    fields=dict(open=x,high=x+1,low=x-1,close=x,raw_close=x,volume=np.full(260,np.nan))
    result=s.alpha_column(('TEST',np.arange(260).astype(str),fields))
    assert np.isnan(result[252:,1]).all()
    assert np.isfinite(result[252:,0]).all()
