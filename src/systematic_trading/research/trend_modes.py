"""Three independently parameterized causal detectors and a long-only latch.

No profit trail, time exit or protective stop overrides the declared state rule.
Unknown evidence is explicit, and retains the last confirmed mode/position.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

VERSION = "trend-modes-1.0.0"
DOWN, RANGE, UP, UNKNOWN = -1, 0, 1, 2
METHODS = ("regression", "structure", "average")
LENGTHS = {"short": (10, 21, 42, 63), "long": (63, 126, 189, 252)}


def rolling(values, length, operation):
    return getattr(pd.Series(values).rolling(length, min_periods=length), operation)().to_numpy()


@dataclass
class Features:
    days: np.ndarray
    open: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    atr: np.ndarray
    cache: dict

    @classmethod
    def build(cls, data):
        o, h, lo, c, v = (np.asarray(data[k], float) for k in ("open", "high", "low", "close", "volume"))
        if not all(np.isfinite(x).all() and (x > 0).all() for x in (o, h, lo, c)):
            raise ValueError("Unsupported prices; do not fill or splice")
        if not np.isfinite(v).all() or (v < 0).any():
            raise ValueError("Unsupported raw volume")
        prior = np.r_[np.nan, c[:-1]]
        atr = rolling(np.maximum(h - lo, np.maximum(abs(h - prior), abs(lo - prior))), 20, "mean")
        log = np.log(c)
        change = np.r_[np.nan, np.diff(log)]
        median = np.r_[np.nan, rolling(v, 21, "median")[:-1]]
        relative = np.divide(v, median, out=np.full(len(c), np.nan), where=median > 0)
        relative = np.minimum(relative, 5.)
        activity = rolling(relative, 5, "mean")
        cache = {}
        for length in sorted(set(sum((list(v) for v in LENGTHS.values()), []))):
            windows = np.lib.stride_tricks.sliding_window_view(log, length)
            x = np.arange(length) - (length - 1) / 2
            means = windows.mean(axis=1)
            slopes = ((windows - means[:, None]) @ x) / (x @ x)
            residual = windows - means[:, None] - slopes[:, None] * x
            variance = np.sum((windows - means[:, None]) ** 2, axis=1)
            r2 = np.divide(slopes ** 2 * (x @ x), variance, out=np.zeros(len(windows)), where=variance > 1e-20)
            pad = lambda a: np.r_[np.full(length - 1, np.nan), a]
            scale = atr / c
            signed = pad(slopes * (length - 1)) / scale
            qlo, qhi = np.quantile(windows, (.1, .9), axis=1)
            width = pad(qhi - qlo) / scale
            net = pad(windows[:, -1] - windows[:, 0])
            path = rolling(abs(change), length - 1, "sum")
            efficiency = np.divide(abs(net), path, out=np.zeros(len(c)), where=path > 0)
            # Independent first/last-third quantile comparisons: no future pivots.
            part = max(3, length // 3)
            first_lo, first_hi = np.quantile(windows[:, :part], (.1, .9), axis=1)
            last_lo, last_hi = np.quantile(windows[:, -part:], (.1, .9), axis=1)
            low_shift, high_shift = pad(last_lo - first_lo) / scale, pad(last_hi - first_hi) / scale
            fast, slow = rolling(log, part, "mean"), rolling(log, length, "mean")
            slow_change = slow - np.r_[np.full(part, np.nan), slow[:-part]]
            average = (fast - slow) / scale
            vl = max(5, min(63, length // 3))
            signed_vol = rolling(np.sign(change) * relative, vl, "sum")
            vol_total = rolling(relative, vl, "sum")
            pressure = np.divide(signed_vol, vol_total, out=np.full(len(c), np.nan), where=vol_total > 0)
            endpoint = pad(means + slopes * (length - 1) / 2)
            lower, upper = np.quantile(residual, (.1, .9), axis=1)
            cache[length] = dict(width=width, efficiency=efficiency, pressure=pressure, activity=activity,
                box_lower=np.exp(pad(qlo)), box_upper=np.exp(pad(qhi)),
                regression=dict(up=signed, down=-signed, flat=abs(signed), quality=pad(r2),
                    lower=np.exp(endpoint + pad(lower)), upper=np.exp(endpoint + pad(upper))),
                structure=dict(up=np.minimum(low_shift, high_shift), down=-np.maximum(low_shift, high_shift),
                    flat=abs((low_shift + high_shift) / 2), quality=efficiency,
                    lower=np.exp(pad(qlo)), upper=np.exp(pad(qhi))),
                average=dict(up=np.where(slow_change > 0, average, -np.inf),
                    down=np.where(slow_change < 0, -average, -np.inf), flat=abs(average), quality=efficiency,
                    lower=np.exp(slow) - atr, upper=np.exp(slow) + atr))
        return cls(np.asarray(data["days"], dtype="datetime64[D]"), o, c, v, atr, cache)

    def truncated(self, cutoff):
        end = int(np.searchsorted(self.days, np.datetime64(cutoff), side="right"))
        def cut(x):
            return {k: cut(v) for k, v in x.items()} if isinstance(x, dict) else x[:end]
        return Features(self.days[:end], self.open[:end], self.close[:end], self.volume[:end], self.atr[:end], cut(self.cache))


def confirmed(mask, count):
    if count not in (1, 2, 3):
        raise ValueError("Undeclared confirmation count")
    sums = np.r_[0, np.cumsum(mask)]
    out = np.zeros(len(mask), bool)
    out[count - 1:] = sums[count:] - sums[:-count] == count
    return out


def classify(features, config):
    """Conflicts need a 25% strength advantage; absence never implies range."""
    method, volume = config["method"], config["volume"]
    if method not in METHODS:
        raise ValueError("Unknown corridor method")
    masks, strength = {}, {}
    for name in ("range", "up", "down"):
        p = config[name]
        if p["length"] not in features.cache:
            raise ValueError("Undeclared detector length")
        f = features.cache[p["length"]]
        s = f[method]
        if name == "range":
            condition = ((s["flat"] <= p["drift"]) & (f["width"] <= p["width"])
                         & (f["efficiency"] <= p["efficiency"]))
            if volume:
                condition &= f["activity"] <= p["activity"]
        else:
            condition = (s[name] >= p["strength"]) & (s["quality"] >= p["quality"])
            if volume:
                sign = 1 if name == "up" else -1
                condition &= (sign * f["pressure"] >= p["pressure"]) & (f["activity"] >= p["activity"])
            strength[name] = (np.where(np.isfinite(s[name]), s[name], 0.) / p["strength"]
                              * np.where(np.isfinite(s["quality"]), s["quality"], 0.) / p["quality"])
        masks[name] = confirmed(condition, p["confirm"])
        if name == "range":
            # An intact, previously identified box takes precedence over a
            # directional detector on another timescale. This gives the range
            # block a real role in transition timing, not just chart labels.
            masks[name] = np.r_[False, masks[name][:-1]]
            prior_atr = np.r_[np.nan, features.atr[:-1]]
            lower = np.r_[np.nan, f["box_lower"][:-1]] - p["buffer"] * prior_atr
            upper = np.r_[np.nan, f["box_upper"][:-1]] + p["buffer"] * prior_atr
            masks[name] &= (features.close >= lower) & (features.close <= upper)
    up, down = masks["up"].copy(), masks["down"].copy()
    overlap = up & down
    up[overlap] = strength["up"][overlap] > 1.25 * strength["down"][overlap]
    down[overlap] = strength["down"][overlap] > 1.25 * strength["up"][overlap]
    raw = np.full(len(features.days), UNKNOWN, np.int8)
    raw[up], raw[down] = UP, DOWN
    raw[masks["range"]] = RANGE
    indices = np.where(raw != UNKNOWN, np.arange(len(raw)), -1)
    last = np.maximum.accumulate(indices)
    state = np.full(len(raw), UNKNOWN, np.int8)
    available = last >= 0
    state[available] = raw[last[available]]
    return dict(state=state, evidence=raw, masks=masks, conflicts=overlap)


def desired_position(state, start=252):
    """Buy range/down -> up; hold through range; sell when down is confirmed."""
    changes = np.flatnonzero(np.r_[False, state[1:] != state[:-1]])
    events = np.zeros(len(state), np.int8)
    for t in changes[changes >= start]:
        if state[t] == UP and state[t - 1] in (RANGE, DOWN):
            events[t] = 1
        elif state[t] == DOWN:
            events[t] = -1
    last = np.maximum.accumulate(np.where(events != 0, np.arange(len(state)), -1))
    return (last >= 0) & (events[np.maximum(last, 0)] == 1)


def simulate(features, classification, *, start=252, cost_bp=5., delay=0):
    if not isinstance(delay, (int, np.integer)) or delay < 0 or not 0 <= cost_bp < 10000:
        raise ValueError("Invalid execution friction")
    n = len(features.days)
    desired = desired_position(classification["state"], start)
    held = np.zeros(n, bool)
    lag = 1 + delay
    if lag < n:
        held[lag:] = desired[:-lag]
    before = np.r_[False, held[:-1]]
    buy, sell = held & ~before, before & ~held
    overnight = np.zeros(n)
    overnight[1:] = np.log(features.open[1:] / features.close[:-1])
    daytime = np.log(features.close / features.open)
    fee = cost_bp / 10000
    netlog = before * overnight + held * daytime - buy * np.log1p(fee) + sell * np.log1p(-fee)
    nav = np.full(n, np.nan)
    nav[start:] = np.exp(np.cumsum(netlog[start:]))
    changes = np.flatnonzero(desired != np.r_[False, desired[:-1]])
    events = [dict(day=int(t), side="buy" if desired[t] else "sell", fill=int(t + lag)) for t in changes]
    entries, exits = np.flatnonzero(buy), list(np.flatnonzero(sell))
    episodes = []
    for i, a in enumerate(entries):
        x = exits[i] if i < len(exits) else None
        episodes.append(dict(entry_index=int(a), entry=float(features.open[a]), entry_signal=int(a - lag),
            exit_index=int(x) if x is not None else None, exit_price=float(features.open[x]) if x is not None else None,
            exit_signal=int(x - lag) if x is not None else None, exit_reason="down" if x is not None else None))
    return dict(nav=nav, desired=desired, held=held, events=events, episodes=episodes, **classification)
