import copy
import numpy as np
from systematic_trading.research.gld_confirmation import (
    candidates, candidate_id, neighbors, fit_variants, select_validation,
)
from systematic_trading.research.range_joint import History, v1_anchor
from systematic_trading.research.range_trace import trace
from test_range_trace import sample, rule


def test_grid_changes_only_confirmation_and_deadline():
    base=v1_anchor();grid=candidates(base)
    assert len(grid)==49
    for g in grid.values():
        p=np.array(g['parameters'])
        assert set(np.flatnonzero(p!=base)) <= {13,30}
    assert grid['c01_t000']['parameters'][30]==0
    assert grid['c08_t005']['parameters'][13]==8


def test_cross_close_confirmation_does_not_trade_until_next_open():
    p=rule();p[13]=1;p[30]=0
    a=sample();rows,episodes=trace(History.build(a),p)
    ep=next(e for e in episodes if e['crossing']==400)
    assert ep['confirmation']==400 and ep['virtual_entry']==401
    assert np.isnan(rows[400]['entry'])
    assert rows[401]['entry']==a['open'][401]
    assert rows[408]['active'] and not rows[408]['time_failed']
    assert not rows[408]['time_rule_enabled']


def test_disabling_time_exit_keeps_price_stop_and_prefix_causality():
    p=rule();p[13]=1;p[30]=0;a=sample()
    a['close'][415]=50;a['low'][415]=49
    full,_=trace(History.build(a),p)
    assert full[415]['exit_reason']==2
    cut,_=trace(History.build({k:v[:415] for k,v in a.items()}),p)
    np.testing.assert_allclose([r['stop'] for r in full[:415]], [r['stop'] for r in cut],equal_nan=True)


def test_neighbors_do_not_wrap_or_make_off_adjacent_to_five_days():
    assert set(neighbors(1,5))=={'c01_t005','c02_t005','c01_t010'}
    assert set(neighbors(8,0))=={'c08_t000','c06_t000','c08_t126'}


def test_validation_prioritizes_guards_and_near_tie_turnover():
    def row(score,guard,turn):
        return dict(score=score,guard_pass=guard,scenarios={'5:0':dict(metrics=dict(annual_turnover=turn))})
    grid=candidates(v1_anchor())
    rows={'c01_t000':row(9,False,0),'c02_t020':row(.50,True,3),'c03_t042':row(.48,True,2)}
    chosen=select_validation(rows,grid)
    assert chosen['selected']=='c03_t042' and chosen['guard_pass']
    rows['c03_t042']['score']=.46
    assert select_validation(rows,grid)['selected']=='c02_t020'
    for r in rows.values():r['guard_pass']=False
    chosen=select_validation(rows,grid)
    assert chosen['selected']=='c01_t000' and not chosen['guard_pass']


def test_IS_variants_use_supported_candidates_and_neighbor_penalty():
    rows=candidates(v1_anchor())
    for r in rows.values():
        r.update(scores={k:0. for k in ('raw','moderate','strong','stable')},evidence=True,
                 exact=dict(guard_pass=True))
    rows['c01_t005']['scores']={k:10. for k in ('raw','moderate','strong','stable')}
    result=fit_variants(rows)
    assert result['variants']['raw']=='c01_t005'
    assert result['variants']['neighbor']!='c01_t005'
    changed=copy.deepcopy(rows);changed['c01_t005']['evidence']=False
    assert fit_variants(changed)['variants']['raw']!='c01_t005'
