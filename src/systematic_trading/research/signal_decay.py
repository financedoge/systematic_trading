"""Signal decay and information-coefficient instrumentation.

A diagnostic layer, not a strategy. It measures whether the signals the
application already trades still predict forward returns, and how quickly that
predictive content fades.

Conventions
-----------
* A signal value at decision date ``d`` may use only information available at
  that close. Forward returns are labels and are never read before ``d``.
* Labels use the executable convention: the next session's adjusted open to the
  open ``horizon`` sessions later. The platform decides at the close and fills
  at the next open, so a close-to-close label would credit return the strategy
  cannot capture.
* Rank IC is Spearman's rho across the candidate pool on one decision date,
  computed as the Pearson correlation of the platform's own normalised ranks so
  the diagnostic and the strategies agree on what a rank means.
* Forward windows overlap at the longer horizons, so per-date IC values are not
  independent. Intervals therefore use a circular block bootstrap over decision
  dates at the platform's 3/6/12-month blocks, never a naive t-statistic.
"""
from __future__ import annotations

from datetime import date
import math
from typing import Any, Mapping, Sequence

import numpy as np

from systematic_trading.signals.trend import _rank_metric

HORIZONS = (1, 5, 10, 21, 63)
BLOCKS = (3, 6, 12)
MIN_NAMES = 4
MIN_DATES = 12

# Predeclared status thresholds. Set before outcomes were inspected.
#   decayed    long-run IC is at or below the breakeven IC, or the recent mean IC
#              has fallen to a non-positive level.
#   weakening  recent mean IC has lost at least this share of the long-run level
#              while remaining positive.
#   healthy    everything else with enough evidence to judge.
WEAKENING_RETENTION = 0.50
RECENT_DATES = 24


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rank_ic(signal: Mapping[str, Any], forward: Mapping[str, Any]) -> float | None:
    """Spearman rank IC across one decision date, or None when undefined.

    Requires at least ``MIN_NAMES`` symbols observed in both series with finite
    values. Ties are averaged, matching the strategies' own rank handling.
    """
    common = {s: _as_float(signal.get(s)) for s in signal}
    common = {s: v for s, v in common.items() if v is not None and _as_float(forward.get(s)) is not None}
    if len(common) < MIN_NAMES:
        return None
    from decimal import Decimal
    left = _rank_metric({s: Decimal(str(v)) for s, v in common.items()})
    right = _rank_metric({s: Decimal(str(_as_float(forward[s]))) for s in common})
    if left is None or right is None:
        return None
    symbols = sorted(common)
    x = np.array([float(left[s]) for s in symbols])
    y = np.array([float(right[s]) for s in symbols])
    if x.std() == 0.0 or y.std() == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def row_value(row: Any, name: str) -> Any:
    """Read a field from a mapping row or an attribute row, whichever is used."""
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


def forward_return(
    bars: Sequence[Any], decision_index: int, horizon: int
) -> float | None:
    """Next-open to next-open adjusted return over ``horizon`` sessions.

    ``bars`` is that symbol's session-ordered history up to and including the
    decision date; ``decision_index`` is its position. Returns None when the
    forward window is not yet observed, never a partial or inferred value.
    """
    if horizon < 1:
        raise ValueError("horizon must be positive")
    entry, exit_ = decision_index + 1, decision_index + 1 + horizon
    if entry >= len(bars) or exit_ >= len(bars):
        return None
    start = _as_float(row_value(bars[entry], "open") if row_value(bars[entry], "open") is not None
                      else row_value(bars[entry], "adjusted_open"))
    end = _as_float(row_value(bars[exit_], "open") if row_value(bars[exit_], "open") is not None
                    else row_value(bars[exit_], "adjusted_open"))
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1.0


def block_bootstrap_mean(
    values: Sequence[float | None],
    *,
    blocks: Sequence[int] = BLOCKS,
    replications: int = 20000,
    seed: int = 20261010,
) -> dict[int, dict[str, Any]]:
    """Circular block bootstrap for the mean of a per-date series.

    Missing dates stay in their calendar slot and simply contribute nothing, so
    an unavailable decision never silently shrinks the sample.
    """
    array = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    valid = np.isfinite(array)
    count = int(valid.sum())
    rng = np.random.default_rng(seed)
    out: dict[int, dict[str, Any]] = {}
    for block in blocks:
        if count < MIN_DATES:
            out[block] = dict(n=count, mean=None, ci95=None, insufficient=True)
            continue
        totals = np.where(valid, array, 0.0)
        mean = float(totals.sum() / count)
        draws = []
        for offset in range(0, replications, 500):
            size = min(500, replications - offset)
            starts = rng.integers(0, len(array), size=(size, math.ceil(len(array) / block)))
            index = ((starts[:, :, None] + np.arange(block)) % len(array)).reshape(size, -1)[:, :len(array)]
            weights = np.zeros((size, len(array)))
            np.add.at(weights, (np.repeat(np.arange(size), len(array)), index.ravel()), 1)
            denom = weights @ valid.astype(float)
            draws.append(np.divide(weights @ totals, denom, out=np.full(size, np.nan), where=denom > 0))
        sample = np.concatenate(draws)
        sample = sample[np.isfinite(sample)]
        out[block] = dict(n=count, mean=mean,
                          ci95=np.quantile(sample, [0.025, 0.975]).tolist() if sample.size else None,
                          insufficient=False)
    return out


def half_life(curve: Mapping[int, float | None]) -> float | None:
    """Sessions for IC to halve, from an exponential fit to the decay curve.

    Returns None when the curve is flat or rising, or when the implied half-life
    is longer than ten times the widest measured horizon — that is "no decay
    detected in this window", which must not be reported as a large number.
    """
    points = [(h, v) for h, v in sorted(curve.items()) if v is not None and v > 0]
    if len(points) < 3:
        return None
    x = np.array([h for h, _ in points], dtype=float)
    y = np.log(np.array([v for _, v in points], dtype=float))
    slope, _ = np.polyfit(x, y, 1)
    if slope >= -1e-6:
        return None
    estimate = float(math.log(2) / -slope)
    return None if estimate > 10 * max(curve) else estimate


def breakeven_ic(
    turnover: float,
    sigma: float,
    cost_bps: float = 5.0,
    period_sessions: int = 21,
) -> float | None:
    """Rank IC required for a signal's edge to cover its trading cost.

    ``turnover`` is annual one-way turnover and ``sigma`` is the standard
    deviation of the forward return over ``period_sessions`` sessions, so the
    annual cost is first scaled to the same period before the comparison.

    A long-only top-slot rule captures roughly ``IC * sigma`` of expected
    per-period edge. The selection-intensity multiplier of the fundamental law is
    deliberately omitted, which makes this a conservative gate: it understates
    how much a strongly concentrated portfolio could earn, so clearing it is
    necessary rather than sufficient.
    """
    if sigma is None or sigma <= 0 or turnover < 0 or period_sessions <= 0:
        return None
    per_period_cost = (cost_bps / 10000.0) * turnover * (period_sessions / 252.0)
    return float(per_period_cost / sigma)


def decay_status(
    long_run: float | None,
    recent: float | None,
    breakeven: float | None,
    *,
    observations: int,
) -> dict[str, Any]:
    """Classify a signal from its long-run and recent mean IC."""
    if long_run is None or recent is None or observations < MIN_DATES:
        return dict(status="insufficient", reason="not enough usable decision dates to judge")
    if breakeven is not None and long_run <= breakeven:
        return dict(status="decayed",
                    reason=f"long-run IC {long_run:.4f} is at or below the breakeven IC {breakeven:.4f}")
    if recent <= 0:
        return dict(status="decayed", reason=f"recent mean IC {recent:.4f} is non-positive")
    if long_run > 0 and recent < long_run * WEAKENING_RETENTION:
        return dict(status="weakening",
                    reason=f"recent mean IC {recent:.4f} retains under "
                           f"{WEAKENING_RETENTION:.0%} of the long-run {long_run:.4f}")
    return dict(status="healthy",
                reason=f"recent mean IC {recent:.4f} against long-run {long_run:.4f}")


def summarise_signal(
    *,
    name: str,
    label: str,
    ic_by_horizon: Mapping[int, Sequence[float | None]],
    turnover: float | None,
    sigma: float | None,
    cost_bps: float = 5.0,
    period_sessions: int = 21,
) -> dict[str, Any]:
    """Full decay record for one signal, including intervals and status."""
    curve: dict[int, float | None] = {}
    intervals: dict[int, Any] = {}
    counts: dict[int, int] = {}
    for horizon in sorted(ic_by_horizon):
        series = ic_by_horizon[horizon]
        usable = [v for v in series if v is not None]
        counts[horizon] = len(usable)
        curve[horizon] = float(np.mean(usable)) if usable else None
        intervals[horizon] = block_bootstrap_mean(series)
    primary = min(HORIZONS)
    series = list(ic_by_horizon.get(primary, []))
    usable = [v for v in series if v is not None]
    recent_series = [v for v in series[-RECENT_DATES:] if v is not None]
    long_run = float(np.mean(usable)) if usable else None
    recent = float(np.mean(recent_series)) if recent_series else None
    dispersion = float(np.std(usable, ddof=1)) if len(usable) > 1 else None
    hit = float(sum(1 for v in usable if v > 0) / len(usable)) if usable else None
    breakeven = (breakeven_ic(turnover, sigma, cost_bps, period_sessions)
                 if turnover is not None and sigma else None)
    return dict(
        name=name,
        label=label,
        horizons=sorted(ic_by_horizon),
        ic_curve=curve,
        ic_intervals={str(h): v for h, v in intervals.items()},
        observations=counts,
        long_run_ic=long_run,
        recent_ic=recent,
        ic_ir=(long_run / dispersion) if (long_run is not None and dispersion) else None,
        hit_rate=hit,
        half_life_sessions=half_life(curve),
        turnover=turnover,
        breakeven_ic=breakeven,
        **decay_status(long_run, recent, breakeven, observations=counts.get(primary, 0)),
    )


def decision_index(bars: Sequence[Any], day: str) -> int | None:
    """Position of ``day`` in a symbol's session-ordered history."""
    for index, row in enumerate(bars):
        if str(row_value(row, "trade_date")) == str(day):
            return index
    return None


def orientation(signal: Mapping[str, Any], forward: Mapping[str, Any], ic: float | None) -> float:
    """Sign convention helper: a signal is used long-high by default."""
    return 1.0 if ic is None or ic >= 0 else -1.0


def sessions_between(first: str, second: str) -> int:
    """Calendar-day gap, used only for reporting cadence, never for labels."""
    return (date.fromisoformat(str(second)) - date.fromisoformat(str(first))).days
