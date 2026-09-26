"""Exploratory sector-volume HHI diagnostics; no strategy or execution changes."""
from __future__ import annotations

import numpy as np


def volume_hhi(activity: np.ndarray) -> np.ndarray:
    activity = np.asarray(activity, dtype=float)
    if activity.ndim != 2 or activity.shape[1] < 2:
        raise ValueError('Expected sessions by at least two sectors')
    if not np.isfinite(activity).all() or (activity <= 0).any():
        raise ValueError('Activity must be finite and positive; never fill missing sectors')
    shares = activity/activity.sum(axis=1, keepdims=True)
    return (shares**2).sum(axis=1)


def causal_ema(values: np.ndarray, span: int) -> np.ndarray:
    if span < 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError('EMA requires finite observations and a positive span')
    result = np.empty(len(values), dtype=float)
    result[0] = values[0]
    alpha = 2/(span+1)
    for i in range(1, len(values)):
        result[i] = alpha*values[i]+(1-alpha)*result[i-1]
    return result


def lagged_derivatives(values: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    if lag < 1:
        raise ValueError('Derivative lag must be positive')
    values = np.asarray(values, dtype=float)
    first, second = np.full(len(values), np.nan), np.full(len(values), np.nan)
    first[lag:] = (values[lag:]-values[:-lag])/lag
    second[2*lag:] = (values[2*lag:]-2*values[lag:-lag]+values[:-2*lag])/lag**2
    return first, second


def forward_returns(prices: np.ndarray, horizon: int) -> np.ndarray:
    prices = np.asarray(prices, dtype=float)
    if horizon < 1 or not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError('Returns require positive finite prices and horizon')
    result = np.full(prices.shape, np.nan)
    result[:-horizon] = prices[horizon:]/prices[:-horizon]-1
    return result


def average_ranks(values: np.ndarray) -> np.ndarray:
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    ranks = np.cumsum(counts)-(counts-1)/2
    return ranks[inverse]


def correlations(x: np.ndarray, y: np.ndarray) -> dict:
    keep = np.isfinite(x) & np.isfinite(y)
    a, b = np.asarray(x)[keep], np.asarray(y)[keep]
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return dict(n=len(a), pearson=None, spearman=None)
    return dict(n=len(a), pearson=float(np.corrcoef(a, b)[0, 1]),
                spearman=float(np.corrcoef(average_ranks(a), average_ranks(b))[0, 1]))


def correlation_block_interval(x, y, *, block=240, replicates=1000, seed=20260926):
    """Descriptive paired circular-block percentile interval, not an iid p-value."""
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = np.asarray(x)[keep], np.asarray(y)[keep]
    if len(x) < block*2:
        return None
    rng = np.random.default_rng(seed)
    starts = rng.integers(len(x), size=(replicates, int(np.ceil(len(x)/block))))
    indices = ((starts[:, :, None]+np.arange(block)) % len(x)).reshape(replicates, -1)[:, :len(x)]
    a, b = x[indices], y[indices]
    a -= a.mean(axis=1, keepdims=True)
    b -= b.mean(axis=1, keepdims=True)
    values = (a*b).sum(axis=1)/np.sqrt((a*a).sum(axis=1)*(b*b).sum(axis=1))
    return [float(v) for v in np.quantile(values[np.isfinite(values)], [.025, .975])]
