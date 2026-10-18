"""Causal daily range-breakout factor; no data acquisition or execution authority.

Every row is a completed-close observation. Its target can first execute at the
following open. Virtual signal episodes are separate from portfolio holdings.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import rankdata


@dataclass(frozen=True)
class BreakoutSpec:
    lookback: int | str = 'adaptive'
    volume_confirmation: bool = True
    heat_exit: bool = True

    @property
    def key(self):
        return f'L{self.lookback}-V{int(self.volume_confirmation)}-H{int(self.heat_exit)}'

    def __post_init__(self):
        if self.lookback not in ('adaptive', 252, 504):
            raise ValueError('Unregistered lookback')


def features(close, high, low, volume, lookback):
    """Window statistics exclude the prospective initial breakout close."""
    arrays = [np.asarray(a, dtype=float) for a in (close, high, low, volume)]
    if len({a.shape for a in arrays}) != 1 or arrays[0].ndim != 1:
        raise ValueError('One aligned history is required')
    c, h, lo, v = arrays
    if any(not np.isfinite(a).all() or (a <= 0).any() for a in arrays):
        raise ValueError('Unsupported price/volume; never fill missing observations')
    if np.any(h < c) or np.any(lo > c) or np.any(h < lo):
        raise ValueError('Inconsistent OHLC')
    x = pd.Series(np.log(c))
    r = x.diff()
    roll = x.rolling(lookback, min_periods=lookback)
    q05, q95 = roll.quantile(.05).shift(1), roll.quantile(.95).shift(1)
    block = min(63, max(10, lookback//4))
    med = x.rolling(block).median()
    drift = (med - med.shift(lookback-block)).abs().shift(1)
    width = q95-q05
    vol_short = r.rolling(min(63, lookback//3)).std().shift(1)
    vol_long = r.rolling(lookback-1).std().shift(1)
    tr = np.maximum(h-lo, np.maximum(np.abs(h-np.r_[c[0], c[:-1]]),
                                    np.abs(lo-np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).rolling(20).mean()
    tight = ((width <= np.log(1.25)) & (drift <= .5*width)
             & (vol_short <= vol_long) & (atr.shift(1) > 0))
    return dict(upper=np.exp(q95.to_numpy()), lower=np.exp(q05.to_numpy()),
                tight=tight.to_numpy(), atr=atr.to_numpy(),
                prior_volume=pd.Series(v).rolling(63).median().shift(1).to_numpy(),
                width=width.to_numpy(), drift=drift.to_numpy(), duration=np.full(len(c), lookback))


def adaptive_features(close, high, low, volume):
    """Longest qualifying prior range, without tuning duration to future returns."""
    selected = {k: v.copy() for k, v in features(close, high, low, volume, 42).items()}
    for lookback in (63, 126, 252, 504, 756):
        other = features(close, high, low, volume, lookback)
        mask = other['tight']
        for key in ('upper', 'lower', 'width', 'drift', 'duration'):
            selected[key][mask] = other[key][mask]
        selected['tight'] |= mask
    return selected


def lifecycle(close, opens, high, low, raw_volume, spec, *, cached=None):
    c, o, v = (np.asarray(a, dtype=float) for a in (close, opens, raw_volume))
    if o.shape != c.shape or not np.isfinite(o).all() or (o <= 0).any():
        raise ValueError('Unsupported opening prices')
    f = cached if cached is not None else (adaptive_features(c, high, low, v)
        if spec.lookback == 'adaptive' else features(c, high, low, v, spec.lookback))
    n = len(c)
    active = np.zeros(n, dtype=bool)
    heat = np.zeros(n, dtype=bool)
    score = np.zeros(n)
    stops = np.full(n, np.nan)
    state = np.zeros(n, dtype=np.int8)  # 0 neutral,1 range,2 pending,3 trend,4 heat,5 reset,6 oversold
    entries, exits, episodes = [], [], []
    pending = episode = None
    reset_until, failed_confirmations = -1, 0
    frozen_lower = -np.inf
    for t in range(1, n):
        if episode is not None:
            if episode['fill_index'] == t:
                episode['entry_price'] = float(o[t])
                episode['peak'] = float(o[t])
                episode['stop'] = max(o[t]-2*episode['atr'], episode['upper']-episode['atr'])
            episode['peak'] = max(episode['peak'], float(c[t]))
            heated_now = (c[t] >= episode['upper']+3*episode['atr']
                          and c[t] >= episode['peak']-f['atr'][t]
                          and v[t] >= 2*f['prior_volume'][t])
            episode['heated'] = episode['heated'] or bool(heated_now)
            k = 2 if spec.heat_exit and episode['heated'] else 4
            episode['stop'] = max(episode['stop'], episode['peak']-k*f['atr'][t])
            stops[t] = episode['stop']
            reason = None
            if c[t] < episode['upper']-.5*episode['atr']:
                reason = 'failed_range'
            elif c[t] < episode['stop']:
                reason = 'trailing_or_initial_stop'
            elif t-episode['fill_index'] >= 20 and episode['peak'] < episode['entry_price']+episode['atr']:
                reason = 'no_follow_through'
            if reason:
                episode.update(exit_signal=t, exit_reason=reason)
                episodes.append(episode)
                exits.append(t)
                frozen_lower = episode['lower']
                episode, reset_until = None, t+21
                state[t] = 6 if c[t] < frozen_lower else 5
            else:
                active[t] = True
                heat[t] = episode['heated']
                state[t] = 4 if episode['heated'] else 3
                score[t] = np.clip((c[t]-episode['upper'])/episode['atr'], 0, 10)
            continue
        if t <= reset_until:
            state[t] = 6 if c[t] < frozen_lower else 5
            continue
        if pending is not None:
            if c[t] <= pending['level']:
                pending = None
                failed_confirmations += 1
                continue
            if t-pending['cross'] == 2:
                volume_ok = v[t-2:t+1].mean() >= 1.2*pending['volume_reference']
                if not spec.volume_confirmation or volume_ok:
                    episode = dict(signal_index=t, fill_index=t+1, duration=int(pending['duration']), upper=pending['upper'],
                                   lower=pending['lower'], atr=pending['atr'], heated=False,
                                   entry_price=None, peak=None, stop=None)
                    active[t] = True
                    state[t] = 3
                    score[t] = np.clip((c[t]-episode['upper'])/episode['atr'], 0, 10)
                    entries.append(t)
                else:
                    failed_confirmations += 1
                pending = None
            else:
                state[t] = 2
            continue
        if f['tight'][t]:
            state[t] = 1
            level = f['upper'][t] + .5*f['atr'][t-1]
            if c[t] > level and c[t-1] <= level:
                pending = dict(cross=t, level=level, upper=f['upper'][t], lower=f['lower'][t],
                               atr=f['atr'][t-1], volume_reference=f['prior_volume'][t], duration=f['duration'][t])
                state[t] = 2
    if episode is not None:
        episodes.append(dict(episode, exit_signal=None, exit_reason='open_at_cutoff'))
    return dict(active=active, heat=heat, score=score, stop=stops, state=state,
                entries=entries, exits=exits, episodes=episodes,
                failed_confirmations=failed_confirmations)


def slot_weights(scores, volatility, eligible, symbols, conflicts=()):
    """Six slots, inverse volatility, 45% cap; unused/capped budget remains cash."""
    selected = []
    for i in sorted(np.flatnonzero(eligible), key=lambda j: (-scores[j], symbols[j])):
        if any(frozenset((symbols[i], symbols[j])) in conflicts for j in selected):
            continue
        selected.append(int(i))
        if len(selected) == 6:
            break
    weights = np.zeros(len(symbols))
    if selected:
        inv = 1/volatility[selected]
        weights[selected] = np.minimum(.45, .98*len(selected)/6*inv/inv.sum())
    return weights


def portfolio_tapes(close, admitted, symbols, scores, active, fr25, conflicts=()):
    n, m = close.shape
    baseline, selection, trading = (np.zeros((n, m)) for _ in range(3))
    for t in range(126, n):
        vol = np.std(close[t-62:t+1]/close[t-63:t]-1, axis=0, ddof=1)*np.sqrt(252)
        momentum = np.mean([close[t]/close[t-h]-1 for h in (21, 63, 126)], axis=0)
        eligible = admitted[t] & (close[t] > close[t-126]) & (vol > 0)
        scaled = momentum/np.maximum(vol, 1e-12)
        base_rank = np.zeros(m)
        base_rank[eligible] = rankdata(scaled[eligible], method='average')/max(1, eligible.sum())
        factor_rank = np.zeros(m)
        candidates = admitted[t] & active[t]
        factor_rank[candidates] = rankdata(scores[t, candidates], method='average')/max(1, candidates.sum())
        baseline[t] = slot_weights(scaled, vol, eligible, symbols, conflicts)
        selection[t] = slot_weights(base_rank+.5*factor_rank, vol, eligible, symbols, conflicts)
        trading[t] = slot_weights(scores[t], vol, candidates, symbols, conflicts)
    return dict(M1=baseline, selection=selection, trading=trading,
                tilt=.8*fr25+.2*trading, blend_control=.8*fr25+.2*baseline)


def adopted_indices(weights, days, start, policy, *, exits=None):
    """Close-indexed decisions; distance is theoretical versus adopted incl. cash."""
    if policy not in ('monthly', 'event'):
        raise ValueError('Unregistered timing')
    selected, anchor = [], None
    for t in range(len(days)-1):
        if days[t+1] < start:
            continue
        target = weights[t]
        if not np.isfinite(target).all() or target.min() < 0 or target.sum() > 1+1e-12:
            raise ValueError('Invalid target')
        monthly = days[t][:7] != days[t+1][:7]
        gap = np.inf if anchor is None else np.abs(target-anchor).sum()+abs(target.sum()-anchor.sum())
        risk_exit = anchor is not None and exits is not None and np.any(exits[t] & (anchor > 0))
        if anchor is None or monthly or policy == 'event' and (gap > .10+1e-12 or risk_exit):
            selected.append(t)
            anchor = target.copy()
    return selected


def metrics(nav, turnover, fees, exposure, days, start, end, *, initial=1_000_000):
    idx = np.flatnonzero((days >= start) & (days <= end))
    if len(idx) < 2:
        raise ValueError('Insufficient evaluation window')
    a, b = int(idx[0]), int(idx[-1])
    path = np.r_[initial if a == 0 else nav[a-1], nav[a:b+1]]
    r = path[1:]/path[:-1]-1
    years = len(r)/252
    dd = float(np.min(path/np.maximum.accumulate(path)-1))
    cagr = float((path[-1]/path[0])**(1/years)-1)
    return dict(cagr=cagr, sharpe=float(np.mean(r)/np.std(r, ddof=1)*np.sqrt(252)) if np.std(r) else 0.,
                max_drawdown=dd, calmar=cagr/abs(dd) if dd else None,
                annual_turnover=float(turnover[a:b+1].sum()/years),
                annual_cost_bps=float(np.sum(fees[a:b+1]/path[:-1])/years*10000),
                average_exposure=float(exposure[a:b+1].mean()), sessions=len(r))
