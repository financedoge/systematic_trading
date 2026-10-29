"""Causal two-timescale regimes, adaptive windows and close-triggered protection.

Research only. Protective levels are tested at closes and filled at a later open;
they are not intraday stop orders or guaranteed prices.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import trend_modes as old
from . import trend_hmm

VERSION = 'multiscale-modes-1.0.0'
FAST = (10, 21, 42, 63)
SLOW = (63, 126, 189, 252)
DOWN, RANGE, UP, UNKNOWN = old.DOWN, old.RANGE, old.UP, old.UNKNOWN


@dataclass
class Features:
    base: old.Features
    errors: dict
    activity: np.ndarray
    volatility: np.ndarray
    hmm_models: dict = field(default_factory=dict)
    hmm_probabilities: dict = field(default_factory=dict)
    window_cache: dict = field(default_factory=dict)

    def __getattr__(self, name):
        return getattr(self.base, name)

    @classmethod
    def build(cls, data):
        base = old.Features.build(data)
        errors = {}
        log = np.log(base.close)
        scale = base.atr / base.close
        for length, values in base.cache.items():
            slope = values['regression']['up'] * scale / (length - 1)
            endpoint = old.rolling(log, length, 'mean') + slope * (length - 1) / 2
            prediction = np.r_[np.nan, (endpoint + slope)[:-1]]
            error = np.minimum(abs(log - prediction) / np.r_[np.nan, scale[:-1]], 5.)
            errors[length] = old.rolling(error, 21, 'mean')
        prior_volume = np.r_[np.nan, old.rolling(base.volume, 21, 'median')[:-1]]
        activity = np.divide(base.volume, prior_volume, out=np.full(len(log), np.nan), where=prior_volume > 0)
        prior_vol = np.r_[np.nan, old.rolling(scale, 63, 'median')[:-1]]
        volatility = np.divide(scale, prior_vol, out=np.full(len(log), np.nan), where=prior_vol > 0)
        return cls(base, errors, activity, volatility)

    def truncated(self, cutoff):
        b = self.base.truncated(cutoff)
        n = len(b.days)
        return Features(b, {k: v[:n] for k, v in self.errors.items()}, self.activity[:n], self.volatility[:n], self.hmm_models)


def windows(f, bank, adaptive, fixed, margin):
    """Completed one-step forecast errors select lengths; five-session dwell."""
    n = len(f.days)
    key=(bank,adaptive,fixed if not adaptive else None,margin)
    if key in f.window_cache:return f.window_cache[key]
    if not adaptive:
        f.window_cache[key]=np.full(n, fixed, int)
        return f.window_cache[key]
    losses = np.array([f.errors[k] + .15 * (1 - f.cache[k]['regression']['quality']) for k in bank])
    losses = np.where(np.isfinite(losses), losses, np.inf)
    best = losses.argmin(axis=0)
    chosen = np.zeros(n, int)
    current, last_switch = 0, -5
    for t in range(n):
        proposed = best[t]
        if proposed != current and t - last_switch >= 5 and losses[proposed, t] < (1 - margin) * losses[current, t]:
            current, last_switch = int(proposed), t
        chosen[t] = bank[current]
    f.window_cache[key]=chosen
    return chosen


def gather(f, lengths, key, method=None):
    out = np.full(len(f.days), np.nan)
    for length in np.unique(lengths):
        values = f.cache[int(length)]
        if method:
            values = values[method]
        mask = lengths == length
        out[mask] = values[key][mask]
    return out


def retain(raw, max_age):
    index = np.where(raw != UNKNOWN, np.arange(len(raw)), -1)
    last = np.maximum.accumulate(index)
    valid = (last >= 0) & (np.arange(len(raw)) - last <= max_age)
    state = np.full(len(raw), UNKNOWN, np.int8)
    state[valid] = raw[last[valid]]
    return state


def classify(f, p):
    adaptive = p['family'] != 'fixed'
    fast = windows(f, FAST, adaptive, p['fast'], p['margin'])
    slow = windows(f, SLOW, adaptive, p['slow'], p['margin'])
    drift = gather(f, fast, 'up', 'regression')
    quality = gather(f, fast, 'quality', 'regression')
    slow_drift = gather(f, slow, 'up', 'regression')
    slow_quality = gather(f, slow, 'quality', 'regression')
    fast_up = old.confirmed((drift >= p['up_strength']) & (quality >= p['up_quality']), p['up_confirm'])
    # Exit evidence deliberately has no volume veto and cannot lose to slow up.
    fast_down = old.confirmed((-drift >= p['down_strength']) & (quality >= p['down_quality']), p['down_confirm'])
    long_up = old.confirmed((slow_drift >= p['slow_strength']) & (slow_quality >= .1), 2)
    long_down = old.confirmed((-slow_drift >= p['slow_strength']) & (slow_quality >= .1), 2)
    context = np.full(len(f.days), UNKNOWN, np.int8)
    context[long_up], context[long_down] = UP, DOWN
    context = retain(context, 21)
    probabilities={}
    if p['family'].startswith('hmm'):
        for name,bank in (('fast',FAST),('slow',SLOW)):
            key=name+('_volume' if p['volume'] else '_price')
            if key not in f.hmm_probabilities:
                f.hmm_probabilities[key]=trend_hmm.filtered(trend_hmm.observations(f,bank,p['volume']),f.hmm_models[key])
            probabilities[name+'_probability']=f.hmm_probabilities[key]
        fast_up=probabilities['fast_probability'][:,2]>=p['up_probability']
        fast_down=probabilities['fast_probability'][:,0]>=p['down_probability']
        context=np.full(len(f.days),UNKNOWN,np.int8)
        context[probabilities['slow_probability'][:,0]>=p['slow_probability']]=DOWN
        context[probabilities['slow_probability'][:,2]>=p['slow_probability']]=UP
    # Range needs independently fitted geometry, not merely absent trend evidence.
    range_length = np.full(len(f.days), p['range_length'], int)
    flat = ((gather(f, range_length, 'flat', 'regression') <= p['range_drift'])
            & (gather(f, range_length, 'width') <= p['range_width'])
            & (gather(f, range_length, 'efficiency') <= .3))
    raw = np.full(len(f.days), UNKNOWN, np.int8)
    raw[flat], raw[fast_up], raw[fast_down] = RANGE, UP, DOWN
    state = retain(raw, 5)
    pressure = gather(f, fast, 'pressure')
    entry_up = fast_up.copy()
    if p['volume']:
        entry_up &= (pressure >= p['entry_pressure']) & (f.activity >= .7)
    prior_upper = np.r_[np.nan, gather(f, fast, 'box_upper')[:-1]]
    reversal = ((f.close > prior_upper + .5 * np.r_[np.nan, f.atr[:-1]])
                & (drift >= 2 * p['up_strength']))
    counter = context == DOWN
    eligible = entry_up & (~counter | (reversal if p['counter'] == 'confirm' else False))
    return dict(state=state, evidence=raw, context=context, fast_length=fast, slow_length=slow,
                fast_up=fast_up, fast_down=fast_down, eligible=eligible, counter=counter,
                lower=gather(f, fast, 'lower', 'regression'), upper=gather(f, fast, 'upper', 'regression'),
                slow_lower=gather(f, slow, 'lower', 'regression'), slow_upper=gather(f, slow, 'upper', 'regression'),
                parameters=p,**probabilities)


def simulate(f, cl, *, start=252, cost_bp=5., delay=0):
    if not isinstance(delay, (int, np.integer)) or delay < 0 or not 0 <= cost_bp < 10000:
        raise ValueError('Invalid execution friction')
    p, n, lag = cl['parameters'], len(f.days), 1 + delay
    desired, held = np.zeros(n, bool), np.zeros(n, bool)
    stops, reasons = np.full(n, np.nan), np.full(n, '', dtype='U24')
    target, active, peak, level = False, False, np.nan, np.nan
    entry_atr = np.nan
    protection = p['family'] in ('protected', 'stress', 'hmm_protected', 'hmm_stress')
    for t in range(start, n):
        adopted = bool(desired[t-lag]) if t >= lag else False
        if adopted and not active:
            peak = f.open[t]
            entry_atr = f.atr[t-1]
            multiplier = p['counter_atr'] if cl['counter'][t-lag] else p['stop_atr']
            level = f.open[t] - multiplier * entry_atr
        if not adopted:
            level, peak = np.nan, np.nan
        active, held[t] = adopted, adopted
        # Test the level established previously, then tighten for the next close.
        # New entry's initial level uses actual fill and previously observed ATR.
        stop_hit = active and protection and f.close[t] < level
        if target and (cl['fast_down'][t] or stop_hit):
            target = False
            reasons[t] = 'protection' if stop_hit else 'fast_down'
        elif not target and not active and cl['eligible'][t] and not cl['eligible'][t-1]:
            target = True
            reasons[t] = 'counter_up' if cl['counter'][t] else 'aligned_up'
        if active and protection:
            stops[t] = level
            peak = max(peak, f.close[t])
            multiplier = p['counter_atr'] if cl['counter'][t] else p['stop_atr']
            if p['family'] in ('stress','hmm_stress') and (f.volatility[t] >= p['vol_trigger'] or (p['volume'] and f.activity[t] >= p['volume_trigger'])):
                multiplier *= p['tighten']
            # Rising volatility may tighten, never widen the adopted stop.
            risk = min(entry_atr, f.atr[t])
            level = max(level, peak - multiplier * risk)
        desired[t] = target
    before = np.r_[False, held[:-1]]
    buy, sell = held & ~before, before & ~held
    overnight = np.r_[0., np.log(f.open[1:] / f.close[:-1])]
    fee = cost_bp / 10000
    netlog = before * overnight + held * np.log(f.close / f.open) - buy * np.log1p(fee) + sell * np.log1p(-fee)
    nav = np.full(n, np.nan)
    nav[start:] = np.exp(np.cumsum(netlog[start:]))
    changes = np.flatnonzero(desired != np.r_[False, desired[:-1]])
    events = [dict(day=int(t), side='buy' if desired[t] else 'sell', fill=int(t+lag)) for t in changes]
    entries, exits = np.flatnonzero(buy), list(np.flatnonzero(sell))
    episodes = []
    for i, a in enumerate(entries):
        x = exits[i] if i < len(exits) else None
        episodes.append(dict(entry_index=int(a), entry=float(f.open[a]), entry_signal=int(a-lag),
            exit_index=int(x) if x is not None else None, exit_price=float(f.open[x]) if x is not None else None,
            exit_signal=int(x-lag) if x is not None else None, exit_reason=str(reasons[x-lag]) if x is not None else None))
    return dict(nav=nav, desired=desired, held=held, events=events, episodes=episodes, stop=stops, reason=reasons, **cl)
