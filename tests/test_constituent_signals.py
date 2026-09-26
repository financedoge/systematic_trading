from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.contracts import BacktestRunSpec
from systematic_trading.research.constituent_signals import (
    WINDOW, ConstituentOverlaySpec, apply_constituent_targets, cohort_features, selected_score,
)


def data():
    a = np.column_stack((np.linspace(10, 20, WINDOW), np.linspace(20, 10, WINDOW), np.full(WINDOW, 12.)))
    return a, np.ones_like(a)*100, a.copy(), [0, 1, 2], [50, 30, 20], [True]*3


def test_missing_and_wrong_identity_keep_full_coverage_denominators():
    args = list(data())
    args[2][10, 1] = np.nan
    args[5][2] = False
    out = cohort_features(*args)
    assert out['value_coverage'] == .5
    assert out['name_coverage'] == pytest.approx(1/3)
    assert out['scores'] is None


def test_breadth_counts_and_volume_direction_are_not_fund_flows():
    out = cohort_features(*data())
    assert out['value_coverage'] == 1
    assert out['values']['breadth'] == pytest.approx(1/3)
    assert out['scores']['breadth'] == -1
    assert out['values']['hhi'] == pytest.approx((20**2+10**2+12**2)/(42**2))
    assert abs(out['scores']['composite']) <= 1


def feature():
    return {'45': {'2025-03-31': dict(known_through='2025-03-31', snapshot='2025-01-31',
        assumed_available='2025-03-17', value_coverage=.97, name_coverage=.8,
        scores={'composite': .6})}}


def test_asof_guard_neutral_coverage_and_future_invariance():
    spec = ConstituentOverlaySpec()
    rows = feature()
    assert selected_score(rows, date(2025, 4, 1), '2025-03-31', spec) == .6
    rows['45']['2026-01-01'] = {'malformed_future_data': True}
    assert selected_score(rows, date(2025, 4, 1), '2025-03-31', spec) == .6
    rows['45']['2025-03-31']['value_coverage'] = .94
    assert selected_score(rows, date(2025, 4, 1), '2025-03-31', spec) == 0
    assert selected_score({}, date(2025, 4, 1), '2025-03-31', spec) == 0
    rows['45']['2025-03-31']['assumed_available'] = '2025-04-01'
    with pytest.raises(ValueError, match='not available'):
        selected_score(rows, date(2025, 4, 1), '2025-03-31', spec)
    with pytest.raises(ValueError, match='future-dated'):
        selected_score(feature(), date(2025, 3, 31), '2025-03-31', spec)
    with pytest.raises(ValueError, match='stale'):
        selected_score(feature(), date(2025, 4, 10), '2025-03-31', spec)


def target(symbol, weight):
    return AllocationTarget(symbol=symbol, target_weight=Decimal(weight), rationale='fixture', sleeve='test')


@pytest.mark.parametrize('score', [-1., -.4, 0., .6, 1.])
def test_tilt_preserves_gross_and_bounds(score):
    targets = [target('SPY', '.30'), target('TLT', '.44'), target('GLD', '.24'), target('EWJ', '0')]
    result = apply_constituent_targets(targets, score, ConstituentOverlaySpec())
    weights = {t.symbol: t.target_weight for t in result}
    assert sum(weights.values()) == pytest.approx(Decimal('.98'))
    assert weights['EWJ'] == 0
    for original in targets:
        assert abs(weights[original.symbol]-original.target_weight) <= Decimal('.03')
        assert 0 <= weights[original.symbol] <= Decimal('.45')
    assert (weights['SPY']-Decimal('.30'))*Decimal(str(score)) >= 0


def test_overlay_cannot_create_spy_and_retains_inherited_caps():
    targets = [target('SPY', '0'), target('GLD', '.6'), target('TLT', '.38')]
    assert apply_constituent_targets(targets, 1, ConstituentOverlaySpec()) == targets
    targets = [target('SPY', '.50'), target('TLT', '.48')]
    assert apply_constituent_targets(targets, 1, ConstituentOverlaySpec())[0].target_weight == Decimal('.50')


def test_strategy_contract_rejects_unattached_overlay():
    values = dict(start_date='2025-01-02', end_date='2025-12-31', warmup_start='2023-01-01',
                  strategy_hash='fixture', source_hash='fixture', repository_commit='fixture')
    with pytest.raises(ValueError, match='requires a constituent'):
        BacktestRunSpec(**values, constituent_overlay=ConstituentOverlaySpec())
    with pytest.raises(ValueError, match='requires a constituent'):
        BacktestRunSpec(**values, strategy='sota_constituents')
    with pytest.raises(ValueError):
        ConstituentOverlaySpec(relative_tilt=float('nan'))
