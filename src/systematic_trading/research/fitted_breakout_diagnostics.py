"""Return, benchmark-alpha and forward-IC diagnostics for fitted ETF lifecycles."""
from __future__ import annotations

from math import erfc, sqrt

import numpy as np
import pandas as pd


def nav_stats(nav):
    a = np.asarray(nav, float)
    if len(a) < 3 or not np.isfinite(a).all() or (a <= 0).any():
        raise ValueError("invalid NAV window")
    r = a[1:] / a[:-1] - 1
    sd = float(r.std(ddof=1))
    dd = float(np.min(a / np.maximum.accumulate(a) - 1))
    growth = float((a[-1] / a[0]) ** (252 / len(r)) - 1)
    return dict(cagr=growth, sharpe=float(r.mean() / sd * np.sqrt(252)) if sd else 0.,
        maxdd=dd, calmar=growth / max(.03, -dd), sessions=len(r), ann_vol=sd * np.sqrt(252))


def hac_regression(y, x, lag=21):
    """OLS with Bartlett/Newey-West covariance; normal approximate two-sided p."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    if x.ndim == 1:
        x = x[:, None]
    keep = np.isfinite(y) & np.isfinite(x).all(axis=1)
    y, x = y[keep], x[keep]
    design = np.column_stack([np.ones(len(y)), x])
    if len(y) < 50 or np.linalg.matrix_rank(design) < design.shape[1]:
        return None
    inverse = np.linalg.inv(design.T @ design)
    coefficients = inverse @ design.T @ y
    score = design * (y - design @ coefficients)[:, None]
    meat = score.T @ score
    for k in range(1, min(lag, len(y) - 1) + 1):
        cross = score[k:].T @ score[:-k]
        meat += (1 - k / (lag + 1)) * (cross + cross.T)
    variance = inverse @ meat @ inverse * len(y) / (len(y) - design.shape[1])
    se = np.sqrt(np.maximum(0, np.diag(variance)))
    z = np.divide(coefficients, se, out=np.zeros_like(coefficients), where=se > 1e-16)
    return dict(coefficients=coefficients.tolist(), se=se.tolist(), z=z.tolist(),
        p=[erfc(abs(float(v)) / sqrt(2)) for v in z], n=len(y))


def alpha(nav, underlying_close, bill_close):
    """Net return alpha over BIL, controlling for the same ETF's BIL-excess return."""
    nav, asset, bill = map(lambda x: np.asarray(x, float), (nav, underlying_close, bill_close))
    rf = bill[1:] / bill[:-1] - 1
    y = nav[1:] / nav[:-1] - 1 - rf
    x = asset[1:] / asset[:-1] - 1 - rf
    fit = hac_regression(y, x)
    if fit is None:
        return dict(alpha=None, beta=None, t=None, p=None)
    return dict(alpha=fit["coefficients"][0] * 252, beta=fit["coefficients"][1],
                t=fit["z"][0], p=fit["p"][0])


def rank_ic(signal, forward, horizon=21):
    s, f = np.asarray(signal, float), np.asarray(forward, float)
    good = np.isfinite(s) & np.isfinite(f)
    s, f = s[good], f[good]
    if len(s) < 50 or np.ptp(s) == 0 or np.ptp(f) == 0:
        return dict(ic=None, p=None, observations=len(s))
    sx, fy = pd.Series(s).rank().to_numpy(), pd.Series(f).rank().to_numpy()
    sx, fy = (sx - sx.mean()) / sx.std(), (fy - fy.mean()) / fy.std()
    fit = hac_regression(fy, sx, lag=horizon)
    return dict(ic=float(np.mean(sx * fy)), p=fit["p"][1] if fit else None, observations=len(s))


def forward_returns(open_, close, bill_open, bill_close, horizon):
    """Decision close t -> next open t+1 -> close t+h, less matched BIL return."""
    n = len(close)
    result = np.full(n, np.nan)
    for t in range(n - horizon):
        result[t] = close[t + horizon] / open_[t + 1] - bill_close[t + horizon] / bill_open[t + 1]
    return result


def holm(pvalues):
    """Family-wise adjusted p-values; unavailable tests count in family size."""
    clean = [(i, 1. if p is None else p) for i, p in enumerate(pvalues)]
    result, previous = [1.] * len(clean), 0.
    for rank, (i, p) in enumerate(sorted(clean, key=lambda x: x[1])):
        previous = max(previous, min(1., p * (len(clean) - rank)))
        result[i] = previous
    return result
