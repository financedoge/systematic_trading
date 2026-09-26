"""Causal, research-only trading-activity concentration overlays (not net flows).

No fit, broker access, registry promotion, or production strategy mutation. Inputs
must be synchronous completed daily bars strictly before the decision session.
"""
from __future__ import annotations

import math
from decimal import Decimal
from statistics import fmean, pstdev
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from systematic_trading.domain.portfolio import AllocationTarget


class FlowConcentrationSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: Literal['activity-concentration-v1'] = 'activity-concentration-v1'
    measure: Literal['relative_dollar_activity', 'relative_volume', 'hhi_component'] = 'relative_dollar_activity'
    derivative: Literal[1, 2] = 2
    normalization_bars: int = Field(default=63, ge=21, le=126)
    smoothing_span: int = Field(default=10, ge=3, le=42)
    difference_lag: int = Field(default=10, ge=2, le=42)
    noise_bars: int = Field(default=126, ge=63, le=252)
    threshold: float = Field(default=0.5, gt=0, le=3, allow_inf_nan=False)
    directional_confirmation: bool = True
    hurst_min: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    action: Literal['tilt', 'gate'] = 'tilt'
    relative_tilt: float = Field(default=0.15, gt=0, le=0.3, allow_inf_nan=False)
    active_cap: float = Field(default=0.03, gt=0, le=0.06, allow_inf_nan=False)


class ActivityConcentrationOverlay:
    name = "etf-activity-lag20"

    def __init__(self, spec: FlowConcentrationSpec):
        self.spec = spec
        self.state = {}

    def apply(self, targets, context):
        return apply_concentration_targets(list(targets), concentration_features(context.bars_by_symbol, self.spec),
                                           self.spec, self.state)


def finite_difference(values: list[float], lag: int, order: int) -> float:
    if order not in (1, 2) or lag < 1 or len(values) <= lag * order:
        raise ValueError('Insufficient observations or invalid finite difference')
    if order == 1:
        return (values[-1] - values[-1-lag]) / lag
    return (values[-1] - 2 * values[-1-lag] + values[-1-2*lag]) / lag**2


def hurst_estimate(log_prices: list[float]) -> float | None:
    """Variance-scaling diagnostic on 252 unsmoothed log prices; not a test of memory."""
    if len(log_prices) < 252:
        return None
    values = log_prices[-252:]
    pairs = []
    for lag in (2, 4, 8, 16, 32):
        scale = pstdev([values[i] - values[i-lag] for i in range(lag, len(values))])
        if scale <= 1e-12:
            return None
        pairs.append((math.log(lag), math.log(scale)))
    mx, my = fmean(x for x, _ in pairs), fmean(y for _, y in pairs)
    return sum((x-mx)*(y-my) for x, y in pairs) / sum((x-mx)**2 for x, _ in pairs)


def concentration_features(histories: dict, spec: FlowConcentrationSpec) -> dict:
    """Compute latest features with finite causal warmup and lagged noise scale.

    The normalization denominator excludes today's activity. The EMA uses a
    fixed trailing warmup of five spans before the noise-estimation interval.
    Scores are raw derivatives / PRIOR derivative std (no future centering).
    """
    symbols = sorted(histories)
    if len(symbols) < 2:
        raise ValueError('Concentration requires at least two assets')
    n = len(histories[symbols[0]])
    need = spec.normalization_bars + 5*spec.smoothing_span + 2*spec.difference_lag + spec.noise_bars + 1
    if n < need or (spec.hurst_min is not None and n < 252):
        raise ValueError(f'Concentration needs {max(need, 252 if spec.hurst_min is not None else 0)} prior sessions; got {n}')
    dates = [r.trade_date for r in histories[symbols[0]][-need:]]
    for rows in histories.values():
        if len(rows) != n or [r.trade_date for r in rows[-need:]] != dates:
            raise ValueError('Concentration histories must have identical sessions')
        if any(r.volume <= 0 or r.close <= 0 for r in rows[-need:]):
            raise ValueError('Concentration rejects nonpositive activity')
    activity = {
        s: [float(r.volume) * (1 if spec.measure == 'relative_volume' else float(r.close))
            for r in histories[s][-need:]] for s in symbols
    }
    norm = spec.normalization_bars
    running = {s: sum(a[:norm]) for s, a in activity.items()}
    smoothed = {s: [] for s in symbols}
    alpha = 2 / (spec.smoothing_span + 1)
    latest_shares = {}
    for i in range(norm, need):
        relative = {s: activity[s][i] / (running[s] / norm) for s in symbols}
        total = sum(relative.values())
        latest_shares = {s: v/total for s, v in relative.items()}
        for s in symbols:
            value = latest_shares[s] ** (2 if spec.measure == 'hhi_component' else 1)
            prior = smoothed[s][-1] if smoothed[s] else value
            smoothed[s].append(alpha*value + (1-alpha)*prior)
            running[s] += activity[s][i] - activity[s][i-norm]
    result = {}
    for s in symbols:
        smooth = smoothed[s]
        lag = spec.difference_lag
        prior_derivatives = [finite_difference(smooth[:j], lag, spec.derivative)
                             for j in range(len(smooth)-spec.noise_bars, len(smooth))]
        noise = pstdev(prior_derivatives)
        derivative = finite_difference(smooth, lag, spec.derivative)
        z = derivative/noise if noise > 1e-12 else 0.0
        bars = histories[s]
        recent = bars[-20:]
        signed = sum(r.volume * (1 if r.close > bars[n-21+i].close else -1 if r.close < bars[n-21+i].close else 0)
                     for i, r in enumerate(recent)) / sum(r.volume for r in recent)
        slope = finite_difference(smooth, lag, 1)
        momentum = float(bars[-1].close / bars[-21].close - 1)
        hurst = hurst_estimate([math.log(float(r.close)) for r in bars[-252:]]) if spec.hurst_min is not None else None
        confirm = not spec.directional_confirmation or (slope > 0 and momentum > 0 and signed > 0)
        persistent = spec.hurst_min is None or (hurst is not None and hurst > spec.hurst_min)
        signal = 1 if z > spec.threshold and confirm and persistent else (-1 if z < -spec.threshold else 0)
        result[s] = dict(share=latest_shares[s], concentration=smoothed[s][-1],
                         hhi=sum(v*v for v in latest_shares.values()), velocity=slope,
                         derivative=derivative, prior_noise=noise, z=z, momentum_20=momentum,
                         signed_volume_20=signed, hurst=hurst, signal=signal,
                         known_through=str(bars[-1].trade_date))
    return result


def apply_concentration_targets(targets: list[AllocationTarget], features: dict,
                                spec: FlowConcentrationSpec,
                                gate_state: dict[str, bool] | None = None) -> list[AllocationTarget]:
    """Tilt within SOTA's selected basket; gate exits go to cash, without redistribution.

    Gate state is updated at scheduled decisions only, starts out of the asset,
    and retains its prior state in the threshold dead band. Tilt preserves base
    gross exposure, a 45% weight cap and 3pp active bounds by bounded projection.
    """
    weights = {t.symbol: t.target_weight for t in targets}
    if spec.action == 'gate':
        if gate_state is None:
            raise ValueError('Gate requires explicit replayable state')
        for symbol, row in features.items():
            if row['signal']:
                gate_state[symbol] = row['signal'] > 0
        adjusted = {s: w if gate_state.get(s, False) else Decimal(0) for s, w in weights.items()}
    else:
        cap, tilt = Decimal(str(spec.active_cap)), Decimal(str(spec.relative_tilt))
        lower = {s: max(Decimal(0), w-cap) if w > 0 else Decimal(0) for s, w in weights.items()}
        upper = {s: min(max(Decimal('0.45'), w), w+cap) if w > 0 else Decimal(0) for s, w in weights.items()}
        # An inherited base weight above 45% is never increased by this overlay.
        adjusted = {s: min(upper[s], max(lower[s], w*(1+tilt*features[s]['signal']))) for s, w in weights.items()}
        target_total = sum(weights.values())
        for _ in range(len(weights)+2):
            residual = target_total - sum(adjusted.values())
            if abs(residual) < Decimal('1e-24'):
                break
            room = {s: (upper[s]-w if residual > 0 else w-lower[s]) for s, w in adjusted.items()}
            total_room = sum(room.values())
            if total_room <= 0:
                raise ValueError('Infeasible concentration weight constraints')
            for s in adjusted:
                adjusted[s] += residual*room[s]/total_room
    return [t.model_copy(update={'target_weight': adjusted[t.symbol],
                                'rationale': t.rationale + f'; research activity {spec.action} signal={features[t.symbol]["signal"]}'})
            for t in targets]
