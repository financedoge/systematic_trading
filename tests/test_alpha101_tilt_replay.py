"""P4.17c — the Alpha101 tilt replayed on the current SOTA: rule, contracts and the frozen result."""
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from systematic_trading.research import alpha101_tilt_study as study
from systematic_trading.research.alpha101_tilt_replay_analysis import (at, contrast, load_all, metrics_from,
                                                                      uncertainty)

ROOT = Path('var/research/alpha101-tilt-replay-20261011-v1')
BUILT = pytest.mark.skipif(not (ROOT / 'analysis.json').exists(), reason='frozen tilt replay not built')


def targets(**weights):
    from systematic_trading.domain.portfolio import AllocationTarget
    return [AllocationTarget(symbol=symbol, target_weight=D(str(weight)), sleeve='pooled', rationale='base')
            for symbol, weight in weights.items()]


# --- the arm definitions -----------------------------------------------------

def test_the_arms_are_the_control_and_two_declared_tilts():
    assert study.ARMS == ('SOTA', 'SOTA-TILT-53', 'SOTA-TILT-FAMILY')
    assert study.SOTA_KEY == 'research_fallback_f3_v1'
    assert study.plan('SOTA-TILT-53')['alphas'] == ['53']
    assert study.plan('SOTA-TILT-FAMILY')['alphas'] == list(study.lib.REGISTERED)
    assert study.plan('SOTA')['budget'] is None
    assert study.BUDGET == D('0.10')
    with pytest.raises(ValueError, match='Unregistered tilt arm'):
        study.plan('SOTA-TILT-99')


def test_the_family_arm_selects_nothing_and_the_single_arm_declares_its_selection():
    protocol = study.protocol()
    assert 'chosen after inspecting the P4.17 screen' in protocol['selection_disclosure']
    assert len(protocol['arms']['SOTA-TILT-FAMILY']['alphas']) == 16
    assert len(protocol['arms']['SOTA-TILT-53']['alphas']) == 1
    assert protocol['initial_cash_usd'] == 1_000_000
    assert protocol['costs'] == [5, 10, 20] and protocol['delays'] == [0, 1]


# --- the tilt rule -----------------------------------------------------------

def test_rank_scores_refuse_a_book_that_cannot_be_ranked():
    assert study.rank_scores(['a'], {'a': 1.0}) is None
    assert study.rank_scores(['a', 'b'], {'a': 1.0, 'b': 1.0}) is None      # no spread
    assert study.rank_scores(['a', 'b'], {'a': 1.0, 'b': 0.0}) == {'a': 1.0, 'b': -1.0}


def test_the_tilt_is_nav_neutral_and_bounded_by_the_cap():
    base = targets(a=0.40, b=0.30, c=0.20, d=0.08)
    scores = {'a': 3.0, 'b': 1.0, 'c': -1.0, 'd': -3.0}
    adjusted, diagnostic = study.tilt_targets(base, scores, D('0.10'))
    weights = {t.symbol: t.target_weight for t in adjusted}
    before = {t.symbol: t.target_weight for t in base}
    assert diagnostic['applied'] and diagnostic['names'] == 4
    assert sum(weights.values()) == sum(before.values())            # gross untouched
    assert weights['a'] > before['a'] and weights['d'] < before['d']
    assert all(D('0') <= w <= study.MAX_WEIGHT for w in weights.values())


def test_a_book_already_above_the_cap_is_never_tilted_further_up():
    """The final clamp runs after this overlay, so a name can arrive above the 45% cap."""
    base = targets(a=0.52, b=0.30, c=0.16)
    scores = {'a': 1.0, 'b': 0.0, 'c': -1.0}
    adjusted, diagnostic = study.tilt_targets(base, scores, D('0.10'))
    weights = {t.symbol: t.target_weight for t in adjusted}
    assert weights['a'] <= D('0.52')                                # never worse
    assert diagnostic['over_cap_names'] == 1
    assert diagnostic['scale'] == 0.0 and diagnostic['applied'] is False
    assert weights == {t.symbol: t.target_weight for t in base}     # shrunk to a no-op


def test_the_zero_floor_shrinks_the_whole_tilt():
    base = targets(a=0.40, b=0.40, c=0.05)
    scores = {'a': 2.0, 'b': 0.0, 'c': -2.0}
    adjusted, diagnostic = study.tilt_targets(base, scores, D('0.20'))
    weights = {t.symbol: t.target_weight for t in adjusted}
    assert min(weights.values()) >= 0
    assert diagnostic['scale'] < 1.0
    assert sum(weights.values()) == sum(t.target_weight for t in base)


def test_an_untiltable_book_is_returned_unchanged():
    base = targets(a=0.5, b=0.4)
    for scores in ({}, {'a': 1.0}, {'a': 1.0, 'b': 1.0}):
        adjusted, diagnostic = study.tilt_targets(base, scores, D('0.10'))
        assert adjusted == base and diagnostic['applied'] is False


def test_the_overlay_keeps_the_symbol_set_the_fallback_protects():
    overlay = study.AlphaTiltOverlay(alphas=('53',), budget=study.BUDGET,
                                     values_by_alpha={'53': {'a': 3.0, 'b': 1.0, 'c': 0.0}})
    base = targets(a=0.40, b=0.30, c=0.10, cash_like=0.0)
    adjusted = overlay.apply(base, None)
    assert {t.symbol for t in adjusted} == {t.symbol for t in base}
    assert overlay.cash_budget_active is False
    weights = {t.symbol: t.target_weight for t in adjusted}
    assert weights['cash_like'] == 0
    assert abs(sum(weights.values()) - sum(t.target_weight for t in base)) < D('1e-12')


def test_the_composite_averages_rank_scores_rather_than_values():
    held = ['a', 'b', 'c']
    per_alpha = {'1': {'a': 100.0, 'b': 0.0, 'c': -100.0},      # different scales
                 '2': {'a': 0.03, 'b': 0.02, 'c': 0.01}}
    scores, used = study.composite_scores(held, per_alpha)
    assert used == 2
    assert scores['a'] > scores['b'] > scores['c']
    assert sum(scores.values()) == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(AssertionError):
        assert sum(scores.values()) == pytest.approx(300.0)


# --- the frozen replay -------------------------------------------------------

@BUILT
def test_every_registered_job_was_replayed_once():
    jobs = study.jobs()
    assert len(jobs) == 3 * 3 * 2 * 2 == 36
    for job in jobs:
        name = study.job_name(job)
        assert (ROOT / 'python' / (name + '.json')).exists(), name
        assert (ROOT / 'python' / (name + '.receipt.json')).exists(), name


@BUILT
def test_the_gate_passed_every_arm_before_the_replays():
    gate = json.loads((ROOT / 'gate.json').read_text(encoding='utf8'))
    assert {arm: row['verdict']['status'] for arm, row in gate['arms'].items()} == {
        arm: 'pass' for arm in study.ARMS}
    assert gate['arms']['SOTA']['incremental_cost_bps'] == 0.0
    for arm in ('SOTA-TILT-53', 'SOTA-TILT-FAMILY'):
        assert 0 < gate['arms'][arm]['incremental_cost_bps'] < 3.0
        assert gate['arms'][arm]['verdict']['annual_cost_bps'] < gate['ceiling_bps']


@BUILT
def test_the_frozen_result_is_inconclusive_and_directionally_better():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    metrics = payload['metrics']
    assert payload['verdict']['status'] == 'inconclusive'
    for arm in ('SOTA-TILT-53', 'SOTA-TILT-FAMILY'):
        assert metrics[arm]['total_return'] > metrics['SOTA']['total_return']
        assert metrics[arm]['calmar'] > metrics['SOTA']['calmar']
        assert metrics[arm]['max_drawdown'] > metrics['SOTA']['max_drawdown']   # less negative
    primary = payload['primary_contrast']
    assert primary['holm_p'] >= 0.05
    assert primary['ci95'][0] < 0 < primary['ci95'][1]


@BUILT
def test_the_analysis_reproduces_from_the_replays():
    results = load_all(ROOT)
    assert len(results) == 36
    headline = at(results, 'SOTA')
    assert headline['sessions'] > 1000
    assert headline['max_drawdown'] < 0 < headline['total_return']
    boot = uncertainty(results)
    for block in ('3', '6', '12'):
        assert all(row['holm_p'] >= 0.0 for row in boot[block])
    assert contrast(boot, ('SOTA-TILT-FAMILY', 'SOTA'))['mean_annual'] > 0
    manual = metrics_from([dict(date='2026-01-01', nav=100.0), dict(date='2026-01-02', nav=101.0)])
    assert manual['total_return'] == pytest.approx(0.01)
