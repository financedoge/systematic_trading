from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from systematic_trading.domain.market import PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext, apply_target_overlays
from systematic_trading.signals.trend import AssetPoolFilterOverlay
from systematic_trading.research.fallback_protocol import definition
from systematic_trading.research.strategy_catalog import instantiate_overlays, StrategyDefinition, strategy_model_card


SYMBOLS = ['SPY','VGK','IEF','TLT','GLD','DBC']


def fixture(eligible):
    bars = {s:[PriceBar(trade_date=date(2024,1,1)+timedelta(days=i),
        open=D(100)+i*(1 if s in eligible else -1), high=D(100)+i*(1 if s in eligible else -1),
        low=D(100)+i*(1 if s in eligible else -1), close=D(100)+i*(1 if s in eligible else -1), volume=100+i)
        for i in range(8)] for s in SYMBOLS}
    return ([AllocationTarget(symbol=s,sleeve='test',target_weight=D('.15'),rationale='base') for s in SYMBOLS],
        SignalContext(date(2024,1,10),{},bars,[]))


def pool(policy):
    return AssetPoolFilterOverlay(short_momentum_bars=2,medium_momentum_bars=3,long_momentum_bars=4,
        volume_bars=2,slow_volume_bars=4,min_selected=4,fallback_policy=policy)


@pytest.mark.parametrize('eligible',[[],['SPY'],['SPY','IEF'],['SPY','IEF','GLD']])
@pytest.mark.parametrize('policy',['eligible_cash','all_cash','defensive_cash'])
def test_valid_weak_breadth_retains_only_original_allowed_weights(eligible,policy):
    targets,context=fixture(eligible)
    result=apply_target_overlays(targets,[pool(policy)],context)
    kept=set(eligible) if policy=='eligible_cash' else set(eligible)&{'IEF','TLT','GLD'} if policy=='defensive_cash' else set()
    assert {t.symbol for t in result if t.target_weight>0}==kept
    assert all(t.target_weight==(D('.15') if t.symbol in kept else 0) for t in result)


@pytest.mark.parametrize('policy',['eligible_cash','all_cash','defensive_cash'])
def test_four_qualifiers_preserve_parent_and_reentry_resets_constraint(policy):
    overlay=pool(policy)
    targets,weak=fixture(['IEF'])
    overlay.apply(targets,weak)
    _,strong=fixture(SYMBOLS[:4])
    assert overlay.apply(targets,strong)==pool('neutral').apply(targets,strong)
    assert overlay.cash_budget_active is False


def test_missing_features_or_short_universe_stop_without_cash_instruction():
    targets,context=fixture(['IEF'])
    context=SignalContext(context.as_of,{},dict(context.bars_by_symbol, SPY=[]),[])
    with pytest.raises(ValueError,match='features'):
        pool('eligible_cash').apply(targets,context)
    with pytest.raises(ValueError,match='universe'):
        pool('all_cash').apply(targets[:1],context)


def test_downstream_cannot_resurrect_rejected_names_or_refill_released_cash():
    targets,context=fixture(['IEF'])
    reduce=SimpleNamespace(apply=lambda ts,c:[t.model_copy(update={'target_weight':t.target_weight/2}) for t in ts])
    refill=SimpleNamespace(apply=lambda ts,c:[t.model_copy(update={'target_weight':D('.2')}) for t in ts])
    out=apply_target_overlays(targets,[pool('eligible_cash'),reduce,refill],context)
    assert sum(t.target_weight for t in out)==D('.075')
    assert [t.symbol for t in out if t.target_weight>0]==['IEF']
    out=apply_target_overlays(targets,[pool('all_cash'),refill],context)
    assert all(t.target_weight==0 for t in out)


def test_versioned_definition_round_trip_and_model_card():
    for recipe in ['F0','F1','F2','F3']:
        d=definition(recipe)
        assert StrategyDefinition.from_dict(d.to_dict())==d
        assert instantiate_overlays(d)[0].fallback_policy==dict(F0='neutral',F1='eligible_cash',F2='all_cash',F3='defensive_cash')[recipe]
        if recipe!='F0':
            assert 'Stop calculation' in strategy_model_card(d)['decisionTree']


def test_old_neutral_weak_branch_unchanged():
    targets,context=fixture([])
    out=pool('neutral').apply(targets,context)
    assert [t.target_weight for t in out]==[t.target_weight for t in targets]


def test_cash_only_path_has_no_infinite_sharpe():
    from systematic_trading.research.momentum_analysis import statistics
    days=['2024-01-02','2024-01-03','2024-01-04']
    economic=dict(nav=[dict(date=d,nav='1000000',cash='1000000') for d in days],fills=[])
    quotes={'SPY':{d:dict(open='100',close='100',reference='100') for d in days}}
    stats=statistics(economic,quotes)
    assert stats['sharpe_zero_cash'] is None
    assert stats['cagr']==stats['max_drawdown']==0
    assert stats['mean_cash_weight']==1
