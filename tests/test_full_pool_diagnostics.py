import numpy as np
import pytest

from systematic_trading.research.full_pool_diagnostics import (
    rank_ic, partial_rank_ic, steering, monthly_contributions,
    multiplier, drawdown_episode, ic_inference, ARMS, interval_contributions,
)


def test_good_total_forecast_rank_does_not_imply_good_increment_rank():
    means = np.array([.01,.02,.03,.04])
    increments = np.array([.004,.003,.002,.001])
    actual = means.copy()
    assert rank_ic(means+increments,actual)==1
    assert rank_ic(increments,actual)==-1
    assert partial_rank_ic(means+increments,actual,[means]) is None


def test_ties_are_averaged_and_small_or_constant_samples_are_missing():
    assert rank_ic([1,1,2,3],[1,1,2,3])==1
    assert rank_ic([1,1,1],[1,2,3]) is None
    assert rank_ic([1,2],[1,2]) is None


def test_equal_budget_active_weights_reconcile_and_reject_cash_change():
    result = steering([.4,.4,0],[.42,.38,0],[.1,-.1,10])
    assert result['gross_return_delta']==pytest.approx(.004)
    assert sum(result['asset_contributions'])==pytest.approx(.004)
    assert result['active_share']==pytest.approx(.02)
    with pytest.raises(ValueError,match='Cash budget'):
        steering([.4,.4],[.42,.4],[.1,-.1])


def test_monthly_attribution_links_net_contributions_and_resets_each_month():
    stats = dict(dates=['2021-01-04','2021-01-05','2021-02-01'],
        daily_returns=[.1,-.1,.2],monthly={'2021-01':-.01,'2021-02':.2},
        asset_daily_contribution={'A':[.07,-.08,.12],'B':[.03,-.02,.08]})
    result = monthly_contributions(stats)
    assert result['2021-01']['A']==pytest.approx(-.018)
    assert sum(result['2021-01'].values())==pytest.approx(-.01)
    assert result['2021-02']['A']==pytest.approx(.12)
    stats['monthly']['2021-01']=0
    with pytest.raises(ValueError,match='reconciliation'):
        monthly_contributions(stats)


def test_threshold_and_positive_forecast_gate_match_frozen_rule():
    assert multiplier(.003,.01)==1.1
    assert multiplier(.003,-.01)==1
    assert multiplier(.0025,.01)==1
    assert multiplier(-.0025,.01)==1
    assert multiplier(-.003,.01)==.9


def test_drawdown_uses_own_peak_trough_and_recovery():
    e = dict(nav=[dict(date=d,nav=n) for d,n in [('a',1100000),('b',900000),('c',1050000),('d',1200000)]])
    result = drawdown_episode(e)
    assert (result['peak'],result['trough'],result['recovery'])==('a','b','d')
    assert result['drawdown']==pytest.approx(900000/1100000-1)


def test_interval_attribution_excludes_peak_day_return():
    stats = dict(dates=['a','b','c','d'],daily_returns=[.1,-.1,-.05,.3],
        asset_daily_contribution={'A':[.1,-.04,-.02,.1],'B':[0,-.06,-.03,.2]})
    result = interval_contributions(stats,'a','c')
    assert result['A']==pytest.approx(-.058)
    assert sum(result.values())==pytest.approx(.9*.95-1)


def test_ic_bootstrap_keeps_missing_calendar_months_and_does_not_annualize():
    days = [f'2021-{i:02}' for i in range(1,13)]+[f'2022-{i:02}' for i in range(1,13)]
    rows = [dict(arm=arm,decision=day,total_ic=.12,mean_ic=.02,increment_ic=.1,total_minus_mean_ic=.1)
            for arm in ARMS for day in days[:18]]
    output = ic_inference(rows,days,200,7)
    for values in output.values():
        assert values['CR/total_ic']['n']==18
        assert values['CR/total_ic']['mean']==pytest.approx(.12)
        assert values['CR/total_ic']['ci95']==pytest.approx([.12,.12])
        assert values['CR/total_ic']['holm_p'] is None
        assert values['CR/increment_ic']['holm_p'] is not None
