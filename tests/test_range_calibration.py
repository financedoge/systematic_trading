import importlib.util
from pathlib import Path
import sys

import numpy as np

from systematic_trading.research.range_calibration import (
    RangeRule, ExitRule, CalibratedRule, candidate_grid, signal_grid,
    fractional_screen, robust_score, select_fitted, transitions,
)


def example():
    t = np.arange(1500)
    c = 100+np.sin(t/6)
    c[1300:1380] = np.linspace(105,180,80)
    c[1380:] = np.linspace(160,80,120)
    o = np.r_[c[0],c[:-1]]
    v = np.ones(len(c))*1000
    v[1300:1380] = 3000
    return c,o,np.maximum(c,o)+.5,np.minimum(c,o)-.5,v


def rule(initial=4,trail=8,buffer=None):
    return CalibratedRule(RangeRule('absolute',.25,.65),ExitRule(initial,'atr',trail,buffer),True)


def test_grid_is_frozen_and_unique():
    grid=candidate_grid()
    assert len(grid)==1080
    assert len(set(grid))==1080


def test_vectorized_rules_equal_individual_rules():
    a=example();specs=[rule(),rule(2,4,.5),candidate_grid()[-1]]
    full=signal_grid(*a,specs,details=True)
    for j,s in enumerate(specs):
        single=signal_grid(*a,[s],details=True)
        for k in full:
            np.testing.assert_array_equal(full[k][:,j],single[k][:,0])


def test_prefix_and_future_open_causality_including_relative_ranges():
    a=example();specs=[rule(),candidate_grid()[-1]]
    full=signal_grid(*a,specs,details=True)
    n=1303
    prefix=signal_grid(*(x[:n] for x in a),specs,details=True)
    for k in full:
        np.testing.assert_array_equal(full[k][:n],prefix[k])
    changed=[x.copy() for x in a];changed[1][n:]*=1.5
    later=signal_grid(*changed,specs)
    np.testing.assert_array_equal(later['active'][:n],full['active'][:n])
    assert full['active'][1302,0]
    assert not full['active'][1301,0]
    assert np.isnan(full['stop'][1302,0])


def test_stop_ratchet_and_wider_stops_retain_more_of_a_single_rally():
    a=example()
    r=signal_grid(*a,[rule(2,4,.5),rule(8,12)],details=True)
    exits=[]
    for j in range(2):
        ix=np.flatnonzero(np.isfinite(r['stop'][:,j]))
        assert np.all(np.diff(r['stop'][ix,j]) >= 0)
        exits.append(np.flatnonzero(r['exit_reason'][:,j])[0])
    assert exits[1] >= exits[0]
    # Gap on the execution day changes realised cash, not the prior exit signal.
    changed=[x.copy() for x in a];changed[1][exits[1]+1]=50
    q=signal_grid(*changed,[rule(8,12)])
    np.testing.assert_array_equal(q['active'][:exits[1]+1,0],r['active'][:exits[1]+1,1])


def test_fractional_screen_holds_units_instead_of_daily_constant_weight():
    c=np.array([100,100,120,80,80.]);o=np.array([100,100,110,90,70.])
    active=np.array([True,True,True,False,False])[:,None]
    nav,trades,_=fractional_screen(c,o,active,1,cost=0)
    np.testing.assert_allclose(nav[:,0],[1,1.196,.804,.706])
    assert trades[0]==1


def test_selector_uses_evidence_and_guards_before_best_score():
    rows=[dict(id='a',score=10,evidence=False,guard_pass=True,annual_turnover=1),
          dict(id='b',score=9,evidence=True,guard_pass=False,annual_turnover=1),
          dict(id='c',score=1,evidence=True,guard_pass=True,annual_turnover=2),
          dict(id='d',score=.98,evidence=True,guard_pass=True,annual_turnover=1)]
    assert select_fitted(rows)['id']=='d'
    assert select_fitted([rows[0]]) is None


def test_dynamic_and_monthly_adoption_are_distinct():
    days=np.array(['2022-12-29','2022-12-30','2023-01-03','2023-01-04','2023-01-05'])
    a=np.array([False,True,True,False,False])
    assert transitions(a,days,'2023-01-01')==[1,3]
    assert transitions(a,days,'2023-01-01','monthly')==[1]


def test_fit_loader_physically_removes_oos_observations(tmp_path):
    sys.path.insert(0,str(Path('scripts').resolve()))
    spec=importlib.util.spec_from_file_location('calibration',Path('scripts/calibrate_range_breakout.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    (tmp_path/'assets').mkdir()
    np.savez(tmp_path/'assets'/'TEST.npz',days=np.array(['2022-12-30','2023-01-03']),close=np.array([1,9999]))
    a=mod.load_asset(tmp_path,'TEST',fit=True)
    assert a['close'].tolist()==[1]


def test_historical_calendar_closures_and_pre_mlk_sessions():
    import exchange_calendars as xc
    cal=xc.get_calendar('XNYS',start='1993-01-01',end='2026-12-31')
    assert not any(cal.is_session(d) for d in ('2001-09-11','2004-06-11','2007-01-02'))
    assert cal.is_session('1997-01-20')


def test_block_scores_do_not_reset_nav_at_each_block():
    a=np.array([1.1,1.2,1.1,1.15,1.2,1.3])
    score,blocks=robust_score(a)
    assert np.isfinite(score).all() and blocks.shape==(3,1)
