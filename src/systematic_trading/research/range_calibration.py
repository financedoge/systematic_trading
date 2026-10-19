"""Finite v2 range/exit calibration; causal signals, no execution authority.

The vectorized state machine evaluates independent parameter candidates together.
Screening uses fractional buy/hold units; finalists MUST be replayed by the shared
whole-share accountant before selection. Screens are not reported as final P&L.
"""
from dataclasses import dataclass, asdict
import itertools

import numpy as np
import pandas as pd

from systematic_trading.research.range_breakout import features

WINDOWS = (21, 42, 63, 126, 252, 504, 756, 1008, 1260)


@dataclass(frozen=True)
class RangeRule:
    basis: str
    threshold: float
    drift: float


@dataclass(frozen=True)
class ExitRule:
    initial_atr: float
    trail_basis: str
    trail: float
    range_buffer: float | None
    heat_multiplier: float = 1.


@dataclass(frozen=True)
class CalibratedRule:
    range: RangeRule
    exit: ExitRule
    volume: bool

    def record(self):
        return asdict(self)


def candidate_grid():
    ranges = [RangeRule('absolute', w, d) for w, d in
              itertools.product((.10, .15, .25, .40, .60, .80), (.35, .65))]
    ranges += [RangeRule('percentile', q, .5) for q in (.25, .5, .75)]
    exits = [ExitRule(i, 'atr', k, b) for i, k, b in
             itertools.product((2., 4., 8.), (4., 8., 12.), (.5, 2., None))]
    exits += [ExitRule(4., 'atr', 8., b, .5) for b in (.5, 2., None)]
    exits += [ExitRule(i, 'percent', d, None) for i, d in
              itertools.product((4., 8.), (.10, .20, .30))]
    return [CalibratedRule(r, e, v) for r, e, v in itertools.product(ranges, exits, (False, True))]


def range_bank(close, high, low, volume, ranges):
    """Longest qualifying window; all bands/statistics precede crossing close."""
    bank = {}
    common = None
    for L in WINDOWS:
        f = features(close, high, low, volume, L)
        x = pd.Series(np.log(close)).diff()
        compress = (x.rolling(min(63, L//3)).std().shift(1).to_numpy()
                    <= x.rolling(L-1).std().shift(1).to_numpy())
        w = pd.Series(f['width'])
        # f.width[t] already ends t-1; reference ends t-2, not current width.
        thresholds = {q: w.rolling(756, min_periods=252).quantile(q).shift(1).to_numpy()
                      for q in (.25, .5, .75)}
        for rule in ranges:
            if rule not in bank:
                bank[rule] = {k: np.full(len(close), np.nan) for k in ('upper', 'lower', 'duration')}
                bank[rule]['tight'] = np.zeros(len(close), bool)
            ceiling = np.log1p(rule.threshold) if rule.basis == 'absolute' else thresholds[rule.threshold]
            mask = ((f['width'] <= ceiling) & (f['drift'] <= rule.drift*f['width']) & compress)
            for k in ('upper', 'lower', 'duration'):
                bank[rule][k][mask] = f[k][mask]
            bank[rule]['tight'] |= mask
        common = f
    return bank, common['atr'], common['prior_volume']


def signal_grid(close, opens, high, low, volume, specs, *, details=False):
    """Independent episodes, completed-close decisions, next-open virtual entry."""
    c, o, v = (np.asarray(x, float) for x in (close, opens, volume))
    if o.shape != c.shape or not np.isfinite(o).all() or (o <= 0).any():
        raise ValueError('Unsupported opening prices')
    ranges = list(dict.fromkeys(s.range for s in specs))
    bank, atr, prior_volume = range_bank(c, high, low, v, ranges)
    ridx = np.array([ranges.index(s.range) for s in specs])
    upper = np.array([bank[r]['upper'] for r in ranges])
    lower = np.array([bank[r]['lower'] for r in ranges])
    tight = np.array([bank[r]['tight'] for r in ranges])
    duration = np.array([bank[r]['duration'] for r in ranges])
    m, n = len(specs), len(c)
    initial = np.array([s.exit.initial_atr for s in specs])
    trail = np.array([s.exit.trail for s in specs])
    percent = np.array([s.exit.trail_basis == 'percent' for s in specs])
    buffer = np.array([np.inf if s.exit.range_buffer is None else s.exit.range_buffer for s in specs])
    heat_k = np.array([s.exit.heat_multiplier for s in specs])
    require_v = np.array([s.volume for s in specs])
    age = np.full(m, -1, int)
    live, heated = np.zeros(m, bool), np.zeros(m, bool)
    u, lo, level, volref = (np.zeros(m) for _ in range(4))
    entry_atr = np.ones(m)
    peak, stop = np.zeros(m), np.zeros(m)
    fill, reset, dur = np.full(m, -1, int), np.full(m, -1, int), np.zeros(m)
    active = np.zeros((n, m), bool)
    out = dict(active=active)
    if details:
        out.update({k: np.full((n, m), np.nan) for k in ('stop', 'upper', 'lower', 'duration', 'entry_atr', 'peak')})
        out['heated'] = np.zeros((n, m), bool)
        out['exit_reason'] = np.zeros((n, m), np.int8)  # 1 range,2 initial/trail
    for t in range(1, n):
        was_live = live.copy()
        entering = was_live & (fill == t)
        peak[entering] = o[t]
        stop[entering] = o[t]-initial[entering]*entry_atr[entering]
        peak[was_live] = np.maximum(peak[was_live], c[t])
        heated |= was_live & (c[t] >= u+3*entry_atr) & (c[t] >= peak-atr[t]) & (v[t] >= 2*prior_volume[t])
        k = np.where(heated, heat_k, 1.)
        candidate = np.where(percent, peak*(1-trail*k), peak-trail*k*atr[t])
        stop[was_live] = np.maximum(stop[was_live], candidate[was_live])
        failed = was_live & (c[t] < u-buffer*entry_atr)
        stopped = was_live & (c[t] < stop)
        exited = failed | stopped
        live[exited] = False
        reset[exited] = t+21
        pending = (age >= 0) & ~was_live
        cancelled = pending & (c[t] <= level)
        age[cancelled] = -1
        confirmed = pending & ~cancelled & (t-age == 2)
        passed = confirmed & (~require_v | (np.mean(v[max(0,t-2):t+1]) >= 1.2*volref))
        live[passed], fill[passed], heated[passed] = True, t+1, False
        age[confirmed] = -1
        eligible = ~was_live & ~pending & (t > reset)
        boundary = upper[ridx, t] + .5*atr[t-1]
        crossing = eligible & tight[ridx, t] & (c[t] > boundary) & (c[t-1] <= boundary)
        age[crossing] = t
        for arr, val in ((u, upper[ridx, t]), (lo, lower[ridx, t]), (dur, duration[ridx, t]), (level, boundary)):
            arr[crossing] = val[crossing]
        entry_atr[crossing], volref[crossing] = atr[t-1], prior_volume[t]
        active[t] = live
        if details:
            tracked = was_live | passed
            for key, arr in (('stop', stop), ('upper', u), ('lower', lo), ('duration', dur), ('entry_atr', entry_atr), ('peak', peak)):
                out[key][t, tracked] = arr[tracked]
            # No fill/peak/stop exists at the confirmation close.
            for key in ('stop', 'peak'):
                out[key][t, passed] = np.nan
            out['heated'][t] = heated & tracked
            out['exit_reason'][t, stopped] = 2
            out['exit_reason'][t, failed] = 1
    return out


def fractional_screen(close, opens, active, start, *, cost=5, delay=0):
    """Fast *screen only*: held units, idle cash, next-open costs and gaps."""
    m = active.shape[1]
    cash, quantity, adopted = np.ones(m), np.zeros(m), np.zeros(m, bool)
    nav = np.ones((len(close)-start, m))
    turnover = np.zeros(m)
    trades = np.zeros(m, int)
    for t in range(start, len(close)):
        signal = t-1-delay
        desired = active[signal] if signal >= 0 else np.zeros(m, bool)
        change = desired != adopted
        sell = change & ~desired
        cash[sell] += quantity[sell]*opens[t]*(1-cost/1e4)
        turnover[sell] += 1
        trades[sell] += 1
        quantity[sell] = 0
        buy = change & desired
        amount = .98*cash[buy]
        quantity[buy] = amount/opens[t]
        cash[buy] -= amount*(1+cost/1e4)
        turnover[buy] += 1
        adopted = desired.copy()
        nav[t-start] = cash+quantity*close[t]
    return nav, trades, turnover


def panel_metrics(nav):
    nav = np.atleast_2d(nav) if np.asarray(nav).ndim == 2 else np.asarray(nav)[:, None]
    path = np.vstack([np.ones(nav.shape[1]), nav])
    r = path[1:]/path[:-1]-1
    sd = np.std(r, axis=0, ddof=1)
    sharpe = np.divide(r.mean(axis=0)*np.sqrt(252), sd, out=np.zeros_like(sd), where=sd > 1e-12)
    return dict(cagr=nav[-1]**(252/len(nav))-1, sharpe=sharpe,
                max_drawdown=np.min(path/np.maximum.accumulate(path, axis=0)-1, axis=0))


def robust_score(nav):
    """Three contiguous equal-session IS blocks, normalized without cash resets."""
    a = np.asarray(nav)
    if a.ndim == 1:
        a = a[:, None]
    blocks = np.array_split(np.arange(len(a)), 3)
    sharpes = np.array([panel_metrics(a[b]/(a[b[0]-1] if b[0] else 1))['sharpe'] for b in blocks])
    return .5*panel_metrics(a)['sharpe']+.5*np.median(sharpes, axis=0)-.25*np.std(sharpes, axis=0), sharpes


def transitions(active, days, start, policy='event'):
    """Single ETF: adopt only signal changes; fixed monthly is an explicit control."""
    result, anchor = [], None
    for t in range(len(days)-1):
        if days[t+1] < start:
            continue
        desired = bool(active[t])
        if anchor is None or (policy == 'event' and desired != anchor) or (policy == 'monthly' and days[t][:7] != days[t+1][:7]):
            result.append(t)
            anchor = desired
    return result


def select_fitted(records):
    """Only caller-supplied IS records. Guarded plateau, else descriptive fallback."""
    candidates = [r for r in records if r['evidence']]
    if not candidates:
        return None
    passing = [r for r in candidates if r['guard_pass']]
    pool = passing or candidates
    best = max(r['score'] for r in pool)
    plateau = [r for r in pool if r['score'] >= best-.03]
    return min(plateau, key=lambda r: (r['annual_turnover'], -r['score'], r['id']))
