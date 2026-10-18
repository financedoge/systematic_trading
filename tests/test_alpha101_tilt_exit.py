"""P4.17f — exit rules for the Alpha101 tilt: trigger semantics and the frozen optimum."""
import json
from pathlib import Path

import pytest
from retained_artifacts import requires_artifact

from systematic_trading.research import alpha101_tilt_exit_study as study

ROOT = Path('var/research/alpha101-tilt-exit-20261011-v2')
BUILT = pytest.mark.skipif(not (ROOT / 'analysis.json').exists(), reason='frozen exit study not built')
DAY = ['2026-01-{:02d}'.format(n) for n in range(1, 11)]


def state(entry_magnitude=0.10, entry_prices=None):
    prices = entry_prices or {'a': 100.0, 'b': 100.0}
    return {'entry_magnitude': entry_magnitude, 'entry_prices': prices,
            'entry_direction': {'a': 1.0, 'b': -1.0}}


def test_arm_names_and_the_two_declared_families():
    assert study.arm_name('FR25', 0.10, 'EXIT-FLIP') == 'FR25-X10-EXIT-FLIP'
    assert len(study.BUDGETS) * len(study.RULES) + len(study.SECONDARY_RULES) == 20
    assert len(study.arms()) == 2 * (1 + 20) == 42
    assert study.plan('FR25-X10-EXIT-FLIP')['family'] == 'signal'
    assert study.plan('FR25-X10-EXIT-SL-05')['family'] == 'pnl'
    assert study.plan('SOTA')['rule'] == 'CONTROL'
    with pytest.raises(ValueError, match='Unregistered exit-rule arm'):
        study.plan('FR25-X99-EXIT-FLIP')


def test_hold_never_closes_and_no_signal_closes_when_the_book_cannot_be_ranked():
    held = {'a': 0.05, 'b': -0.05}
    assert study.should_exit('HOLD', held, {}, state(), DAY[0]) is False
    assert study.should_exit('EXIT-NOSIG', held, {}, state(), DAY[0]) is True
    assert study.should_exit('EXIT-NOSIG', held, {'a': 1.0, 'b': -1.0}, state(), DAY[0]) is False


def test_flip_closes_only_when_the_signal_turns_against_the_held_tilt():
    held = {'a': 0.05, 'b': -0.05}
    aligned = {'a': 0.03, 'b': -0.03}
    opposed = {'a': -0.01, 'b': 0.01}
    assert study.alignment(held, aligned) > 0 and study.alignment(held, opposed) < 0
    assert study.should_exit('EXIT-FLIP', held, aligned, state(), DAY[0]) is False
    assert study.should_exit('EXIT-FLIP', held, opposed, state(), DAY[0]) is True
    assert study.should_exit('EXIT-FLIP-REENTER', held, opposed, state(), DAY[0]) is True


def test_fade_closes_when_the_signal_has_decayed_below_half_its_entry_size():
    held = {'a': 0.05, 'b': -0.05}
    assert study.should_exit('EXIT-FADE', held, {'a': 0.024, 'b': -0.024}, state(0.10), DAY[0]) is True
    assert study.should_exit('EXIT-FADE', held, {'a': 0.03, 'b': -0.03}, state(0.10), DAY[0]) is False


def test_the_profit_and_loss_rules_read_the_tilts_own_return():
    held = {'a': 0.05, 'b': -0.05}
    richer = {'a': 130.0, 'b': 100.0}
    poorer = {'a': 80.0, 'b': 100.0}
    assert study.tilt_return(held, state(), richer) == pytest.approx(0.05 * 0.30)
    assert study.should_exit('EXIT-TP-1', held, {}, state(), richer) is True
    assert study.should_exit('EXIT-SL-05', held, {}, state(), richer) is False
    assert study.should_exit('EXIT-SL-05', held, {}, state(), poorer) is True
    assert study.should_exit('EXIT-PNL', held, {}, state(), poorer) is False   # -1% > -2%


def test_re_entry_needs_the_entry_direction_and_the_entry_magnitude():
    current = state()
    assert study.should_reenter({'a': 1.0, 'b': -1.0}, {'a': 0.05, 'b': -0.05}, current) is True
    assert study.should_reenter({'a': 1.0, 'b': -1.0}, {'a': 0.02, 'b': -0.02}, current) is False   # too small
    assert study.should_reenter({'a': 1.0, 'b': -1.0}, {'a': -0.05, 'b': 0.05}, current) is False  # opposed
    assert study.should_reenter({}, {'a': 0.05, 'b': -0.05}, current) is False


def test_simulate_opens_monthly_holds_and_closes_on_the_rule():
    books = {day: {'a': 0.5, 'b': 0.5} for day in DAY}
    rebals = {DAY[0]}
    desired = {day: {'a': 0.05, 'b': -0.05} for day in DAY[:4]}
    desired.update({day: {'a': -0.05, 'b': 0.05} for day in DAY[4:]})
    closed = {'a': {day: 100.0 for day in DAY}, 'b': {day: 100.0 for day in DAY}}
    rows, events = study.simulate(books, rebals, 0.10, 'EXIT-FLIP', desired, closed)
    assert events['entries'] == 1 and events['exits'] == 1
    # Only the entry and the exit are submitted: between them the engine holds shares, so no session
    # re-submits an unchanged target (re-submitting is a daily-rebalanced process, not a held one).
    assert sorted(rows) == [DAY[0], DAY[4]]
    assert events['submitted'] == 2
    assert rows[DAY[0]] == {'a': 0.55, 'b': 0.45}          # entered at the monthly decision
    assert rows[DAY[4]] == {'a': 0.5, 'b': 0.5}            # flipped against it, so the tilt is off
    held, events = study.simulate(books, rebals, 0.10, 'HOLD', desired, closed)
    assert events['exits'] == 0 and events['submitted'] == 1
    assert held[DAY[0]] == {'a': 0.55, 'b': 0.45}          # held exactly as entered all month


def test_the_submitted_targets_change_only_when_the_tilt_or_the_book_changes():
    books = {day: {'a': 0.5, 'b': 0.5} for day in DAY}
    desired = {day: {'a': 0.05, 'b': -0.05} for day in DAY}
    rows, events = study.simulate(books, {DAY[0]}, 0.10, 'HOLD', desired, {})
    assert sorted(rows) == [DAY[0]] and events['submitted'] == 1
    # a strategy rebalance must always be submitted, and the book reverting afterwards is a change too
    books[DAY[5]] = {'a': 0.4, 'b': 0.6}
    rows, events = study.simulate(books, {DAY[0], DAY[5]}, 0.10, 'HOLD', desired, {})
    assert sorted(rows) == [DAY[0], DAY[5], DAY[6]] and events['submitted'] == 3
    assert rows[DAY[5]] == pytest.approx({'a': 0.45, 'b': 0.55})   # rebalanced book plus the tilt
    assert rows[DAY[6]] == pytest.approx({'a': 0.55, 'b': 0.45})   # back to the base book plus the tilt
    # unchanged sessions in between are not re-submitted
    assert DAY[1] not in rows and DAY[7] not in rows


def test_re_entry_happens_after_an_exit_not_only_while_still_held():
    """The branch used to sit behind a `held` guard an exit had already emptied, so it never fired."""
    books = {day: {'a': 0.5, 'b': 0.5} for day in DAY}
    desired = {day: {'a': 0.05, 'b': -0.05} for day in DAY}
    desired.update({DAY[2]: {'a': -0.05, 'b': 0.05}, DAY[3]: {'a': -0.05, 'b': 0.05}})  # against
    desired.update({day: {'a': 0.05, 'b': -0.05} for day in DAY[4:]})                  # aligned again
    closed = {'a': {day: 100.0 for day in DAY}, 'b': {day: 100.0 for day in DAY}}
    rows, events = study.simulate(books, {DAY[0]}, 0.10, 'EXIT-FLIP-REENTER', desired, closed)
    assert events['exits'] == 1 and events['reentries'] == 1
    assert rows[DAY[0]] == {'a': 0.55, 'b': 0.45}     # entry
    assert rows[DAY[2]] == {'a': 0.5, 'b': 0.5}       # exit
    assert rows[DAY[4]] == {'a': 0.55, 'b': 0.45}     # genuine re-entry inside the month


def test_the_profit_and_loss_rules_cannot_see_the_session_they_trade_on():
    """A target executed at day D's open may only be decided with closes before D."""
    books = {day: {'a': 0.5, 'b': 0.5} for day in DAY}
    desired = {day: {'a': 0.05, 'b': -0.05} for day in DAY}
    calm = {'2025-12-31': 100.0, **{day: 100.0 for day in DAY}}
    flat = dict(calm)
    # 'a' collapses on the last session only: a look-ahead stop would exit on that same session
    rows, events = study.simulate(books, {DAY[0]}, 0.10, 'EXIT-SL-05', desired,
                                  {'a': dict(calm, **{DAY[-1]: 10.0}), 'b': flat})
    assert events['exits'] == 0, 'the stop must not react to the close of the session it trades'
    assert set(rows) == {DAY[0]}
    # the same collapse one session earlier is knowable, so the stop fires on the following session
    rows, events = study.simulate(books, {DAY[0]}, 0.10, 'EXIT-SL-05', desired,
                                  {'a': dict(calm, **{DAY[-2]: 10.0}), 'b': flat})
    assert events['exits'] == 1 and DAY[-1] in rows
    assert rows[DAY[-1]] == {'a': 0.5, 'b': 0.5}
    # The declared prior-close entry proxy makes a later loss measurable without future prices.
    assert events['exit_days'] == [DAY[-1]]


# --- the frozen study ---------------------------------------------------------

@BUILT
@requires_artifact(ROOT / 'decisions')
def test_every_arm_is_frozen_and_replayed():
    assert len(study.arms()) == 42
    for arm in study.arms():
        assert (ROOT / 'decisions' / (arm + '.json')).exists(), arm
    for job in study.jobs():
        assert (ROOT / 'python' / (study.daily.job_name(job) + '.json')).exists(), job


@BUILT
def test_the_controls_have_no_tilt_and_the_signal_rules_do_their_job():
    diag = json.loads((ROOT / 'decision_diagnostics.json').read_text(encoding='utf8'))
    assert diag['FR25']['exits'] == 0 and diag['FR25']['entries'] == 0
    hold = diag['FR25-X10-HOLD']
    flip = diag['FR25-X10-EXIT-FLIP']
    assert hold['exits'] == 0 and hold['entries'] == 70          # monthly entry, held
    assert flip['exits'] >= 40 and flip['entries'] == 70         # the signal turns often
    assert diag['FR25-X10-EXIT-FLIP-REENTER']['reentries'] >= 100
    assert diag['FR25-X10-EXIT-NOSIG']['exits'] == 0             # this family never stops ranking entirely


@BUILT
def test_the_optimum_is_reported_for_every_metric_with_its_family_behind_it():
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    for base in ('FR25', 'SOTA'):
        pick = payload['in_sample_optimum'][base]
        assert set(pick) == {'total_return', 'cagr', 'sharpe_zero_cash', 'calmar', 'max_drawdown'}
        for arm in pick.values():
            assert study.plan(arm)['base'] == base and arm != base
    assert 'costs' in payload and len(payload['costs']) == 42
    assert payload['statement'].startswith('Arms are ranked on outcomes net of')


@BUILT
def test_no_arm_was_filtered_by_the_cost_ceiling():
    record = json.loads((ROOT / 'gate.json').read_text(encoding='utf8'))
    assert 'no arm was filtered by it' in record['note']
    over = [arm for arm, row in record['arms'].items()
            if row['verdict']['annual_cost_bps'] > record['ceiling_bps']]
    assert over, 'the study must contain arms above the ceiling, or it tested nothing'
    payload = json.loads((ROOT / 'analysis.json').read_text(encoding='utf8'))
    assert all(arm in payload['metrics'] for arm in over)
