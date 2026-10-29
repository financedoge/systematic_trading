"""Versioned research-only breakout decisions; frozen lifecycle replay is unchanged.

Decision state is distinct from filled exposure. One completed close can confirm
an entry; both orders fill at next open plus the same optional delay. Stops are
close-based, including entry day, never hypothetical intraday fills. Pending
orders are binding. ATR for initial risk is frozen at confirmation. Continuation
re-entry respects cooldown. No fitted thresholds or production registration here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from systematic_trading.research import range_lifecycle as legacy

VERSION = "breakout-revisit-1.0.0"


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
                reason = None
                if c[t] < episode["stop"]:
                    reason = "stop"
                age = t - episode["entry_index"]
                time_limit = spec.time_limits[int(p[21])]
                if reason is None and time_limit and age >= time_limit and peak < episode["entry"] + p[22] * episode["atr"]:
                    reason = "time"
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


def simple_prepared(features, lookback=63, trail=6., exit_rule="trail"):
    """Shared, unfitted breakout/ATR specification across all admitted assets."""
    p = legacy.canonical([.15, 1, .6, 1.2, 1, 0, 1, 0, 1.8, 0,
                          3., -1., 0, trail, .10, 0., 0, 6., 2., 1., .6,
                          0, 2., 0, 0, 1., 0])
    c = features.close
    upper = pd.Series(c).rolling(lookback).max().shift(1).to_numpy()
    cross = (c > upper) & (np.r_[np.nan, c[:-1]] <= upper)
    if exit_rule != "trail":
        p[15] = 1e12  # explicit ablation: disable trailing, retain initial risk stop
    result = dict(parameters=p, atr=features.atr[20], upper=upper, boundary=upper,
                  cross=cross, volmed=features.volmed[20])
    if exit_rule == "channel":
        result["channel_exit"] = pd.Series(c).rolling(20).min().shift(1).to_numpy()
    elif exit_rule == "hold":
        result["max_hold"] = 63
    elif exit_rule != "trail":
        raise ValueError("unknown exit rule")
    return result


def momentum_score(close):
    """Six-month log momentum / trailing realized volatility, known at close."""
    frame = pd.DataFrame(np.log(close))
    return (frame.diff(126) / (frame.diff().rolling(63).std() * np.sqrt(126))).to_numpy()


def select_targets(panel, eligible, scores, monthly, *, clock="dynamic", replace=True, slots=6):
    """Fixed slots, BIL for vacancies, positive momentum and rank-buffered replacement.

    Dynamic reevaluates daily. Monthly controls defer all changes to month-end.
    Hybrid allows daily exits but admits/replaces only at month-end. A held asset
    survives ranking changes until outside top slots+2; then stronger eligible
    names can replace it. Targets execute only on membership changes or monthly
    anchors. Signal stops describe virtual asset regimes, not broker stop orders.
    """
    if clock not in {"dynamic", "monthly", "hybrid"}:
        raise ValueError("unknown clock")
    n, m = eligible.shape
    symbols = list(panel["symbols"])
    bill = symbols.index("BIL")
    weights, theoretical = np.zeros((n, m + 1)), np.zeros((n, m + 1))
    holdings, indices = [], []
    anchors = set(map(int, monthly))
    adopted = np.zeros(m + 1)
    for t in range(int(monthly[0]), n):
        tradable = [j for j in range(m) if j != bill and eligible[t, j] and np.isfinite(scores[t, j]) and scores[t, j] > 0]
        ranked = sorted(tradable, key=lambda j: (-scores[t, j], symbols[j]))
        if clock != "monthly" or t in anchors:
            holdings = [j for j in holdings if j in tradable]
            if clock == "dynamic" or t in anchors:
                if replace:
                    holdings = [j for j in holdings if j in ranked[:slots + 2]]
                holdings.extend([j for j in ranked if j not in holdings][:slots - len(holdings)])
        desired = np.zeros(m + 1)
        desired[holdings] = .98 / slots
        desired[bill] = .98 * (slots - len(holdings)) / slots
        theoretical[t] = desired
        distance = np.abs(desired - adopted).sum() + abs(desired.sum() - adopted.sum())
        if t in anchors or distance > 1e-10:
            weights[t] = desired
            adopted = desired.copy()
            indices.append(t)
    return weights, np.array(indices, int), theoretical
