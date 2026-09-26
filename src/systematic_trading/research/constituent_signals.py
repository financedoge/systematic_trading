"""Research-only stock participation features and bounded SPY target overlays."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SIGNALS = ('concentration', 'breadth', 'breadth_change', 'participation', 'signed_activity')
WINDOW = 211  # EMA warmup 64 + 20-session difference stencil + 126 prior noise values.


class ConstituentOverlaySpec(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: Literal['constituent-proxy-v1'] = 'constituent-proxy-v1'
    signal: Literal['concentration', 'breadth', 'breadth_change', 'participation',
                    'signed_activity', 'composite', 'price_control'] = 'composite'
    holdings_lag_days: Literal[45, 60] = 45
    min_value_coverage: float = Field(default=.95, ge=.9, le=1, allow_inf_nan=False)
    min_name_coverage: float = Field(default=.70, ge=.7, le=1, allow_inf_nan=False)
    relative_tilt: float = Field(default=.15, gt=0, le=.15, allow_inf_nan=False)
    active_cap: float = Field(default=.03, gt=0, le=.03, allow_inf_nan=False)
    stage: Literal['late', 'early', 'selection', 'tree'] = 'late'
    selection_boost: float = Field(default=.15, gt=0, le=.15, allow_inf_nan=False)
    tree_inputs: Literal['joint', 'price'] = 'joint'


def threshold(value: float, band: float) -> int:
    return 1 if value > band else -1 if value < -band else 0


def cohort_features(close, volume, adjusted, sector_ids, values, identity_valid):
    """One causal 211-session window; missing names remain in coverage denominators.

    The same dated cohort and same complete-observation subset are used throughout
    each feature's backward stencil. No returns after the feature date are read.
    """
    import numpy as np

    if close.shape != volume.shape or close.shape != adjusted.shape or close.shape[0] != WINDOW:
        raise ValueError('Features require matching 211-session stock matrices')
    weights = np.asarray(values, dtype=float)
    sectors = np.asarray(sector_ids, dtype=int)
    if len(weights) != close.shape[1] or np.any(~np.isfinite(weights)) or np.any(weights <= 0):
        raise ValueError('Every expected constituent needs a positive snapshot value')
    valid = (np.isfinite(close) & (close > 0) & np.isfinite(adjusted) & (adjusted > 0)
             & np.isfinite(volume) & (volume >= 0)).all(axis=0) & np.asarray(identity_valid, dtype=bool)
    coverage = dict(value_coverage=float(weights[valid].sum()/weights.sum()),
                    name_coverage=float(valid.mean()), expected_names=len(weights), observed_names=int(valid.sum()))
    if valid.sum() < 2:
        return dict(**coverage, values=None, scores=None)
    c, v, a, w, sec = close[:, valid], volume[:, valid], adjusted[:, valid], weights[valid], sectors[valid]
    activity = c*v
    sector_activity = np.column_stack([activity[:, sec == i].sum(axis=1) for i in range(11)])
    if np.any(sector_activity.sum(axis=1) <= 0) or activity[-21:].sum() <= 0:
        return dict(**coverage, values=None, scores=None)
    shares = sector_activity/sector_activity.sum(axis=1, keepdims=True)
    hhi = (shares**2).sum(axis=1)
    smooth = hhi.copy()
    for i in range(1, len(smooth)):
        smooth[i] = (2/11)*hhi[i] + (9/11)*smooth[i-1]
    accel = (smooth[20:]-2*smooth[10:-10]+smooth[:-20])/100
    noise = float(np.std(accel[-127:-1]))
    z = float(accel[-1]/noise) if noise > 1e-12 else 0.0
    breadth = float((a[-1] > a[-126:].mean(axis=0)).mean())
    prior_breadth = float((a[-21] > a[-146:-20].mean(axis=0)).mean())
    momentum = a[-1]/a[-64]-1
    participation = float(momentum.mean()-np.average(momentum, weights=w))
    signed = float((np.sign(np.diff(a[-22:], axis=0))*activity[-21:]).sum()/activity[-21:].sum())
    values_out = dict(hhi=float(hhi[-1]), hhi_smoothed=float(smooth[-1]),
        hhi_velocity=float((smooth[-1]-smooth[-11])/10), hhi_acceleration=float(accel[-1]),
        concentration_z=z, breadth=breadth, breadth_change=breadth-prior_breadth,
        participation=participation, signed_activity=signed)
    scores = dict(concentration=threshold(z, .5), breadth=threshold(breadth-.5, .05),
        breadth_change=threshold(breadth-prior_breadth, .03),
        participation=threshold(participation, .02), signed_activity=threshold(signed, .05))
    scores['composite'] = sum(scores.values())/len(SIGNALS)
    sector_coverage = {str(i): float(weights[valid & (sectors == i)].sum()/weights[sectors == i].sum())
                       if np.any(sectors == i) else None for i in range(11)}
    return dict(**coverage, values=values_out, scores=scores, sector_value_coverage=sector_coverage)


def selected_score(features: dict, day: date, known_through: str, spec: ConstituentOverlaySpec) -> float:
    row = features.get(str(spec.holdings_lag_days), {}).get(known_through)
    if row is None:
        return 0.0
    cutoff = date.fromisoformat(known_through)
    if cutoff >= day or row['known_through'] != known_through or (day-cutoff).days > 7:
        raise ValueError('Constituent observation is future-dated, stale or inconsistent')
    if row['assumed_available'] > known_through or row['snapshot'] > known_through:
        raise ValueError('Constituent cohort is not available under the modeled publication lag')
    if row['value_coverage'] < spec.min_value_coverage or row['name_coverage'] < spec.min_name_coverage:
        return 0.0
    if row.get('scores') is None:
        return 0.0
    score = float(row['scores'][spec.signal])
    if not -1 <= score <= 1:
        raise ValueError('Invalid constituent signal score')
    return score


def apply_constituent_targets(targets, score: float, spec: ConstituentOverlaySpec):
    """Adjust an already selected SPY sleeve, preserving gross and bounded weights."""
    if not -1 <= score <= 1:
        raise ValueError('Signal score outside [-1, 1]')
    weights = {t.symbol: t.target_weight for t in targets}
    base = weights.get('SPY', Decimal(0))
    if not base or not score:
        return targets
    cap = Decimal(str(spec.active_cap))
    delta = min(cap, max(-cap, base*Decimal(str(spec.relative_tilt))*Decimal(str(score))))
    delta = min(max(Decimal('.45')-base, Decimal(0)), delta) if delta > 0 else max(-base, delta)
    others = {s: w for s, w in weights.items() if s != 'SPY' and w > 0}
    room = {s: min(cap, w if delta > 0 else max(Decimal('.45')-w, Decimal(0))) for s, w in others.items()}
    possible = sum(room.values(), Decimal(0))
    delta = min(delta, possible) if delta > 0 else max(delta, -possible)
    adjusted = dict(weights)
    adjusted['SPY'] += delta
    remaining = abs(delta)
    # Proportional redistribution with per-asset room; unchanged total exposure.
    while remaining > Decimal('1e-24'):
        eligible = {s: others[s] for s in others if room[s] > Decimal('1e-24')}
        total = sum(eligible.values(), Decimal(0))
        if not total:
            raise ValueError('Infeasible constituent overlay bounds')
        moves = {s: min(room[s], remaining*w/total) for s, w in eligible.items()}
        for s, move in moves.items():
            adjusted[s] += -move if delta > 0 else move
            room[s] -= move
        remaining -= sum(moves.values())
    return [t.model_copy(update=dict(target_weight=adjusted[t.symbol],
        rationale=t.rationale+f'; research US constituent proxy {spec.signal}={score:g}')) for t in targets]
