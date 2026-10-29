"""Adversarial order timing and frozen study receipt checks."""
import gzip
import json
from pathlib import Path
import numpy as np
from systematic_trading.research import stop_review as m
from test_stop_review import flat,RULE


def test_delayed_exit_preserves_rearm_and_can_signal_at_exit_close():
    f,c=flat();c['fast_probability'][4]=[.95,.04,.01];c['fast_down'][4]=True;c['eligible'][4]=False
    c['fast_probability'][5]=[.1,.8,.1];c['fast_down'][5]=False;c['eligible'][5]=False
    f.close[8:]=101;f.high[8:]=102
    a=m.simulate(f,c,start=1,delay=1,mode='baseline');b=m.simulate(f,c,start=1,delay=1,mode='close_next',rule=dict(enabled=False))
    np.testing.assert_array_equal(a['desired'],b['desired']);np.testing.assert_allclose(a['nav'],b['nav'],equal_nan=True,rtol=0,atol=1e-14)
    assert [e['session'] for e in b['fills'][:3]]==[3,6,8]


def test_protective_fill_cancels_pending_delayed_exit():
    f,c=flat();c['fast_probability'][4]=[.95,.04,.01];c['fast_down'][4]=True;c['eligible'][4]=False
    f.low[5]=95
    a=m.simulate(f,c,start=1,delay=1,rule=dict(enabled=False))
    assert [(e['session'],e['side']) for e in a['fills'][:2]]==[(3,'buy'),(5,'sell')]
    assert not any(e['session']==6 and e['side']=='sell' for e in a['fills'])


def test_no_same_day_recovery_and_stop_cannot_use_later_bar():
    f,c=flat();f.low[3]=96
    a=m.simulate(f,c,start=1,rule=RULE,recovery=True)
    assert not a['review_signal'][3]
    g,cc=flat();g.high[20:]=1000;g.low[20:]=1
    b=m.simulate(g,cc,start=1,rule=RULE,recovery=True)
    # Compare unchanged prefixes against an unmodified fixture.
    ff,ccc=flat();d=m.simulate(ff,ccc,start=1,rule=RULE,recovery=True)
    np.testing.assert_array_equal(d['nav'][:20],b['nav'][:20])


def test_complete_frozen_receipts():
    root=Path(__file__).resolve().parents[1]/'research/stop-review-20261027-v1'
    if not (root/'validation.json').exists():return
    v=json.loads((root/'validation.json').read_text());assert v['control_cases']==612 and v['asset_cases']==1836
    assert max(v[k] for k in ('max_control_error','max_close_engine_error','max_independent_ledger_error'))<1e-11
    rows=json.loads((root/'asset-results.json').read_text());assert len(rows)==1836
    charts=json.loads(gzip.decompress((root/'chart-data.json.gz').read_bytes()));assert len(charts)==102
    for c in charts.values():
        assert set(c['arms'])==set(m.ARMS)
        for a in c['arms'].values():
            assert all(len(a[k])==len(c['days']) for k in ('nav','stop','policy'))
            for e in a['trades']:
                if e['exit_index'] is not None:assert e['exit_index']>=e['entry_index']
