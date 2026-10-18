"""P4.17e — the daily, threshold-triggered tilt: trigger semantics and the frozen frontier."""
import json
from pathlib import Path

import pytest
from retained_artifacts import requires_artifact

from systematic_trading.research import alpha101_tilt_daily_study as study

ROOT = Path('var/research/alpha101-tilt-daily-20261011-v2')
BUILT = pytest.mark.skipif(not (ROOT / 'analysis.json').exists(), reason='frozen daily tilt not built')


def series(*weights):
    """Books and desired tilts from a list of (day, {symbol: weight}, {symbol: tilt}) triples."""
    return {day: book for day, book, _ in weights}, {day: tilt for day, _, tilt in weights}


DAY = ['2026-01-{:02d}'.format(n) for n in range(1, 9)]


def test_daily_arm_names_and_plans_are_declared():
    assert study.daily_arm('FR25', 0.10, 0.0) == 'FR25-D10-T0'
    assert study.daily_arm('SOTA', 0.05, 2.0) == 'SOTA-D5-T200'
    assert study.monthly_arm('FR25') == 'FR25-M10'
    assert len(study.arms()) == 2 * (1 + 3 * len(study.THRESHOLDS) + 1)
    plan = study.plan('FR25-D10-T200')
    assert plan['mode'] == 'daily' and plan['budget'] == 0.10 and plan['threshold'] == 2.0
    assert study.plan('FR25-M10')['mode'] == 'monthly'
    assert study.plan('SOTA')['mode'] == 'control'
    with pytest.raises(ValueError, match='Unregistered daily-tilt arm'):
        study.plan('FR25-D10-T999')


def test_a_zero_threshold_re_tilts_whenever_the_signal_moves():
    books, desired = series(*[(day, {'a': 0.5, 'b': 0.5},
                                {'a': 0.05, 'b': -0.05} if n % 2 == 0 else {'a': -0.05, 'b': 0.05})
                               for n, day in enumerate(DAY)])
    _, stats = study.simulate(books, set(), 0.10, 0.0, desired)
    assert stats['trades'] == len(DAY)                  # every session changes the tilt
    assert stats['trade_share'] == pytest.approx(1.0)


def test_a_wide_threshold_only_trades_when_the_signal_really_moves():
    flat = [(day, {'a': 0.5, 'b': 0.5}, {'a': 0.05, 'b': -0.05}) for day in DAY[:4]]
    jump = [(DAY[4], {'a': 0.5, 'b': 0.5}, {'a': -0.05, 'b': 0.05})]
    steady = [(day, {'a': 0.5, 'b': 0.5}, {'a': -0.05, 'b': 0.05}) for day in DAY[5:]]
    books, desired = series(*flat, *jump, *steady)
    _, tight = study.simulate(books, set(), 0.10, 0.0, desired)
    assert tight['trades'] == 2                          # establishing, then the flip
    _, wide = study.simulate(books, set(), 0.10, 2.0, desired)
    assert wide['trades'] == 2                           # the flip is exactly two budgets' distance
    _, absurd = study.simulate(books, set(), 0.10, 10.0, desired)
    assert absurd['trades'] == 1                         # only the establishing tilt


def test_a_strategy_rebalance_always_re_derives_the_tilt():
    books, desired = series(*[(day, {'a': 0.5, 'b': 0.5}, {'a': 0.05, 'b': -0.05}) for day in DAY[:5]],
                            (DAY[5], {'a': 0.5, 'b': 0.5}, {'a': 0.06, 'b': -0.06}),
                            *[(day, {'a': 0.5, 'b': 0.5}, {'a': 0.06, 'b': -0.06}) for day in DAY[6:]])
    _, without = study.simulate(books, set(), 0.10, 5.0, desired)
    rows, with_rebalance = study.simulate(books, {DAY[5]}, 0.10, 5.0, desired)
    assert without['trades'] == 1                        # the small move never clears the band
    assert with_rebalance['trades'] == 2                 # the rebalance forces it through
    assert rows[DAY[5]] == {'a': 0.56, 'b': 0.44}        # and the new tilt is actually held


def test_an_empty_desired_tilt_leaves_the_book_alone():
    books, desired = series(*[(day, {'a': 0.5, 'b': 0.5}, {}) for day in DAY])
    rows, stats = study.simulate(books, set(), 0.10, 0.0, desired)
    assert stats['trades'] == 0
    assert all(row == {'a': 0.5, 'b': 0.5} for row in rows.values())


def test_the_daily_row_keeps_the_base_symbol_set_and_the_contracts():
    template = dict(signal_session='2026-01-02', known_through='2025-12-31',
                    targets=[dict(symbol=s, target_weight='0', rationale='base', sleeve='pooled') for s in ('a', 'b')])
    row = study.tilt_row(template, {'a': 0.4, 'b': 0.1})
    assert [t['symbol'] for t in row['targets']] == ['a', 'b']
    assert row['targets'][0]['target_weight'] == '0.4'
    with pytest.raises(ValueError, match='out-of-contract'):
        study.tilt_row(template, {'a': 0.9, 'b': 0.0})
    with pytest.raises(ValueError, match='outside the base universe'):
        study.tilt_row(template, {'a': 0.4, 'zz': 0.1})


def test_the_daily_cross_section_is_transposed_into_the_tested_rule():
    per_symbol = {'a': {'53': 5.0, '26': 3.0}, 'b': {'53': 1.0, '26': 4.0}, 'c': {'53': 0.0, '26': 0.0}}
    scores = study.composite_scores(['a', 'b', 'c'], per_symbol)
    assert set(scores) == {'a', 'b', 'c'}
    assert scores['a'] > scores['c']
    assert sum(scores.values()) == pytest.approx(0.0, abs=1e-12)


# --- the frozen frontier -----------------------------------------------------

@BUILT
@requires_artifact(ROOT / 'decisions')
def test_every_arm_was_frozen_and_replayed():
    assert len(study.arms()) == 34
    for arm in study.arms():
        assert (ROOT / 'decisions' / (arm + '.json')).exists(), arm
    for job in study.jobs():
        assert (ROOT / 'python' / (study.job_name(job) + '.json')).exists(), job


@BUILT
def test_the_threshold_is_the_frequency_and_cost_control():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    diag, gate = payload['diagnostics'], payload['gate']
    daily = diag['FR25-D10-T0']['trades']
    wide = diag['FR25-D10-T300']['trades']
    assert daily > 1200 and wide < 100                       # the band cuts trades by ~95%
    assert gate['arms']['FR25-D10-T0']['verdict']['annual_cost_bps'] > 130
    assert gate['arms']['FR25-D10-T300']['verdict']['annual_cost_bps'] < 44
    for arm in ('FR25-D5-T200', 'FR25-D10-T300', 'FR25-D20-T300'):
        assert gate['arms'][arm]['verdict']['status'] == 'pass'
    for arm in ('FR25-D5-T0', 'FR25-D10-T0', 'FR25-D20-T0'):
        assert gate['arms'][arm]['verdict']['status'] == 'reject'


@BUILT
def test_high_frequency_degrades_the_book_monotonically():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    metrics = payload['metrics']
    control = metrics['FR25']['total_return']
    assert metrics['FR25-D5-T0']['total_return'] < control
    assert metrics['FR25-D10-T0']['total_return'] < metrics['FR25-D5-T0']['total_return']
    assert metrics['FR25-D20-T0']['total_return'] < metrics['FR25-D10-T0']['total_return']
    assert metrics['FR25-D20-T0']['sharpe_zero_cash'] < metrics['FR25']['sharpe_zero_cash']
    assert metrics['SOTA-D20-T0']['total_return'] < metrics['SOTA']['total_return']


@BUILT
def test_nothing_that_clears_the_ceiling_is_distinguishable_from_doing_nothing():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    for base in ('FR25', 'SOTA'):
        for row in payload['contrasts'][base]['6']:
            if row['threshold'] is None or row['threshold'] < 2.0:
                continue
            assert row['holm_p'] >= 0.05
            assert row['ci95'][0] < 0 < row['ci95'][1]
            assert abs(row['mean_annual']) < 0.01
