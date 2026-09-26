import numpy as np
import pytest

from systematic_trading.research.underlying_sectors import (
    aggregate_cohort, hhi_features, horizon_returns,
)


def test_aggregate_sums_underlying_turnover_and_snapshot_weighted_returns():
    p = np.array([[10., 20., 5.], [11., 18., 6.]])
    v = np.array([[10., 5., 20.], [20., 10., 10.]])
    a = aggregate_cohort(p, v, p, [0, 0, 1], [3., 1., 2.], sector_count=2)
    np.testing.assert_allclose(a['dollars'], [[200, 100], [400, 60]])
    np.testing.assert_allclose(a['shares'], [[15, 20], [30, 10]])
    np.testing.assert_allclose(a['weighted_return'][1], [.05, .2])
    np.testing.assert_allclose(a['equal_return'][1], [0, .2], atol=1e-14)
    np.testing.assert_allclose(a['within_hhi'][0], [.5, 1])


def test_missing_names_stay_in_coverage_denominator():
    p = np.array([[10., np.nan], [11., np.nan]])
    a = aggregate_cohort(p, np.ones_like(p), p, [0, 0], [3., 1.], sector_count=1)
    np.testing.assert_allclose(a['value_coverage'][:, 0], .75)
    np.testing.assert_allclose(a['name_coverage'][:, 0], .5)
    assert np.isnan(a['weighted_return'][0, 0])
    assert a['weighted_return'][1, 0] == pytest.approx(.1)


def test_forward_returns_exclude_signal_day_and_do_not_bridge_gaps():
    a = np.array([.9, .1, .2, np.nan, .3])
    out = horizon_returns(a, 2)
    assert out[0] == pytest.approx(.32)
    assert np.isnan(out[1:]).all()


def test_same_cohort_features_are_causal():
    a = np.column_stack((np.arange(1, 201)+100., np.ones(200)*50))
    before = hhi_features(a, smoothing='smoothed')
    a[151:] *= np.array([3., 1.])
    after = hhi_features(a, smoothing='smoothed')
    np.testing.assert_allclose(before[:151], after[:151], equal_nan=True)
    assert np.isfinite(before[70:]).all()


def test_raw_derivatives_and_no_zero_filled_sector():
    a = np.array([[1., 1.], [1., 2.], [1., 3.], [np.nan, 2.]])
    out = hhi_features(a)
    h = np.array([.5, 5/9, 10/16])
    assert out[2, 2] == pytest.approx(h[2]-2*h[1]+h[0])
    assert np.isnan(out[3]).all()


def test_invalid_cohort_rejected():
    with pytest.raises(ValueError):
        aggregate_cohort(np.ones((3, 2)), np.ones((3, 2)), np.ones((3, 2)), [0, 1], [0., 1.], sector_count=2)
