"""Research-only regime/consolidation ablations; frozen engine stays unchanged.

Baseline lifecycle code is copied from breakout_revisit-1.0.0 and parity-tested.
Only entry gating and declared exit protections differ. All decisions at close,
next-open fills, symmetric delay, no intraday stops or new execution authority.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from systematic_trading.research import range_lifecycle as old

VERSION = "breakout-adaptive-1.0.0"
EXIT_MODES = ("legacy", "breakeven", "atr_0.5", "atr_1", "atr_2", "first_lower")
TREND_MODES = ("none", "avoid_down", "up_only")


def regimes(close):
    """Close-time observed state; attribution uses the previous session's state."""
    c = np.asarray(close, float)
    mean = pd.Series(c).rolling(200).mean().to_numpy()
    lag = pd.Series(mean).shift(63).to_numpy()
    valid = np.isfinite(lag)
    state = np.full(len(c), "unknown", dtype="U8")
    state[valid] = "mixed"
    state[valid & (c > mean) & (mean > lag)] = "up"
    state[valid & (c < mean) & (mean < lag)] = "down"
    return state


def range_menu(domain):
    lengths = (21, 63) if domain == "short" else (126, 252)
    return ("legacy",) + tuple(f"{kind}_{n}" for kind in ("flat", "rising") for n in lengths)


def boxes(features, name):
    """Prior closes only. Rising boxes are projected one step from a prior fit.

    Flat: 10/90% close band, efficiency<=.30, absolute fitted drift<=half band,
    width<=8 ATR20, last-third return volatility<=whole-window volatility.
    Rising: positive log-price OLS slope, 10/90% residual channel<=4 ATR20,
    same volatility contraction. No current bar enters range recognition.
    """
    kind, raw = name.split("_")
    length = int(raw)
    if kind not in {"flat", "rising"} or length < 10:
        raise ValueError("invalid range")
    c, n = features.close, len(features.close)
    upper, lower = np.full(n, np.nan), np.full(n, np.nan)
    valid = np.zeros(n, bool)
    x = np.arange(length, dtype=float)
    centered = x - x.mean()
    logc = np.log(c)
    for t in range(length, n):
        y = logc[t - length:t]
        slope = float(centered @ y / (centered @ centered))
        r = np.diff(y)
        sd = float(np.std(r))
        contraction = sd > 0 and np.std(r[-max(5, length // 3):]) <= sd
        a = features.atr[20][t - 1]
        if not np.isfinite(a) or a <= 0:
            continue
        if kind == "flat":
            low, high = np.quantile(y, [.1, .9])
            efficiency = abs(y[-1] - y[0]) / max(np.abs(r).sum(), 1e-15)
            qualifies = (efficiency <= .30 and abs(slope) * (length - 1) <= .5 * (high - low)
                         and np.exp(high) - np.exp(low) <= 8 * a)
        else:
            residual = y - (y.mean() + slope * centered)
            qlo, qhi = np.quantile(residual, [.1, .9])
            prediction = y.mean() + slope * (length - x.mean())
            low, high = prediction + qlo, prediction + qhi
            qualifies = slope > 0 and np.exp(high) - np.exp(low) <= 4 * a
        if contraction and qualifies and high > low:
            valid[t] = True
            upper[t], lower[t] = np.exp(high), np.exp(low)
    return dict(upper=upper, lower=lower, valid=valid)


def prepare(features, vector, range_name="legacy", trend="none", exit_mode="legacy", *, box_cache=None):
    if trend not in TREND_MODES or exit_mode not in EXIT_MODES:
        raise ValueError("invalid component")
    out = old.prepare(features, vector)
    p = out["parameters"].copy()
    if range_name != "legacy":
        b = boxes(features, range_name) if box_cache is None else box_cache[range_name]
        out.update(b)
        out["boundary"] = b["upper"] + p[5] * np.r_[np.nan, out["atr"][:-1]]
        out["cross"] = ((features.close > out["boundary"])
                        & (np.r_[np.nan, features.close[:-1]] <= out["boundary"]))
        out["cross_idx"] = np.flatnonzero(out["cross"])
    state = regimes(features.close)
    out["entry_allowed"] = (np.ones(len(state), bool) if trend == "none"
                            else np.isin(state, ["up", "mixed"]) if trend == "avoid_down"
                            else state == "up")
    if exit_mode.startswith("atr_"):
        # Explicit expanded exit domain, not silently clamped to legacy bounds.
        p[12], p[13], p[15], p[16] = 0, float(exit_mode[4:]), 1, 0
    out.update(parameters=p, exit_mode=exit_mode)
    return out


def simulate(features, prepared, *, start=252, end=None, cost_bp=5., delay=0, target=1.):
    """Sequential corrected lifecycle. Returned ``desired`` is known at each close.

    ``channel_exit`` and ``max_hold`` in prepared are optional simple-rule
    ablations. All other fields use the frozen legacy feature/parameter contract.
    Economic NAV here is an asset diagnostic only; portfolios use the app engine.
    """
    if not isinstance(delay, (int, np.integer)) or delay < 0:
        raise ValueError("delay must be a nonnegative integer")
    if not 0 <= target <= 1 or not 0 <= cost_bp < 10000:
        raise ValueError("invalid target/cost")
    n = len(features.close)
    allowed = prepared.get("entry_allowed", np.ones(n, bool))
    exit_mode = prepared.get("exit_mode", "legacy")
    if exit_mode not in EXIT_MODES:
        raise ValueError("unknown exit mode")
    end = n if end is None else min(int(end), n)
    p, spec = prepared["parameters"], features.spec
    c, o, v, atr = features.close, features.open, features.volume, prepared["atr"]
    nav = np.full(n, np.nan)
    desired, held = np.zeros(n, bool), np.zeros(n, bool)
    stops, levels = np.full(n, np.nan), np.full(n, np.nan)
    cash, units, pending, confirmation, episode, continuation = 1., 0., None, None, None, None
    cooldown_until = -1
    episodes, events = [], []
    for t in range(max(1, start), end):
        if pending is not None and pending["fill"] == t:
            if pending["side"] == "buy":
                episode = pending["episode"]
                entry = float(o[t])
                notional = target * cash / (1 + target * cost_bp / 10000)
                units = notional / entry
                cash -= notional * (1 + cost_bp / 10000)
                stop = entry - p[10] * episode["atr"]
                if p[11] >= 0:
                    stop = max(stop, episode["u"] - p[11] * episode["atr"])
                episode.update(entry_index=t, entry=entry, peak=float(c[t]), stop=stop, heated=False)
            else:
                cash += units * o[t] * (1 - cost_bp / 10000)
                units = 0.
                episode.update(exit_index=t, exit_price=float(o[t]))
                episodes.append(episode.copy())
                continuation = episode.copy() if p[24] else None
                cooldown_until = t + int(p[23]) - 1
                episode = None
            pending = None
        if units:
            # The entry close is fully observed and is eligible to trigger an exit.
            if pending is None:
                episode["peak"] = max(episode["peak"], float(c[t]))
                a, peak = atr[t], episode["peak"]
                if (p[16] and np.isfinite(a) and c[t] >= episode["u"] + p[17] * episode["atr"]
                        and v[t] >= p[18] * prepared["volmed"][t] and c[t] >= peak - p[19] * a):
                    episode["heated"] = True
                if peak >= episode["entry"] + p[15] * episode["atr"] and np.isfinite(a):
                    mult = p[20] if episode["heated"] else 1.
                    trail = peak - p[13] * mult * a if p[12] == 0 else peak * (1 - p[14] * mult)
                    episode["stop"] = max(episode["stop"], trail)
                # Extra protection is armed by a 1-confirmation-ATR peak gain.
                # It never loosens the original initial stop or assumes a fill there.
                protected = peak >= episode["entry"] + episode["atr"]
                if protected and exit_mode == "breakeven":
                    episode["stop"] = max(episode["stop"], episode["entry"])
                reason = None
                if c[t] < episode["stop"]:
                    reason = "stop"
                age = t - episode["entry_index"]
                time_limit = spec.time_limits[int(p[21])]
                if reason is None and time_limit and age >= time_limit and peak < episode["entry"] + p[22] * episode["atr"]:
                    reason = "time"
                if (reason is None and exit_mode == "first_lower" and protected
                        and t > episode["entry_index"] and c[t] < c[t - 1]):
                    reason = "first_lower"
                if reason is None and "channel_exit" in prepared and c[t] < prepared["channel_exit"][t]:
                    reason = "channel"
                if reason is None and prepared.get("max_hold", 0) and age >= prepared["max_hold"]:
                    reason = "age"
                if reason:
                    episode.update(exit_signal=t, exit_reason=reason)
                    pending = dict(side="sell", fill=t + 1 + delay)
                    events.append(dict(day=t, side="sell", fill=t + 1 + delay))
            stops[t], levels[t] = episode["stop"], episode["trigger"]
        elif pending is None and t > cooldown_until:
            # Gate both fresh crossings and continuation/confirmation. A binding
            # pending buy is not cancelled retrospectively at its fill.
            if not allowed[t]:
                confirmation = None
                nav[t] = cash
                continue
            if confirmation is not None:
                if c[t] <= confirmation["trigger"]:
                    confirmation = None
                else:
                    confirmation["count"] += 1
            if confirmation is None:
                wait = spec.reentry_waits[int(p[26])]
                if continuation is not None and (wait <= 0 or t - continuation["exit_signal"] > wait):
                    continuation = None
                trigger = continuation["peak"] + p[25] * atr[t - 1] if continuation else np.nan
                if continuation is not None and c[t] > trigger:
                    confirmation = dict(crossing=t, count=int(p[6]), u=continuation["u"], trigger=float(trigger), reentry=True)
                elif prepared["cross"][t]:
                    confirmation = dict(crossing=t, count=1, u=float(prepared["upper"][t]),
                                        trigger=float(prepared["boundary"][t]), reentry=False)
            if confirmation is not None:
                levels[t] = confirmation["trigger"]
                volume_confirm = p[7] and v[t] >= p[8] * prepared["volmed"][t]
                if confirmation["count"] >= int(p[6]) or volume_confirm:
                    record = dict(confirmation, confirmation=t, atr=float(atr[t]))
                    if not np.isfinite(record["atr"]) or record["atr"] <= 0:
                        raise ValueError("unsupported confirmation ATR")
                    pending = dict(side="buy", fill=t + 1 + delay, episode=record)
                    events.append(dict(day=t, side="buy", fill=t + 1 + delay))
                    continuation, confirmation = None, None
        nav[t] = cash + units * c[t]
        held[t] = units > 0
        desired[t] = (pending["side"] == "buy") if pending is not None else units > 0
    if episode is not None:
        episodes.append(dict(episode, exit_index=None, exit_price=None))
    return dict(nav=nav, desired=desired, held=held, stop=stops, level=levels,
                episodes=episodes, events=events)

