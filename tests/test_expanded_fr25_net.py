"""Expanded study preserves the matched ablation and training-only selection."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_expanded_fr25_net as s


def test_only_selection_boundary_changes_in_matched_m1():
    original=s.fr25_definition()
    defs=s.definitions([dict(symbol='TEST')])
    assert defs['original']==original
    assert defs['expanded'].overlays==original.overlays
    assert defs['m1'].overlays[1:]==defs['expanded'].overlays[1:]
    assert defs['m1'].overlays[0]==s.m1_14_definition().overlays[0]
    assert defs['m1'].universe_members==defs['expanded'].universe_members
    assert defs['m1'].overlays[-1].kind=='final_weight_cap'


def test_selection_ignores_later_results_and_stress_winners():
    rows=[]
    for arm in (*s.MAIN,'momentum','unranked'):
        for p in s.POLICIES:
            for cost in (5,20):
                rows.append(dict(arm=arm+'-'+p,cost_bp=cost,delay=0,windows={
                    'calibration':dict(sharpe=2 if p=='0.40' and cost==5 else 99 if cost==20 else 1,
                        cagr=.1,max_drawdown=.1),
                    'later':dict(sharpe=100 if p=='monthly' else -100)}))
    assert s.select(rows)['selected']=='expanded-0.40'
    assert not any(s.select(rows)['guards'].values())
