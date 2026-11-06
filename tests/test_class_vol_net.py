import copy
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import research_class_vol_net as study


def entry(key,half,whole,withheld=.03):
    metric=dict(sharpe=whole,cagr=.08,max_drawdown=.12,annual_turnover=5)
    return dict(key=key,metrics={'calibration':metric,**{k:dict(metric,sharpe=half) for k in study.HALVES}},
                withheld_cagr=withheld,stressed_cagr=.02)


def test_training_selection_uses_matched_timing_and_weaker_half():
    rows=[entry('pooled_raw-monthly',.3,.4),entry('pooled_raw-0.40',.2,1.1),
          entry('class_raw-monthly',.5,.6),entry('pooled_risk-monthly',.3,1.0),
          entry('class_risk-0.40',.9,1.05)]
    winner,n=study.choose(copy.deepcopy(rows),.03)
    assert (winner['key'],n)==('class_raw-monthly',2)
    for r in rows:r['later']={'sharpe':1000 if r['key']=='class_risk-0.40' else -1000}
    assert study.choose(rows,.03)[0]['key']=='class_raw-monthly'


def test_cash_floor_and_winner_removal_do_not_silently_rescue_failure():
    rows=[entry('pooled_raw-monthly',.1,.1),entry('pooled_risk-monthly',.8,1.,withheld=-.01)]
    winner,n=study.choose(rows,.09)
    assert n==0 and not winner['eligible']
    assert not winner['checks']['return_floor'] and not winner['checks']['winner_stress']
