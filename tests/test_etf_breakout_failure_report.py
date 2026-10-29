from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_etf_breakout_failure_report as report  # noqa: E402
from test_breakout_revisit import fixture  # noqa: E402


def test_report_calmar_has_no_optimizer_floor():
    assert report.standard_calmar(.06, -.01) == pytest.approx(6)
    assert report.standard_calmar(-.06, -.20) == pytest.approx(-.3)
    assert report.standard_calmar(.06, 0) is None


@pytest.mark.parametrize("delay", [0, 1])
def test_log_attribution_reconciles_gaps_fees_and_partial_window(delay):
    f, prepared = fixture()
    f.open[3], f.open[5] = 77., 70.
    sim = report.source.br.simulate(f, prepared, start=1, delay=delay)
    for start in (2, 3, 4):
        result = report.interval_accounting(f, sim, start, len(f.close))
        assert result["net_cumulative"] == pytest.approx(sim["nav"][-1] / sim["nav"][start - 1] - 1)
        assert result["captured_market_log_return"] + result["uninvested_market_log_return"] == pytest.approx(np.log(f.close[-1] / f.close[start - 1]))
        assert result["max_daily_accounting_error"] < 1e-12
        assert result["fee_cumulative_drag"] >= -1e-12


def test_attribution_rejects_corrupted_economic_path():
    f, prepared = fixture()
    sim = report.source.br.simulate(f, prepared, start=1)
    sim["nav"][3] *= 1.01
    with pytest.raises(AssertionError):
        report.interval_accounting(f, sim, 2, len(f.close))


def test_activated_percentage_trail_can_leave_initial_stop_unchanged():
    f, prepared = fixture((100, 101, 103, 114, 96, 95, 94, 93))
    f.days = np.arange(len(f.close)) + np.datetime64("2023-01-01")
    prepared["L"] = np.ones(len(f.close), int)
    prepared["parameters"][12] = 1
    prepared["parameters"][14] = .30
    prepared["parameters"][15] = 1
    sim = report.source.br.simulate(f, prepared, start=1)
    episodes = report.episode_details(f, prepared, sim, 2, len(f.close))
    e = episodes[0]
    assert e["armed"]
    assert e["exit_kind"] == "Initial risk stop"
    assert e["effective_last_stop"] == 97
    assert e["armed_days_at_initial_floor"] == 3
    assert e["base_pct_trail_break_even_peak_gain"] == pytest.approx(.3 / .7)


def test_early_window_never_uses_final_episode_exit_or_peak():
    f, prepared = fixture((100, 101, 103, 104, 120, 110, 96, 97))
    f.days = np.arange(len(f.close)) + np.datetime64("2023-01-01")
    prepared["L"] = np.ones(len(f.close), int)
    sim = report.source.br.simulate(f, prepared, start=1, end=4)
    e = report.episode_details(f, prepared, sim, 2, 4)[0]
    assert e["exit"] is None
    assert e["exit_or_mark"] == 104
    assert e["peak_gain"] == pytest.approx(.04)
