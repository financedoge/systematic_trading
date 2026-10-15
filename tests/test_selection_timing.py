import pytest

from systematic_trading.research.selection_timing import mixed_tape, select_pair
from systematic_trading.research.target_change_rebalance import adoption_schedule


def scores(sharpe=1.,turnover=2.):
    return {s:dict(sharpe=sharpe,cagr=.1,max_drawdown=-.1,annual_turnover=turnover)
        for s in ('5-0','10-0','5-1')}


def test_two_dimensional_neighbor_and_cost_tie_break():
    widths=['4','6','8'];thresholds=['.1','monthly']
    matrix={x+'/'+n:scores() for x in widths for n in thresholds}
    matrix['8/monthly']=scores(1.2,1)
    assert select_pair(widths,thresholds,matrix)['selected']=='6/monthly'
    matrix['8/.1']=scores(1.21,10)
    assert select_pair(widths,thresholds,matrix)['selected']=='8/monthly'
    matrix['8/monthly']['5-1']['sharpe']=1.
    assert select_pair(widths,thresholds,matrix)['selected']=='6/monthly'


def test_mixed_tape_and_adoption_carry_previous_width_anchor():
    days=['2023-12-29','2024-01-02','2024-01-03']
    known=['2023-12-28','2023-12-29','2024-01-02']
    tapes={x:{d:dict(signal_session=d,known_through=k,
        targets=[dict(symbol='SPY',target_weight=w)]) for d,k in zip(days,known,strict=True)}
        for x,w in [('6','.5'),('8','.7')]}
    mixed=mixed_tape(tapes,{'2024-01-02':'8/.1'})
    assert [r['selected_width'] for r in mixed.values()]==['6','8','8']
    decisions,ledger=adoption_schedule(mixed,['2024-01-02'],'monthly',switches={'2024-01-02':'.1'})
    assert list(decisions)==['2023-12-29','2024-01-02']
    assert ledger[1]['anchor_before']['SPY']=='0.5'
    assert ledger[1]['distance']=='0.4'
    assert ledger[-1]['distance']=='0.0'


def test_mixed_tape_rejects_missing_candidate_dates():
    with pytest.raises(ValueError,match='calendar'):
        mixed_tape({'6':{'a':{}},'8':{}},{})


def test_bad_selection_override_rejected_before_signal_computation(monkeypatch):
    from systematic_trading.research import usd_monitored as m
    from systematic_trading.research.strategy_catalog import defensive_cash_definition
    # Use real definition/overlay instantiation; input selection validation must
    # reject an impossible width before any model or price calculation.
    day='2024-01-02'
    monkeypatch.setattr(m,'_WORK',dict(days=['2023-12-29',day],typed={'SPY':[]},
        definitions=[defensive_cash_definition().to_dict()]))
    with pytest.raises(ValueError,match='selection-width'):
        m.targets_worker(day,selection_top_n=8)
