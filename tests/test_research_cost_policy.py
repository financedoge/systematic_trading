"""Current cost policy cannot silently inherit the historical absolute cutoff."""
import json

import pytest

from systematic_trading.research import turnover_gate as gate


@pytest.mark.parametrize('cost', [40, 44, 45.65769789755, 108.46, 600, 2020])
def test_cost_does_not_veto_a_net_replay(cost):
    result = gate.screen(cost / 5, sigma=.05, candidate_ic=.026)
    assert result['annual_cost_bps'] == pytest.approx(cost)
    assert result['cost_test'] is None and result['cost_ceiling_bps'] is None
    assert result['status'] == 'requires_replay'
    assert not result['net_performance_established']
    assert not result['promotion_eligible']
    json.dumps(result, allow_nan=False)


def test_weak_information_stays_visible_without_becoming_a_portfolio_verdict():
    result = gate.screen(40, sigma=.05, candidate_ic=-.02)
    assert result['margin_test'] is False
    assert result['ic_margin'] < 0
    assert result['status'] == 'requires_replay'


@pytest.mark.parametrize('ic,sigma', [(None, .05), (.02, None), (None, None)])
def test_missing_evidence_is_not_replaced_with_another_signals_ic(ic, sigma):
    result = gate.screen(8, sigma=sigma, candidate_ic=ic)
    assert result['status'] == 'insufficient'
    assert result['candidate_ic'] == ic
    assert result['margin_test'] is None


@pytest.mark.parametrize('cost,turnover', [(0, 10), (5, 0)])
def test_zero_cost_still_requires_performance_evidence(cost, turnover):
    result = gate.screen(turnover, sigma=.05, candidate_ic=.02, cost_bps=cost)
    assert result['annual_cost_bps'] == 0
    assert result['status'] == 'requires_replay'
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('kwargs', [dict(annual_turnover=-1), dict(cost_bps=float('nan')),
    dict(candidate_ic=float('nan')), dict(candidate_ic=1.1), dict(sigma=float('inf')),
    dict(sigma=0), dict(period_sessions=0), dict(thresholds=gate.LEGACY_THRESHOLDS)])
def test_invalid_inputs_and_retired_ceiling_configuration_fail_explicitly(kwargs):
    with pytest.raises(ValueError):
        gate.screen(**(dict(annual_turnover=10, sigma=.05, candidate_ic=.02) | kwargs))


def test_legacy_reproduction_is_explicit_and_does_not_change_current_policy():
    old = gate.legacy_screen(9.13153957951, sigma=.05, candidate_ic=.1)
    new = gate.screen(9.13153957951, sigma=.05, candidate_ic=.1)
    assert old['version'] == 'turnover-gate-v1'
    assert old['status'] == 'reject' and old['cost_test'] is False
    assert old['margin_test'] is True
    assert new['version'] == 'turnover-diagnostics-v2'
    assert new['status'] == 'requires_replay'
    assert 'max_annual_cost_bps' not in gate.THRESHOLDS
