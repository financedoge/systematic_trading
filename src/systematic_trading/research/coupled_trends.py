"""Two latent daily trend factors; exact nine-state inference, no trend windows.

Transition factorization: P(L_t | L_prev, S_prev) P(S_t | S_prev, L_t).
The independent control removes both cross-factor transition dependencies.
Persistence constraints identify the timescales; they are not lookback windows.
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from scipy.optimize import lsq_linear

from . import trend_hmm

VERSION = 'coupled-daily-trends-v1'
LONG = np.repeat(np.arange(3), 3)
SHORT = np.tile(np.arange(3), 3)
DESIGN = np.column_stack((-(LONG == 0).astype(float), LONG == 2,
                          -(SHORT == 0).astype(float), SHORT == 2)).astype(float)


@dataclass
class Features:
    days: np.ndarray
    open: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    hmm_models: dict = field(default_factory=dict)
    coupled_cache: dict = field(default_factory=dict)

    @classmethod
    def build(cls, data):
        for k in ('open', 'close', 'volume'):
            if not np.isfinite(data[k]).all() or (data[k] <= 0).any():
                raise ValueError('Complete positive audited observations required')
        return cls(np.asarray(data['days'], dtype='datetime64[D]'),
                   *[np.asarray(data[k], float) for k in ('open', 'close', 'volume')])

    def truncated(self, cutoff):
        n = int(np.sum(self.days <= np.datetime64(cutoff)))
        return Features(self.days[:n], self.open[:n], self.close[:n], self.volume[:n], self.hmm_models)


def fit_models(f):
    data = dict(close=f.close, volume=f.volume)
    return {f'{int(c)}_{int(v)}': fit(observations(data, v)[1:], coupled=c)
            for c in (False, True) for v in (False, True)}


def observations(data, volume=False):
    close = np.asarray(data['close'], float)
    columns = [np.r_[np.nan, np.log(close[1:] / close[:-1])]]
    if volume:
        v = np.asarray(data['volume'], float)
        if not np.isfinite(v).all() or (v <= 0).any():
            raise ValueError('Audited positive raw volume required; no substitution')
        columns.append(np.r_[np.nan, np.log(v[1:] / v[:-1])])
    return np.column_stack(columns)


def transition(long, short):
    # long[i,j,k], short[j,k,l]; joint (i,j) -> (k,l).
    a = long[:, :, :, None] * short[None, :, :, :]
    return a.reshape(9, 9)


def bounded_rows(counts, own_axis, low, high):
    out = counts / counts.sum(axis=-1, keepdims=True)
    for idx in np.ndindex(out.shape[:-1]):
        own = idx[own_axis]
        stay = np.clip(out[idx][own], low, high)
        mask = np.arange(3) != own
        out[idx][mask] *= (1 - stay) / out[idx][mask].sum()
        out[idx][own] = stay
    return out


def update_transitions(xi, coupled):
    counts = xi.reshape(3, 3, 3, 3)
    lc = counts.sum(axis=3)
    sc = counts.sum(axis=0)
    if not coupled:
        lc = np.repeat(lc.sum(axis=1, keepdims=True) / 3, 3, axis=1)
        sc = np.repeat(sc.sum(axis=1, keepdims=True) / 3, 3, axis=1)
    lp = np.full((3, 3, 3), .1)
    sp = np.full((3, 3, 3), .1)
    for i in range(3):
        lp[i, :, i] += 30.
        sp[i, :, i] += 3.
    return bounded_rows(lc + lp, 0, .98, .999), bounded_rows(sc + sp, 0, .65, .97)


def fit(x, *, coupled, iterations=20):
    x = np.asarray(x, float)
    if len(x) < 500 or not np.isfinite(x).all():
        raise ValueError('At least 500 complete training observations required')
    scale = np.maximum(x.std(axis=0), 1e-6)
    z = np.clip(x / scale, -5, 5)  # Preserve zero return as zero drift.
    best = None
    for amplitude in (.18, .4):
        coef = np.array([.08, .08, amplitude, amplitude])
        means = np.zeros((9, z.shape[1])); means[:, 0] = DESIGN @ coef
        variance = np.ones(z.shape[1])
        long, short = update_transitions(np.eye(9) * 10, coupled)
        long[:] = .0025
        short[:] = .04
        for i in range(3):
            long[i, :, i] = .995; short[i, :, i] = .92
        initial = np.ones(9) / 9
        for iteration in range(iterations):
            a = transition(long, short)
            gamma, xi, ll = trend_hmm.expectation(
                trend_hmm.emissions(z, means, np.broadcast_to(variance, means.shape)), initial, a)
            # Priors stabilize sparsely observed conditional transitions.
            objective = ll + 30 * np.log(long[np.arange(3), :, np.arange(3)]).sum()
            objective += 3 * np.log(short[np.arange(3), :, np.arange(3)]).sum()
            objective += .1 * (np.log(long).sum() + np.log(short).sum())
            if best is None or objective > best['objective']:
                best = dict(scale=scale.tolist(), means=means.tolist(), variance=variance.tolist(),
                            long=long.tolist(), short=short.tolist(), transition=a.tolist(),
                            initial=initial.tolist(), coefficients=coef.tolist(), coupled=coupled,
                            log_likelihood=ll, objective=objective, iteration=iteration,
                            initialization=amplitude, training_rows=len(x))
            weights = gamma.sum(axis=0) + 1e-9
            target = gamma.T @ z / weights[:, None]
            coef = lsq_linear(DESIGN * np.sqrt(weights[:, None]),
                              target[:, 0] * np.sqrt(weights), bounds=(.015, 1.5)).x
            means[:, 0] = DESIGN @ coef
            if z.shape[1] > 1:
                means[:, 1:] = target[:, 1:]
            variance = np.maximum(
                (gamma[:, :, None] * (z[:, None, :] - means[None, :, :])**2).sum(axis=(0, 1)) / len(z), .1)
            long, short = update_transitions(xi, coupled)
            initial = (gamma[0] + .1) / (1 + .9)
    return best


def filtered(x, model):
    x = np.asarray(x, float)
    if not np.isfinite(x[1:]).all():
        raise ValueError('Missing observation after initial return; no fill')
    z = np.clip(x[1:] / np.asarray(model['scale']), -5, 5)
    means = np.array(model['means'])
    alpha, _, _, ll = trend_hmm.forward(
        trend_hmm.emissions(z, means, np.broadcast_to(model['variance'], means.shape)),
        np.array(model['initial']), np.array(model['transition']))
    joint = np.vstack([np.full(9, 1 / 9), alpha])
    long = joint.reshape(-1, 3, 3).sum(axis=2)
    short = joint.reshape(-1, 3, 3).sum(axis=1)
    mu = means[:, 0] * model['scale'][0]
    prediction = joint @ np.asarray(model['transition'])
    return dict(joint=joint, slow_probability=long, fast_probability=short,
                drift=joint @ mu, forecast_drift=prediction @ mu,
                slow_drift=long @ np.array([-model['coefficients'][0], 0, model['coefficients'][1]]) * model['scale'][0],
                log_likelihood=ll)


def classify(f, p):
    model = f.hmm_models[f"{int(p['coupled'])}_{int(p['volume'])}"]
    cachekey = (p['coupled'], p['volume'])
    if cachekey not in f.coupled_cache:
        data = dict(close=f.close, volume=f.volume)
        f.coupled_cache[cachekey] = filtered(observations(data, p['volume']), model)
    q = f.coupled_cache[cachekey]
    aligned = q['slow_probability'][:, 2] >= .55
    counter = q['slow_probability'][:, 0] >= .55
    threshold = np.where(aligned & p['context'], p['aligned_exit'], p['exit'])
    up = q['fast_probability'][:, 2] >= p['entry']
    eligible = up & (q['forecast_drift'] > 0)
    down = q['fast_probability'][:, 0] >= threshold
    state = np.where(down, -1, np.where(up, 1, 0))
    context = np.where(counter, -1, np.where(aligned, 1, 0))
    return dict(**q, state=state, context=context, eligible=eligible, fast_down=down,
                aligned=aligned, counter=counter, parameters=p, sigma=model['scale'][0])


def simulate(f, cl, *, start=252, cost_bp=5, delay=0):
    if not isinstance(delay, (int, np.integer)) or delay < 0 or not 0 <= cost_bp < 10000:
        raise ValueError('Invalid friction')
    p, n, lag = cl['parameters'], len(f.days), 1 + delay
    desired, held = np.zeros(n, bool), np.zeros(n, bool)
    stops, reasons = np.full(n, np.nan), np.full(n, '', dtype='U24')
    target, active, armed = False, False, True
    peak, level, entry_risk = np.nan, np.nan, np.nan
    for t in range(start, n):
        adopted = bool(desired[t-lag])
        multiplier = p['wide'] if p['context'] and cl['aligned'][t] else p['tight']
        if adopted and not active:
            peak = f.open[t]
            # Daily fitted return dispersion; no rolling trend window or future ATR.
            entry_risk = f.open[t] * cl['sigma']
            known_mult = p['wide'] if p['context'] and cl['aligned'][t-lag] else p['tight']
            level = f.open[t] - known_mult * entry_risk
        if not adopted:
            level, peak = np.nan, np.nan
        active, held[t] = adopted, adopted
        if cl['fast_probability'][t, 2] < p['reset']:
            armed = True
        stop_hit = active and f.close[t] < level
        if target and (cl['fast_down'][t] or stop_hit):
            target, armed = False, False
            reasons[t] = 'protection' if stop_hit else 'fast_down'
        elif not target and not active and armed and cl['eligible'][t]:
            target, armed = True, False
            reasons[t] = 'counter_up' if cl['counter'][t] else 'fast_up'
        if active:
            stops[t] = level
            peak = max(peak, f.close[t])
            level = max(level, peak - multiplier * entry_risk)
        desired[t] = target
    before = np.r_[False, held[:-1]]
    buy, sell = held & ~before, before & ~held
    fee = cost_bp / 10000
    overnight = np.r_[0., np.log(f.open[1:] / f.close[:-1])]
    netlog = before * overnight + held * np.log(f.close / f.open) - buy * np.log1p(fee) + sell * np.log1p(-fee)
    nav = np.full(n, np.nan); nav[start:] = np.exp(np.cumsum(netlog[start:]))
    changes = np.flatnonzero(desired != np.r_[False, desired[:-1]])
    events = [dict(day=int(t), side='buy' if desired[t] else 'sell', fill=int(t+lag)) for t in changes]
    entries, exits = np.flatnonzero(buy), list(np.flatnonzero(sell))
    episodes = []
    for i, a in enumerate(entries):
        x = exits[i] if i < len(exits) else None
        episodes.append(dict(entry_index=int(a), entry=float(f.open[a]), entry_signal=int(a-lag),
                             exit_index=int(x) if x is not None else None,
                             exit_price=float(f.open[x]) if x is not None else None,
                             exit_signal=int(x-lag) if x is not None else None,
                             exit_reason=str(reasons[x-lag]) if x is not None else None))
    return dict(nav=nav, desired=desired, held=held, events=events, episodes=episodes,
                stop=stops, reason=reasons, **cl)
