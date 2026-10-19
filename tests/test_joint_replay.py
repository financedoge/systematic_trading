import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
spec=importlib.util.spec_from_file_location('joint_runner_test',Path(__file__).resolve().parents[1]/'scripts/run_joint_breakout.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_history_loader_physically_excludes_validation_and_oos(tmp_path,monkeypatch):
    (tmp_path/'assets').mkdir()
    days=np.array(['2022-12-30','2023-01-03','2024-01-02'])
    np.savez_compressed(tmp_path/'assets/TEST.npz',days=days,close=np.array([1.,2.,999.]))
    monkeypatch.setattr(runner,'PARENT',tmp_path)
    a=runner.asset('TEST','2022-12-31')
    np.testing.assert_array_equal(a['days'],days[:1])
    np.testing.assert_array_equal(a['close'],[1.])
    b=runner.asset('TEST','2023-12-31')
    assert b['close'].tolist()==[1.,2.]


def test_execution_clock_preserves_later_open_and_delayed_exits():
    days=np.array(['2023-12-29','2024-01-02','2024-01-03','2024-01-04','2024-01-05','2024-01-08'])
    signal=np.array([False,True,True,False,False,False])
    ids,closed=runner.adopt_state(signal,days,'2024-01-01','event',1)
    assert ids==[0,1,3]
    assert np.flatnonzero(closed).tolist()==[5]


def test_exact_metric_blocks_use_previous_nav_not_fresh_account():
    days=pd.bdate_range('2020-01-01',periods=10).strftime('%Y-%m-%d').to_numpy()
    nav=np.array([110.,99.,120.,130.,110.,140.,100.,110.,120.])*10000
    path=dict(nav=nav,exposure=np.ones(9)*.98)
    a=dict(days=days,close=np.arange(100.,110.))
    st=runner.stats_exact(path,a,str(days[1]),np.zeros(9,bool))
    assert abs(st[0,3]-(100/140-1))<1e-12
    assert abs(st[1,3]-(99/110-1))<1e-12
    # Second block starts from120, not initial100 or first block130.
    assert abs(st[2,0]-((140/120)**84-1))<1e-6


def test_screen_and_exact_whole_share_metrics_are_close():
    n=300;days=pd.bdate_range('2021-01-01',periods=n).strftime('%Y-%m-%d').to_numpy()
    c=100+np.arange(n)*.1+np.sin(np.arange(n))
    a=dict(days=days,close=c,open=np.r_[c[0],c[:-1]],high=c+2,low=c-2,volume=np.ones(n)*1000)
    signal=np.zeros(n,bool);signal[200:230]=True;signal[240:280]=True
    r=runner.SingleReplay(a,'TEST',str(days[200]))
    indices,closed=runner.adopt_state(signal,days,str(days[200]),'event',0)
    path,_,_=r.run(.98*signal[:,None],indices,5,0)
    exact=runner.stats_exact(path,a,str(days[200]),closed[200:])
    screen=runner.screen_stats(c,a['open'],signal,200,n)
    np.testing.assert_allclose(exact[:,0],screen[:,0],atol=.001)
    np.testing.assert_allclose(exact[:,3],screen[:,3],atol=.001)
    np.testing.assert_array_equal(exact[:,6],screen[:,6])

