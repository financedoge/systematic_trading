from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_trend_exit_failure_report as report  # noqa: E402
from test_breakout_revisit import fixture  # noqa: E402


def setup(close=(100, 101, 102, 103, 104, 105, 106, 107, 106.5, 103, 102, 101)):
    f, p = fixture(close)
    f.days = np.arange(len(f.close)) + np.datetime64("2023-01-01")
    p["trend_rule"] = dict(lookback=21, buffer_atr=1.)
    p["parameters"][15] = 1e12
    return f, p


def test_independent_support_excludes_today_and_pre_entry_prices():
    c = np.exp(np.arange(30) * .01)
    v = report.independent_support(c, 10, 20, report.RULE, .1)
    c[:10] *= .01
    c[20:] *= 100
    assert report.independent_support(c, 10, 20, report.RULE, .1) == v
    assert report.independent_support(c, 18, 20, report.RULE, .1) is None


def test_symmetric_zero_slope_does_not_form_spurious_support():
    c = np.array([74.20237732, 74.18412018, 74.24800873, 74.18412018, 74.20237732, 75.])
    assert report.independent_support(c, 0, 5, report.RULE, .08) is None


@pytest.mark.parametrize("delay", [0, 1])
def test_reconstruction_includes_pending_exit_and_separates_fill_gap(delay):
    f, p = setup()
    f.open[10:] = 90
    sim = report.study.model.simulate(f, p, start=1, delay=delay)
    for lo in (2, 5, 9):
        episodes, count, error = report.inspect_episodes(f, p, sim, lo, len(f.close))
        assert count > 0 and error < 1e-8
        assert sum(e["evaluation_log_contribution"] for e in episodes) == pytest.approx(np.log(sim["nav"][-1] / sim["nav"][lo - 1]))
        e = episodes[0]
        assert e["exit_kind"] == "Trend support"
        assert e["net_return"] == pytest.approx(e["exit_or_mark"] / e["entry_price"] * .9995 / 1.0005 - 1)
        assert e["decision_to_fill_gap"] == pytest.approx(e["exit_or_mark"] / e["decision_close"] - 1)


def test_reconstruction_rejects_corrupted_support_even_when_stop_is_unchanged():
    f, p = setup()
    sim = report.study.model.simulate(f, p, start=1)
    t = np.flatnonzero(np.isfinite(sim["trend_level"]))[0]
    sim["trend_level"][t] += .01
    with pytest.raises(AssertionError):
        report.inspect_episodes(f, p, sim, 2, len(f.close))


def test_cutoff_does_not_leak_later_exit_or_peak():
    f, p = setup()
    sim = report.study.model.simulate(f, p, start=1)
    e = report.inspect_episodes(f, p, sim, 2, 6)[0][0]
    assert e["exit"] is None and e["decision"] is None
    assert e["exit_kind"] == "Open at cutoff"
    assert e["exit_or_mark"] == f.close[5]
    assert e["peak_close_gain"] == pytest.approx(f.close[5] / f.open[2] - 1)


def test_initial_stop_classification_when_no_trend_forms():
    f, p = setup((100, 101, 80, 82, 83, 84, 85, 86))
    sim = report.study.model.simulate(f, p, start=1)
    e = report.inspect_episodes(f, p, sim, 2, len(f.close))[0][0]
    assert e["exit_kind"] == "Initial risk"
    assert not e["trend_formed"]
