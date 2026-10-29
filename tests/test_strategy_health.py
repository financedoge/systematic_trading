from dataclasses import replace

import pytest

from systematic_trading.research.strategy_health import (
    ClosedTrade, HealthConfig, HealthController, Mode, loss_streaks,
)


def trade(i, value=-.01, *, shadow=False, policy="original", **changes):
    t = ClosedTrade(str(i), policy, 10*i, 10*i+5, 10*i+5, value, .02, shadow)
    return replace(t, **changes)


def paused():
    c = HealthController("original")
    for i in range(1, 5):
        c.observe(trade(i))
    return c


def recover(c, policy="original"):
    for i, value in zip(range(6, 10), [.02, .02, -.01, .02], strict=True):
        d = c.observe(trade(i, value, shadow=True, policy=policy))
    return d


def test_three_losses_defend_four_pause_after_outcomes_known():
    c = HealthController("original")
    assert c.observe(trade(1)).mode == Mode.NORMAL
    assert c.observe(trade(2)).mode == Mode.NORMAL
    d = c.observe(trade(3, known_session=39))
    assert (d.mode, d.risk_multiplier, d.earliest_effective_session) == (Mode.DEFENSIVE, .5, 40)
    assert not d.request_refit
    d = c.observe(trade(4))
    assert (d.mode, d.allow_new_entry, d.request_refit) == (Mode.PAUSED, False, True)
    assert d.risk_multiplier == 0
    assert d.ewma_r == pytest.approx(-.5)
    assert d.ewma_win_rate == 0


def test_shadow_recovery_is_fresh_and_requires_four_observations():
    c = paused()
    with pytest.raises(ValueError, match="fresh"):
        c.observe(trade(5, .1, shadow=True, entry_session=40))
    for i in (6, 7, 8):
        assert c.observe(trade(i, .02, shadow=True)).mode == Mode.PAUSED
    d = c.observe(trade(9, -.01, shadow=True))
    assert d.mode == Mode.PROBATION and d.risk_multiplier == .25
    assert not d.request_refit
    assert d.earliest_effective_session == 96
    with pytest.raises(ValueError, match="Probation"):
        c.observe(trade(10, entry_session=95))


def test_wins_without_positive_compounded_return_do_not_recover():
    c = paused()
    for i, value in zip(range(6, 10), [.01, .01, .01, -.04], strict=True):
        d = c.observe(trade(i, value, shadow=True))
    assert d.mode == Mode.PAUSED


def test_recovery_cannot_be_manufactured_by_small_risk_denominators():
    c = paused()
    for i in (6, 7, 8):
        c.observe(trade(i, .01, shadow=True, initial_risk_fraction=.001))
    d = c.observe(trade(9, -.10, shadow=True, initial_risk_fraction=.1))
    assert d.mode == Mode.PAUSED  # positive sum R, negative compounded return


def test_one_refit_candidate_requires_new_forward_evidence():
    c = paused()
    c.observe(trade(5, .1, shadow=True))
    c.stage_shadow_candidate("refit1", fit_cutoff=55, available_session=56)
    assert not c.phase_r
    with pytest.raises(ValueError):
        c.stage_shadow_candidate("refit2", fit_cutoff=55, available_session=56)
    with pytest.raises(ValueError, match="Unexpected"):
        c.observe(trade(6, .1, shadow=True))
    d = recover(c, "refit1")
    assert d.policy_id == "refit1" and d.mode == Mode.PROBATION


def test_probation_needs_actual_trades_and_repauses_on_two_losses():
    c = paused()
    recover(c)
    with pytest.raises(ValueError, match="actual"):
        c.observe(trade(10, .1, shadow=True))
    assert c.observe(trade(10)).mode == Mode.PROBATION
    d = c.observe(trade(11))
    assert d.mode == Mode.PAUSED and d.request_refit


def test_successful_probation_and_defensive_recovery_have_hysteresis():
    c = paused()
    recover(c)
    assert c.observe(trade(10, .02)).mode == Mode.PROBATION
    assert c.observe(trade(11, -.01)).mode == Mode.PROBATION
    assert c.observe(trade(12, .02)).mode == Mode.NORMAL
    c = HealthController("original")
    for i in range(1, 4):
        c.observe(trade(i))
    assert c.observe(trade(4, .02)).mode == Mode.DEFENSIVE
    assert c.observe(trade(5, .02)).mode == Mode.NORMAL


def test_duplicate_wrong_policy_and_backdated_evidence_rejected():
    c = HealthController("original")
    c.observe(trade(2))
    with pytest.raises(ValueError, match="Duplicate"):
        c.observe(trade(2))
    with pytest.raises(ValueError, match="known-time"):
        c.observe(trade(1))
    with pytest.raises(ValueError, match="Unexpected"):
        c.observe(trade(3, policy="future_fit"))
    assert c.loss_streak == 1


def test_prefix_invariance_and_zero_outcome_breaks_loss_run():
    outcomes = [trade(i, x) for i, x in enumerate([-.01, -.01, 0, -.01, -.01, -.01], 1)]
    full, prefix = HealthController("original"), HealthController("original")
    a = [full.observe(t) for t in outcomes]
    b = [prefix.observe(t) for t in outcomes[:4]]
    assert a[:4] == b
    assert loss_streaks([-.01, -.01, 0, -.01]) == [1, 2, 0, 1]


@pytest.mark.parametrize("changes", [dict(net_return=float("nan")), dict(net_return=-1),
    dict(initial_risk_fraction=0), dict(known_session=1), dict(entry_session=10.5)])
def test_invalid_evidence_rejected_without_state_change(changes):
    c = HealthController("original")
    with pytest.raises(ValueError):
        c.observe(trade(1, **changes))
    assert c.last_known == -1 and not c.seen


def test_config_and_future_candidate_checks():
    with pytest.raises(ValueError):
        HealthConfig(pause_losses=3)
    with pytest.raises(ValueError):
        HealthConfig(shadow_wins=5)
    c = paused()
    with pytest.raises(ValueError):
        c.stage_shadow_candidate("refit", fit_cutoff=50, available_session=50)
