"""Coverage-aware descriptive aggregation of historical equity sector cohorts."""
from __future__ import annotations

import numpy as np


def aggregate_cohort(close, volume, adjusted, sector_ids, values, *, sector_count=11):
    """Aggregate one dated cohort. Weights are fixed past snapshot portfolio values.

    Missing names are retained in coverage denominators; reported aggregates cover
    observed names only. Returns reweight observed one-day returns, never fill
    missing prices. These conditional observed-subset returns are not index returns.
    """
    close, volume, adjusted = [np.asarray(a, float) for a in (close, volume, adjusted)]
    values, sector_ids = np.asarray(values, float), np.asarray(sector_ids, int)
    if close.shape != volume.shape or close.shape != adjusted.shape or close.ndim != 2:
        raise ValueError('Expected matching sessions-by-stocks arrays')
    if close.shape[1] != len(values) or len(values) != len(sector_ids) or (values <= 0).any():
        raise ValueError('Cohort weights must be positive and match stock columns')
    if not np.isfinite(values).all() or (sector_ids < 0).any() or (sector_ids >= sector_count).any():
        raise ValueError('Invalid weights or sectors')
    shape = (len(close), sector_count)
    out = {k: np.full(shape, np.nan) for k in ('shares', 'dollars', 'within_hhi', 'value_coverage',
        'name_coverage', 'return_value_coverage', 'return_name_coverage', 'weighted_return', 'equal_return')}
    one_day = np.full_like(adjusted, np.nan)
    valid_prices = np.isfinite(adjusted) & (adjusted > 0)
    good = valid_prices[1:] & valid_prices[:-1]
    np.divide(adjusted[1:], adjusted[:-1], out=one_day[1:], where=good)
    one_day[1:] -= 1
    for s in range(sector_count):
        cols = sector_ids == s
        if not cols.any():
            continue
        w = values[cols]
        observed = np.isfinite(close[:, cols]) & (close[:, cols] > 0) & np.isfinite(volume[:, cols]) & (volume[:, cols] >= 0)
        shares = np.where(observed, volume[:, cols], 0)
        dollars = np.where(observed, volume[:, cols]*close[:, cols], 0)
        out['shares'][:, s] = shares.sum(axis=1)
        out['dollars'][:, s] = dollars.sum(axis=1)
        out['value_coverage'][:, s] = (observed*w).sum(axis=1)/w.sum()
        out['name_coverage'][:, s] = observed.mean(axis=1)
        total = dollars.sum(axis=1)
        np.divide((dollars**2).sum(axis=1), total**2, out=out['within_hhi'][:, s], where=total > 0)
        r = one_day[:, cols]
        usable = np.isfinite(r)
        covered_value = (usable*w).sum(axis=1)
        count = usable.sum(axis=1)
        out['return_value_coverage'][:, s] = covered_value/w.sum()
        out['return_name_coverage'][:, s] = count/len(w)
        np.divide((np.where(usable, r, 0)*w).sum(axis=1), covered_value,
                  out=out['weighted_return'][:, s], where=covered_value > 0)
        np.divide(np.where(usable, r, 0).sum(axis=1), count,
                  out=out['equal_return'][:, s], where=count > 0)
        out['shares'][total <= 0, s] = np.nan
        out['dollars'][total <= 0, s] = np.nan
    return out


def horizon_returns(daily_returns, horizon):
    """t+1 through t+h, and NaN if any required future daily observation is missing."""
    a = np.asarray(daily_returns, float)
    if horizon < 1:
        raise ValueError('Positive horizon required')
    result = np.full(a.shape, np.nan)
    for t in range(len(a)-horizon):
        window = a[t+1:t+horizon+1]
        valid = np.isfinite(window).all(axis=0)
        result[t] = np.where(valid, np.prod(1+window, axis=0)-1, np.nan)
    return result


def hhi_features(activity, *, smoothing='raw'):
    """One cohort through time, so membership changes do not enter the stencil."""
    a = np.asarray(activity, float)
    ok = np.isfinite(a).all(axis=1) & (a > 0).all(axis=1)
    hhi = np.full(len(a), np.nan)
    hhi[ok] = ((a[ok]/a[ok].sum(axis=1, keepdims=True))**2).sum(axis=1)
    return scalar_features(hhi, smoothing=smoothing)


def scalar_features(hhi, *, smoothing='raw'):
    hhi = np.asarray(hhi, float)
    c = hhi.copy()
    lag = 1
    if smoothing == 'smoothed':
        lag = 10
        # Restart after missing data; require 50 consecutive sessions to wash out initialization.
        c[:] = np.nan
        ema, run = 0., 0
        for t, x in enumerate(hhi):
            if not np.isfinite(x):
                run = 0
                continue
            ema = x if run == 0 else (2/11)*x+(9/11)*ema
            run += 1
            if run >= 50:
                c[t] = ema
    elif smoothing != 'raw':
        raise ValueError('Unknown smoothing')
    d1, d2 = np.full(len(c), np.nan), np.full(len(c), np.nan)
    d1[lag:] = (c[lag:]-c[:-lag])/lag
    d2[2*lag:] = (c[2*lag:]-2*c[lag:-lag]+c[:-2*lag])/lag**2
    return np.column_stack((c, d1, d2))
