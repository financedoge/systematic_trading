import copy
import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from systematic_trading.domain.market import PriceBar
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.lean.contracts import BacktestRunSpec
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.research.flow_concentration import (
    FlowConcentrationSpec, finite_difference, concentration_features,
    apply_concentration_targets, hurst_estimate,
)
from systematic_trading.live.trading_calendar import is_us_trading_day


def histories():
    result = {s: [] for s in instruments_for_definition(current_sota_definition())}
    for i in range(600):
        day = date(2023, 1, 3) + timedelta(days=i)
        if not is_us_trading_day(day):
            continue
        for j, rows in enumerate(result.values()):
            value = 100 + .02*i + math.sin(i/9+j)
            rows.append(dict(trade_date=str(day), open=str(value), high=str(value+1),
                             low=str(value-1), close=str(value), volume=100000+int(10000*math.sin(i/6+j))))
    return result


def test_acceleration_distinguishes_slowdown_from_negative_velocity():
    assert finite_difference([float(i*i) for i in range(100)], 10, 2) == 2
    slowing = [float(300*i-i*i) for i in range(100)]
    assert finite_difference(slowing, 10, 1) > 0
    assert finite_difference(slowing, 10, 2) == -2
    assert finite_difference([float(i) for i in range(100)], 10, 2) == 0


def test_neutral_activity_has_no_false_acceleration():
    rows = histories()
    bars = {s: [PriceBar.model_validate(dict(r, close='100', open='100', high='100', low='100', volume=1000*(j+1)))
                for r in v] for j, (s, v) in enumerate(rows.items())}
    features = concentration_features(bars, FlowConcentrationSpec())
    assert all(abs(v['share'] - 1/12) < 1e-12 and v['signal'] == 0 for v in features.values())
    assert hurst_estimate([1.0]*252) is None


@pytest.mark.parametrize('config', [FlowConcentrationSpec(), FlowConcentrationSpec(hurst_min=.55),
                                  FlowConcentrationSpec(action='gate')])
def test_future_prices_and_volumes_cannot_change_targets(config):
    rows = histories()
    decision = date(2024, 5, 1)
    before = targets_for_day(rows, decision, flow_overlay=config, flow_state={})
    changed = copy.deepcopy(rows)
    for values in changed.values():
        for r in values:
            if r['trade_date'] >= str(decision):
                r.update(close='99999', high='99999', open='99999', low='99999', volume=999999999)
    after = targets_for_day(changed, decision, flow_overlay=config, flow_state={})
    assert before == after


def test_feature_rejects_missing_observation_instead_of_silent_alignment():
    bars = {s: [PriceBar.model_validate(r) for r in v] for s, v in histories().items()}
    bars['SPY'].pop(-20)
    with pytest.raises(ValueError, match='identical sessions'):
        concentration_features(bars, FlowConcentrationSpec())


def test_relative_activity_invariant_to_constant_per_asset_unit_scaling():
    bars = {s: [PriceBar.model_validate(r) for r in v] for s, v in histories().items()}
    before = concentration_features(bars, FlowConcentrationSpec())
    changed = dict(bars)
    changed['SPY'] = [r.model_copy(update={'volume': r.volume*100}) for r in bars['SPY']]
    after = concentration_features(changed, FlowConcentrationSpec())
    for symbol in before:
        assert after[symbol]['share'] == pytest.approx(before[symbol]['share'], abs=1e-12)
        assert after[symbol]['z'] == pytest.approx(before[symbol]['z'], abs=1e-10)
        assert after[symbol]['signal'] == before[symbol]['signal']


def test_tilt_preserves_gross_caps_and_selected_pool():
    base = [AllocationTarget(symbol=s, target_weight=Decimal(w), sleeve='sota', rationale='')
            for s, w in [('A', '.44'), ('B', '.3'), ('C', '.24'), ('D', '0')]]
    features = {s: {'signal': sig} for s, sig in [('A', 1), ('B', -1), ('C', 0), ('D', 1)]}
    result = apply_concentration_targets(base, features, FlowConcentrationSpec())
    assert abs(sum(t.target_weight for t in result)-Decimal('.98')) < Decimal('1e-24')
    assert result[-1].target_weight == 0
    for old, new in zip(base, result):
        assert 0 <= new.target_weight <= Decimal('.45')
        assert abs(old.target_weight-new.target_weight) <= Decimal('.03')


def test_gate_has_hysteresis_and_sells_to_cash():
    base = [AllocationTarget(symbol='A', target_weight=Decimal('.4'), sleeve='sota', rationale='')]
    spec, state = FlowConcentrationSpec(action='gate'), {}
    observed = []
    for signal in (0, 1, 0, -1, 0, 1):
        observed.append(apply_concentration_targets(base, {'A': {'signal': signal}}, spec, state)[0].target_weight)
    assert observed == [0, Decimal('.4'), Decimal('.4'), 0, 0, Decimal('.4')]


def test_flow_spec_requires_an_explicit_challenger_identity():
    kwargs = dict(start_date='2025-01-02', end_date='2025-12-31', warmup_start='2023-01-01',
                  strategy_hash='test', source_hash='test', repository_commit='test')
    with pytest.raises(ValueError, match='sota_flow requires'):
        BacktestRunSpec(**kwargs, flow_overlay=FlowConcentrationSpec())
    assert BacktestRunSpec(**kwargs, strategy='sota_flow', flow_overlay=FlowConcentrationSpec()).promotion_eligible is False
