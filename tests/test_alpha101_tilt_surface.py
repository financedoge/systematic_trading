"""P4.17d — the tilt budget surface: plan, saturation and the frozen envelope."""
import json
from pathlib import Path

import pytest
from retained_artifacts import requires_artifact

from systematic_trading.research import alpha101_tilt_surface_study as study

ROOT = Path('var/research/alpha101-tilt-surface-20261011-v2')
BUILT = pytest.mark.skipif(not (ROOT / 'analysis.json').exists(), reason='frozen surface not built')


def test_the_arms_are_two_bases_and_the_declared_budget_grid():
    assert study.BASES['FR25']['source'] == 'research_fr25_14_v1'
    assert study.BASES['SOTA']['source'] == 'research_fallback_f3_v1'
    assert study.BUDGETS == (0.10, 0.20, 0.30, 0.50, 0.75, 1.00, 1.50)
    assert len(study.arms()) == 2 * (1 + len(study.BUDGETS))
    assert study.plan('FR25-TILT-150')['budget'] == 1.50
    assert study.plan('SOTA')['budget'] is None
    with pytest.raises(ValueError, match='Unregistered surface arm'):
        study.plan('FR25-TILT-999')


def test_the_protocol_declares_the_cost_deviation_and_refuses_to_name_an_optimum():
    protocol = study.protocol()
    deviations = ' '.join(protocol['deviations'])
    assert 'irrespective of cost' in deviations
    assert 'No optimal X is declared' in deviations
    assert protocol['bases']['FR25']['bars_root'] and protocol['bases']['SOTA']['bars_root']


@BUILT
@requires_artifact(ROOT / 'decisions')
def test_every_arm_is_frozen_and_replayed():
    assert len(study.arms()) == 16
    for arm in study.arms():
        assert (ROOT / 'decisions' / (arm + '.json')).exists(), arm
    for job in study.jobs():
        assert (ROOT / 'python' / (study.job_name(job) + '.json')).exists(), job


@BUILT
def test_the_effective_tilt_saturates_well_below_the_declared_budget():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    used = payload['realized']
    # declared budgets above ~100% buy almost no extra tilt: one shrink factor caps it
    assert used['FR25-TILT-100']['realized'] < 0.55
    assert used['FR25-TILT-150']['realized'] < 0.55
    assert used['FR25-TILT-150']['realized'] == pytest.approx(used['FR25-TILT-100']['realized'], abs=0.02)
    # and the cost of the two is the same to a tenth of a basis point
    gate = payload['gate']['arms']
    assert gate['FR25-TILT-150']['verdict']['annual_cost_bps'] == pytest.approx(
        gate['FR25-TILT-100']['verdict']['annual_cost_bps'], abs=0.1)


@BUILT
def test_higher_budgets_degrade_fr25_and_the_gate_flags_the_expensive_ones():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    metrics, gate = payload['metrics'], payload['gate']['arms']
    control = metrics['FR25']['total_return']
    for arm in ('FR25-TILT-30', 'FR25-TILT-50', 'FR25-TILT-75', 'FR25-TILT-150'):
        assert metrics[arm]['total_return'] < control
        assert metrics[arm]['sharpe_zero_cash'] < metrics['FR25']['sharpe_zero_cash']
    for budget, expected in ((0.10, 'pass'), (0.20, 'pass'), (0.30, 'reject'), (1.00, 'reject')):
        arm = f'FR25-TILT-{int(100 * budget)}'
        assert gate[arm]['verdict']['status'] == expected, arm
