"""Causal profit exit on failure of the post-entry rising trend.

Frozen entry/risk/cooldown contracts remain unchanged. A positive-slope support
channel, estimated only from prior post-entry closes, replaces the old profit
trail. Stops ratchet and execute from closing decisions at the following open.
"""
from __future__ import annotations

import numpy as np

from systematic_trading.research import range_lifecycle as old
from systematic_trading.research.breakout_adaptive import EXIT_MODES, regimes as regimes

VERSION = "post-breakout-trend-1.0.0"
CENTERS = {n: np.arange(n, dtype=float) - (n - 1) / 2 for n in range(5, 64)}


def rising_support(close, entry_index, today, lookback, buffer_atr, prior_atr):
    """Projected 10% residual support of positive log trend, minus ATR noise band.

    Current close is deliberately excluded. Five prior post-entry closes are
    required; thereafter the window grows to its fitted maximum lookback.
    """
    if today - entry_index < 5 or not np.isfinite(prior_atr):
        return None
    y = np.log(close[max(entry_index, today - lookback):today])
    n = len(y)
    center = CENTERS[n]
    mean = float(y.mean())
    slope = float(center @ y / (n * (n * n - 1) / 12))
    if slope <= 0:
        return None
    residuals = np.sort(y - mean - slope * center)
    rank = .1 * (n - 1)
    lower = int(rank)
    residual = float(residuals[lower] + (rank - lower) * (residuals[min(lower + 1, n - 1)] - residuals[lower]))
    prediction = float(mean + slope * ((n + 1) / 2) + residual)
    return float(np.exp(prediction) - buffer_atr * prior_atr)


def prepare(features, vector, rule=None):
    out = old.prepare(features, vector)
    out["trend_rule"] = rule
    if rule is not None:
        if rule["lookback"] not in (10, 21, 42, 63) or rule["buffer_atr"] not in (.5, 1., 2.):
            raise ValueError("Undeclared trend-exit rule")
        p = out["parameters"].copy()
        p[15], p[16] = 1e12, 0  # replace profit trail; retain original initial risk
        out["parameters"] = p
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
    rule = prepared.get("trend_rule")
    trend_levels = np.full(n, np.nan)
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
                if rule is not None:
                    candidate = rising_support(c, episode["entry_index"], t,
                                               rule["lookback"], rule["buffer_atr"], atr[t - 1])
                    if candidate is not None:
                        episode["trend_established"] = True
                        episode["trend_stop"] = max(episode.get("trend_stop", -np.inf), candidate)
                        episode["stop"] = max(episode["stop"], episode["trend_stop"])
                reason = None
                if c[t] < episode["stop"]:
                    reason = "stop"
                age = t - episode["entry_index"]
                time_limit = spec.time_limits[int(p[21])]
                if reason is None and time_limit and not episode.get("trend_established", False) and age >= time_limit and peak < episode["entry"] + p[22] * episode["atr"]:
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
            trend_levels[t] = episode.get("trend_stop", np.nan)
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
                episodes=episodes, events=events, trend_level=trend_levels)

