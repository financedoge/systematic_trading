import numpy as np
import pytest

from systematic_trading.research import fitted_breakout_diagnostics as d


def test_nav_metrics_include_first_loss():
    m = d.nav_stats([100., 90., 90.])
    assert m["maxdd"] == pytest.approx(-.1)
    assert m["sessions"] == 2
    assert m["cagr"] < 0


def test_alpha_separates_beta_from_intercept():
    rng = np.random.default_rng(1)
    underlying = rng.normal(.0004, .01, 1000)
    rf = np.full(1000, .0001)
    strategy = rf + .3 * (underlying - rf) + .0002 + rng.normal(0, .00001, 1000)
    nav = lambda r: np.r_[1., np.cumprod(1 + r)]
    result = d.alpha(nav(strategy), nav(underlying), nav(rf))
    assert result["beta"] == pytest.approx(.3, abs=.001)
    assert result["alpha"] == pytest.approx(.0504, abs=.001)
    assert result["p"] < .01


def test_ic_constant_is_undefined_and_rank_is_monotonic():
    assert d.rank_ic(np.ones(100), np.arange(100.))["ic"] is None
    values = np.arange(100.)
    assert d.rank_ic(values, values ** 2)["ic"] == pytest.approx(1.)
    assert d.rank_ic(values, -values)["ic"] == pytest.approx(-1.)


def test_forward_labels_start_at_executable_open_and_do_not_cross_end():
    result = d.forward_returns(np.array([10., 20., 30., 40.]), np.array([11., 22., 33., 44.]),
                               np.ones(4), np.ones(4), 2)
    assert result[0] == pytest.approx(33 / 20 - 1)
    assert np.isnan(result[-2:]).all()


def test_holm_accounts_for_missing_tests_and_controls_family():
    assert d.holm([.01, .04, None]) == pytest.approx([.03, .08, 1.])
