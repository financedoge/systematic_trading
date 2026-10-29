import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_fitted_breakout_portfolios import overlay_targets  # noqa: E402


def panel():
    return dict(symbols=np.array(["A", "B", "BIL"]),
        days=np.array(["2022-12-30", "2023-01-03", "2023-01-04", "2023-01-05"]),
        close=np.ones((4, 3)), fr25=np.tile([.45, .30, 0.], (4, 1)))


def test_overlay_preserves_core_cash_and_parks_removed_exposure():
    a = panel()
    multiplier = np.tile([.5, 1., 1.], (4, 1))
    weights, ix, theory = overlay_targets(a, multiplier, "dynamic")
    np.testing.assert_allclose(theory[0], [.225, .30, .225, 0.])
    assert np.allclose(theory.sum(axis=1), .75)
    assert ix.tolist() == [0]
    np.testing.assert_allclose(weights[0], theory[0])


def test_overlay_event_adoption_and_fixed_interval_control():
    a = panel()
    multiplier = np.tile([.5, 1., 1.], (4, 1))
    multiplier[1:, 0] = 1.
    weights, ix, theory = overlay_targets(a, multiplier, "dynamic")
    assert ix.tolist() == [0, 1]
    np.testing.assert_allclose(weights[1], [.45, .30, 0., 0.])
    _, fixed, fixed_theory = overlay_targets(a, multiplier, "monthly")
    assert fixed.tolist() == [0]
    np.testing.assert_allclose(fixed_theory, theory)


def test_overlay_future_changes_do_not_change_prior_targets():
    a = panel()
    x, y = np.ones((4, 3)), np.ones((4, 3))
    y[2:] = .5
    left = overlay_targets(a, x, "dynamic")
    right = overlay_targets(a, y, "dynamic")
    np.testing.assert_allclose(left[0][:2], right[0][:2])
    np.testing.assert_allclose(left[2][:2], right[2][:2])
