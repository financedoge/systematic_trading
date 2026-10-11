"""P4.15 — turnover and breakeven-IC gate."""
from decimal import Decimal
import json
from pathlib import Path

import pytest

from systematic_trading.research import turnover_gate as gate
from systematic_trading.research import turnover_gate_analysis as analysis
from systematic_trading.research.signal_decay import breakeven_ic

# Artifacts resolve against the repository, never the current directory: var/research is generated
# workspace evidence and is not committed, so a fresh checkout rebuilds it through the study's own
# published path. Artifact-dependent checks are not skipped — they fail loudly and name that command.
REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_ROOT = REPO_ROOT / 'var/research/turnover-gate-20261010-v1'
CALIBRATION = GATE_ROOT / 'calibration.json'
ACCEPTANCE = GATE_ROOT / 'acceptance.json'
REPLAYS = REPO_ROOT / 'var/research/fr25-placebo-20261010-v1'
REBUILD_GATE = ('.venv/Scripts/python.exe scripts/run_turnover_gate.py build\n'
                '     (it consumes the pinned P4.14 replay root var/research/fr25-placebo-20261010-v1,\n'
                '      which must be built first: .venv/Scripts/python.exe scripts/run_fr25_placebo.py\n'
                '      prepare --root var/research/fr25-placebo-20261010-v1, then its calculate,\n'
                '      economics and analyze stages)')
REBUILD_REPLAYS = ('.venv/Scripts/python.exe scripts/run_fr25_placebo.py prepare '
                   '--root var/research/fr25-placebo-20261010-v1\n'
                   '     (then its calculate, economics and analyze stages)')


def _pinned(path, *, rebuild):
    """The artifact, or a loud failure naming the published command that rebuilds it."""
    path = Path(path)
    if not path.exists():
        pytest.fail(f'Pinned evidence is missing: {path}\n'
                    'var/research is generated workspace evidence and is not committed, so a fresh '
                    'checkout must rebuild it through the study\'s own published path, from the '
                    'repository root:\n'
                    f'  {rebuild}\n'
                    'This check is not skipped: a gate verdict without its pinned evidence is not a '
                    'result, and there is no fallback that would make the assertion weaker.')
    return path


def _mapping(rows):
    return {day: weights for day, weights in rows}


# --- implied turnover ---------------------------------------------------------

def test_a_static_mapping_pays_only_for_establishing_the_book():
    mapping = _mapping([('2024-01-02', {'AAA': 0.6, 'BBB': 0.4}), ('2025-01-02', {'AAA': 0.6, 'BBB': 0.4})])
    result = gate.implied_turnover(mapping)
    assert result['rows'][0]['traded_notional'] == pytest.approx(1.0)
    assert result['rows'][1]['traded_notional'] == pytest.approx(0.0)
    assert result['total_traded_notional'] == pytest.approx(1.0)
    assert result['annual_turnover'] == pytest.approx(1.0 / (366 / 365.25), rel=1e-6)


def test_a_full_switch_each_decision_is_charged_twice():
    mapping = _mapping([('2024-01-02', {'AAA': 1.0}), ('2024-07-02', {'BBB': 1.0}), ('2025-01-02', {'AAA': 1.0})])
    result = gate.implied_turnover(mapping)
    assert [row['traded_notional'] for row in result['rows']] == pytest.approx([1.0, 2.0, 2.0])
    assert result['total_traded_notional'] == pytest.approx(5.0)
    assert result['max_traded_per_decision'] == pytest.approx(2.0)


def test_implied_turnover_needs_two_decisions_to_annualise():
    with pytest.raises(ValueError, match='at least two decisions'):
        gate.implied_turnover({'2024-01-02': {'AAA': 1.0}})


def test_implied_turnover_rejects_a_negative_or_nonfinite_weight():
    with pytest.raises(ValueError, match='negative target weight'):
        gate.implied_turnover({'2024-01-02': {'AAA': 1.0}, '2024-02-02': {'AAA': -0.5, 'BBB': 1.5}})
    with pytest.raises(ValueError, match='Nonfinite'):
        gate.implied_turnover({'2024-01-02': {'AAA': 1.0}, '2024-02-02': {'AAA': float('nan')}})


def test_implied_turnover_rejects_a_single_decision_above_two_times_nav():
    with pytest.raises(ValueError, match='above two times NAV'):
        gate.implied_turnover({'2024-01-02': {'AAA': 1.0}, '2024-02-02': {'AAA': 3.0, 'BBB': 1.0}})


def test_weights_from_targets_accepts_decimal_strings_and_rejects_negatives():
    weights = gate.weights_from_targets([dict(symbol='AAA', target_weight='0.25'),
                                         dict(symbol='BBB', target_weight=Decimal('0.5'))])
    assert weights == {'AAA': 0.25, 'BBB': 0.5}
    with pytest.raises(ValueError, match='invalid target weight'):
        gate.weights_from_targets([dict(symbol='AAA', target_weight='-0.1')])


# --- cost and breakeven -------------------------------------------------------

def test_annual_cost_is_turnover_times_the_frozen_cost():
    assert gate.annual_cost_bps(8.07) == pytest.approx(40.35)
    assert gate.annual_cost_bps(8.0, cost_bps=5.0) == pytest.approx(40.0)


def test_annual_cost_rejects_invalid_inputs():
    with pytest.raises(ValueError, match='non-negative'):
        gate.annual_cost_bps(-1.0)
    with pytest.raises(ValueError, match='non-negative'):
        gate.annual_cost_bps(1.0, cost_bps=-5)


def test_the_gate_delegates_the_breakeven_definition():
    verdict = gate.screen(8.07, sigma=0.0522)
    assert verdict['breakeven_ic'] == breakeven_ic(8.07, 0.0522, cost_bps=5.0, period_sessions=21)
    assert verdict['breakeven_ic'] == pytest.approx(0.0064, abs=5e-5)


# --- the frozen verdict -------------------------------------------------------

def test_a_cheap_signal_with_an_edge_passes():
    verdict = gate.screen(8.07, sigma=0.0522, candidate_ic=0.0943)
    assert verdict['status'] == 'pass' and verdict['cost_test'] and verdict['margin_test']
    assert verdict['ic_margin'] == pytest.approx(14.64, abs=0.05)


def test_a_candidate_above_the_cost_ceiling_is_rejected():
    verdict = gate.screen(120.0, sigma=0.0522)
    assert verdict['status'] == 'reject'
    assert verdict['cost_test'] is False and verdict['margin_test'] is False
    assert any('exceeds the' in reason for reason in verdict['reasons'])


def test_a_cheap_candidate_without_an_edge_is_rejected_on_the_margin_alone():
    verdict = gate.screen(8.07, sigma=0.0522, candidate_ic=0.01)
    assert verdict['status'] == 'reject'
    assert verdict['cost_test'] is True and verdict['margin_test'] is False
    assert any('IC margin' in reason for reason in verdict['reasons'])


def test_the_cost_ceiling_carries_its_disclosed_tolerance():
    within = gate.screen(8.8, sigma=0.0522, candidate_ic=0.0943)
    above = gate.screen(8.9, sigma=0.0522, candidate_ic=0.0943)
    assert within['cost_ceiling_bps'] == pytest.approx(44.0)
    assert within['cost_test'] is True and above['cost_test'] is False


def test_a_missing_dispersion_is_insufficient_rather_than_a_pass():
    verdict = gate.screen(8.07, sigma=None, candidate_ic=0.0943)
    assert verdict['status'] == 'insufficient'
    assert verdict['margin_test'] is None and verdict['breakeven_ic'] is None
    assert verdict['cost_test'] is True


def test_the_reference_ic_is_used_when_a_candidate_declares_none():
    verdict = gate.screen(8.07, sigma=0.0522)
    assert verdict['candidate_ic'] == gate.PROGRAMME_REFERENCE_IC


def test_the_frozen_thresholds_are_the_declared_ones():
    assert gate.THRESHOLDS['cost_bps'] == 5.0
    assert gate.THRESHOLDS['max_annual_cost_bps'] == 40.0
    assert gate.THRESHOLDS['cost_tolerance'] == 0.10
    assert gate.THRESHOLDS['min_ic_margin'] == 3.0
    assert gate.THRESHOLDS['period_sessions'] == 21


# --- calibration --------------------------------------------------------------

def test_calibration_reports_the_direction_of_the_gap():
    conservative = gate.calibrate(8.21, 8.07)
    assert conservative['measured_over_implied'] == pytest.approx(0.9829, abs=1e-4)
    assert conservative['implied_is_conservative'] is True
    optimistic = gate.calibrate(8.0, 8.4)
    assert optimistic['implied_is_conservative'] is False


def test_calibration_rejects_a_zero_implied_value():
    with pytest.raises(ValueError, match='positive implied'):
        gate.calibrate(0.0, 8.0)


# --- registered archetypes ----------------------------------------------------

def test_archetypes_are_the_registered_appendix_a_figures():
    names = {entry['name']: entry['annual_turnover'] for entry in gate.archetypes()}
    assert names == {'alpha101 fastest': 404.0, 'alpha101 median': 120.0, 'alpha101 slowest': 40.0,
                     'monitored strategy': 8.07}


def test_alpha101_archetypes_fail_and_the_monitored_book_passes():
    results = {entry['name']: entry for entry in gate.assess_archetypes(sigma=0.0522)}
    assert results['alpha101 fastest']['status'] == 'reject'
    assert results['alpha101 median']['status'] == 'reject'
    assert results['alpha101 slowest']['status'] == 'reject'
    assert results['monitored strategy']['status'] == 'pass'
    assert results['alpha101 fastest']['annual_cost_bps'] > results['alpha101 slowest']['annual_cost_bps']
    # the cost ceiling alone decides all three, so the verdict does not rest on the margin threshold
    assert all(results[name]['cost_test'] is False for name in ('alpha101 fastest', 'alpha101 median',
                                                                'alpha101 slowest'))


# --- against the frozen evidence ----------------------------------------------

def test_the_published_calibration_reverifies():
    calibration = json.loads(_pinned(CALIBRATION, rebuild=REBUILD_GATE).read_text(encoding='utf8'))
    acceptance = json.loads(_pinned(ACCEPTANCE, rebuild=REBUILD_GATE).read_text(encoding='utf8'))
    from systematic_trading.lean.contracts import sha256
    assert sha256(CALIBRATION) == acceptance['calibration_sha256']
    metrics = calibration['calibration']
    assert metrics['arms'] > 200
    assert metrics['implied_is_conservative_in_all'] is True
    assert 0.98 <= metrics['ratio_median'] <= 0.99
    assert metrics['raw_screen']['false_pass'] == 0
    assert metrics['correction'].startswith('none')


def test_the_published_verdicts_recompute_from_the_recorded_dispersion():
    calibration = json.loads(_pinned(CALIBRATION, rebuild=REBUILD_GATE).read_text(encoding='utf8'))
    sigma = calibration['sigma']
    recomputed = {entry['name']: entry['status'] for entry in gate.assess_archetypes(sigma=sigma)}
    published = {entry['name']: entry['status'] for entry in calibration['verdicts']['archetypes']}
    assert recomputed == published
    assert published['monitored strategy'] == 'pass'
    assert published['alpha101 median'] == 'reject'


def test_the_gate_and_the_decay_measurement_share_one_dispersion_definition():
    calibration = json.loads(_pinned(CALIBRATION, rebuild=REBUILD_GATE).read_text(encoding='utf8'))
    _pinned(REPLAYS / 'bars.json', rebuild=REBUILD_REPLAYS)
    assert calibration['selection_change']['matches_published'] is True
    assert calibration['sigma'] == pytest.approx(calibration['selection_change']['sigma'])
