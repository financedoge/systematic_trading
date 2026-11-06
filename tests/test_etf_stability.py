import copy
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_etf_stability as study


def candidate(key,first=.08,second=.09,remaining=.03):
    return dict(id=key,metrics=dict(first=dict(sharpe=.8,cagr=first),second=dict(sharpe=.9,cagr=second),
        IS=dict(cagr=(first+second)/2,max_drawdown=.1,annual_turnover=8)),
        withheld=dict(cagr=remaining),stressed=dict(cagr=.02))


def test_cash_replacement_preserves_other_weights_and_original_targets():
    w=np.array([[.3,.2,.1],[.1,.4,.3]])
    before=w.copy()
    altered=study.withheld(w,['B','B'],['A','B','C'])
    np.testing.assert_array_equal(w,before)
    np.testing.assert_array_equal(altered[:,[0,2]],w[:,[0,2]])
    assert not altered[:,1].any()


def test_search_requires_return_floor_and_winner_stress_uses_no_later_metrics():
    rows=[candidate('cashlike',.01,.01),candidate('fragile',remaining=-.01),candidate('qualified')]
    base=dict(cagr=.06,max_drawdown=.1)
    winner,n=study.select(copy.deepcopy(rows),.03,base)
    assert (winner['id'],n)==('qualified',1)
    for row in rows:
        row['OOS']=dict(sharpe=999 if row['id']=='cashlike' else -999)
    assert study.select(rows,.03,base)[0]['id']=='qualified'
    assert not rows[0]['checks']['cagr_guard'] and not rows[1]['checks']['top_three_stress']


def test_empty_eligible_set_stays_unqualified():
    leader,count=study.select([candidate('loss',remaining=-.04)],.03,dict(cagr=.06,max_drawdown=.1))
    assert count==0 and not leader['eligible']
