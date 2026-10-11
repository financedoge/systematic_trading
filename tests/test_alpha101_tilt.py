"""P4.17b — the Alpha101 tactical tilt: rule, bounds and the frozen measurement."""
import json
from pathlib import Path

import pytest

from systematic_trading.research import alpha101_tilt as tilt

ROOT = Path('var/research/alpha101-tilt-20261011-v1')
BUILT = pytest.mark.skipif(not (ROOT / 'tilt.json').exists(), reason='frozen tilt measurement not built')


def book(**weights):
    return {symbol: float(weight) for symbol, weight in weights.items()}


# --- the tilt rule -----------------------------------------------------------

def test_rank_scores_are_linear_and_mean_zero():
    assert tilt.rank_scores(['a', 'b']) == {'a': 1.0, 'b': -1.0}
    scores = tilt.rank_scores(['a', 'b', 'c'])
    assert scores == {'a': 1.0, 'b': 0.0, 'c': -1.0}
    assert sum(scores.values()) == pytest.approx(0.0)
    four = tilt.rank_scores(['a', 'b', 'c', 'd'])
    assert four['a'] == 1.0 and four['d'] == -1.0 and sum(four.values()) == pytest.approx(0.0)


def test_the_tilt_is_nav_neutral_and_spends_exactly_the_budget():
    base = book(a=0.30, b=0.25, c=0.25, d=0.18)
    values = {'a': 4.0, 'b': 3.0, 'c': 2.0, 'd': 1.0}
    tilted, diagnostic = tilt.tilt_weights(base, values, 0.10)
    assert diagnostic['applied'] and diagnostic['scale'] == pytest.approx(1.0)
    assert sum(tilted.values()) == pytest.approx(sum(base.values()))
    gains = sum(value - base[symbol] for symbol, value in tilted.items() if value > base[symbol])
    losses = sum(base[symbol] - value for symbol, value in tilted.items() if value < base[symbol])
    assert gains == pytest.approx(0.05) and losses == pytest.approx(0.05)
    assert tilted['a'] > base['a'] and tilted['d'] < base['d']


def test_the_tilt_never_breaches_the_cap():
    base = book(a=0.45, b=0.30, c=0.20)
    values = {'a': 9.0, 'b': 1.0, 'c': 0.0}
    tilted, diagnostic = tilt.tilt_weights(base, values, 0.20)
    assert diagnostic['applied'] is True
    assert diagnostic['cap_binding'] is True and diagnostic['scale'] < 1.0
    assert max(tilted.values()) <= tilt.MAX_WEIGHT + 1e-12
    assert sum(tilted.values()) == pytest.approx(sum(base.values()))


def test_the_tilt_never_makes_a_weight_negative():
    base = book(a=0.20, b=0.20, c=0.02)
    values = {'a': 5.0, 'b': 1.0, 'c': 0.0}
    tilted, diagnostic = tilt.tilt_weights(base, values, 0.20)
    assert min(tilted.values()) >= 0.0
    assert diagnostic['scale'] < 1.0
    assert sum(tilted.values()) == pytest.approx(sum(base.values()))


def test_a_book_without_a_cross_section_is_left_alone():
    base = book(a=0.5, b=0.4)
    tilted, diagnostic = tilt.tilt_weights(base, {'a': 1.0}, 0.10)
    assert tilted == base and diagnostic['applied'] is False
    sparse, other = tilt.tilt_weights(base, {'a': 1.0, 'b': 1.0}, 0.10)
    assert sparse == base and other['applied'] is False       # no rank spread to tilt on
    assert 'reason' in other


# --- the published headroom --------------------------------------------------

def test_the_headroom_is_derived_from_the_published_ceiling_and_drag():
    configured = tilt.calibration()
    assert configured['ceiling_bps'] == pytest.approx(44.0)
    assert configured['monitored_drag_bps'] == pytest.approx(40.4, abs=0.1)
    assert configured['headroom_bps'] == pytest.approx(44.0 - configured['monitored_drag_bps'])
    assert configured['cost_bps'] == 5.0
    thresholds = tilt.headroom_thresholds(configured['headroom_bps'])
    assert thresholds['max_annual_cost_bps'] == pytest.approx(configured['headroom_bps'])
    assert thresholds['cost_tolerance'] == 0.0
    assert thresholds['min_ic_margin'] == 3.0                  # the frozen margin is not relaxed


# --- the frozen measurement --------------------------------------------------

@BUILT
def test_the_grid_is_the_whole_family_and_nothing_is_dropped():
    payload = json.loads((ROOT / 'tilt.json').read_text(encoding='utf8'))
    rows = payload['rows']
    assert len(rows) == 16 * 3
    assert {row['alpha'] for row in rows} == set(tilt.screening.lib.REGISTERED)
    assert {row['budget'] for row in rows} == set(tilt.BUDGETS)
    assert payload['thresholds']['min_ic_margin'] == 3.0
    assert payload['decisions'] == 130


@BUILT
def test_every_candidate_carries_a_verdict_and_a_reason():
    payload = json.loads((ROOT / 'tilt.json').read_text(encoding='utf8'))
    for row in payload['rows']:
        assert row['gate']['status'] in {'pass', 'reject', 'insufficient'}
        assert row['gate']['reasons'], (row['alpha'], row['budget'])
        assert row['gate']['cost_ceiling_bps'] == pytest.approx(payload['calibration']['headroom_bps'])


@BUILT
def test_the_tilt_uses_a_small_fraction_of_the_headroom_at_the_small_budget():
    payload = json.loads((ROOT / 'tilt.json').read_text(encoding='utf8'))
    headroom = payload['calibration']['headroom_bps']
    small = [row for row in payload['rows'] if row['budget'] == 0.05]
    assert max(row['gate']['annual_cost_bps'] for row in small) < 0.2 * headroom
    assert sum(1 for row in small if row['gate']['status'] == 'pass') >= 12
    # the breakeven IC collapses relative to the rejected full mappings
    assert max(row['gate'].get('breakeven_ic') or 0.0 for row in small) < 0.001


@BUILT
def test_the_balance_breaks_at_the_largest_budget():
    payload = json.loads((ROOT / 'tilt.json').read_text(encoding='utf8'))
    passes = {budget: sum(1 for row in payload['rows']
                          if row['budget'] == budget and row['gate']['status'] == 'pass')
              for budget in tilt.BUDGETS}
    assert passes[0.05] >= 12 and passes[0.10] >= 12
    assert passes[0.20] < passes[0.05]
    expensive = [row for row in payload['rows'] if row['budget'] == 0.20]
    assert max(row['gate']['annual_cost_bps'] for row in expensive) > payload['calibration']['headroom_bps']


@BUILT
def test_negative_information_is_rejected_rather_than_tilted_long():
    payload = json.loads((ROOT / 'tilt.json').read_text(encoding='utf8'))
    rows = {row['alpha']: row for row in payload['rows'] if row['budget'] == 0.05}
    for alpha in ('101', '23', '12'):
        assert rows[alpha]['observed_ic'] < 0
        assert rows[alpha]['gate']['status'] == 'reject'
    assert rows['7']['gate']['status'] == 'insufficient'        # still a constant cross-section


@BUILT
def test_the_measurement_reproduces_and_its_inputs_are_unchanged():
    checks = tilt.verify(ROOT)
    assert checks['reproduced'] is True
    assert all(value for key, value in checks.items() if key != 'reproduced')
