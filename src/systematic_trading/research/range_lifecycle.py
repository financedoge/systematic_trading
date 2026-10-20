"""Causal range -> breakout -> trend-hold -> dynamic-TP lifecycle signal.

This module is the checked reference implementation for the GLD lifecycle study.
Every behavioral threshold is an element of the parameter vector; there is no
fixed range width, confirmation count, stop multiple, trailing distance or time
limit. Decisions use completed closes only; fills happen at the following session
open (optionally one session later for execution-delay stress).

Lifecycle
---------
At completed close ``t`` (bands and range statistics use closes up to ``t-1``):

1. Range: for each candidate lookback ``L`` in ``WINDOWS`` and quantile tail ``q``
   compute ``D_t = exp(quantile_q(x[t-L:t]))``, ``U_t = exp(quantile_{1-q}(...))``
   and log width ``W_t = log(U_t/D_t)``. The range qualifies when

       W_t <= width_cap
       |median(last b closes) - median(first b closes)| <= drift_max * W_t
       std(last c returns) <= vol_ratio_cap * std(last L returns)

   with ``b = min(63, max(10, L//4))`` and ``c = min(63, max(5, L//3))``. The
   selected range is the longest qualifying ``L`` (price has been stable for the
   longest available window).

2. Breakout trigger: ``close_t > U_t + buffer * ATR_p[t-1]``. The range and bands
   are frozen at the crossing close. The crossing is only accepted when
   ``close_{t-1} <= trigger`` so the rule needs an actual crossing event.

3. Confirmation: ``confirm_sessions`` consecutive closes above the frozen trigger
   are required; any close at/below it cancels the pending breakout. A volume
   surge (raw volume >= ``volume_ratio`` times its prior ``volref`` median)
   confirms immediately, closing the gap between crossing and fill when the
   breakout has genuine activity.

4. Entry: first consequent open after confirmation at ``target`` of NAV with
   ``cost_bp`` per side.

5. Initial risk: ``S0 = entry - initial_stop_atr * ATR_entry``; when
   ``band_fail_atr >= 0`` also ``S0 = max(S0, U* - band_fail_atr * ATR_entry)`` so
   a failed breakout back into the range is cut without a tight price-only stop.

6. Trend hold and dynamic take profit: with ``H`` the highest close since entry,
   once ``H >= entry + trail_activate_atr * ATR_entry`` the stop ratchets to
   ``H - k * ATR_t`` (``trail_basis=0``) or ``H * (1 - d)`` (``trail_basis=1``).
   When price extension and volume climax indicate overheating the trail distance
   is multiplied by ``heat_trail_mult``. A time stop exits when ``time_limit``
   sessions have elapsed and peak gain is still below ``time_exit_gain_atr *
   ATR_entry``.

7. Exit: a close below the current stop or the time rule is executed at the next
   open; then a ``cooldown`` flat period is enforced before another range/breakout
   can be adopted. Cash earns zero.

Accounting uses fractional units, costs charged on traded notional and no
intraday stop fills. ``trace=True`` records, for every session, the selected
range, trigger, state, entry, peak, stop decomposition and exit reason so the
behavior can be audited day by day.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

WINDOWS = (21, 42, 63, 126, 252, 504)
TAILS = (0.05, 0.10, 0.15, 0.20)
ATR_PERIODS = (10, 20, 40, 60)
VOL_PERIODS = (20, 63, 126)
TIME_LIMITS = (0, 10, 20, 42, 63, 126)
REENTRY_WAITS = (0, 21, 42, 63, 126, 252)

# name, lower bound, upper bound, integral: every behavioral threshold is fitted.
PARAMETERS = (
    ("width_cap", 0.05, 0.80, False),
    ("tail_index", 0, 3, True),
    ("drift_max", 0.15, 1.50, False),
    ("vol_ratio_cap", 0.50, 1.60, False),
    ("atr_index", 0, 3, True),
    ("breakout_buffer_atr", 0.0, 1.50, False),
    ("confirm_sessions", 1, 6, True),
    ("volume_shortcut", 0, 1, True),
    ("volume_ratio", 1.0, 3.0, False),
    ("volref_index", 0, 2, True),
    ("initial_stop_atr", 1.5, 12.0, False),
    ("band_fail_atr", -1.0, 4.0, False),
    ("trail_basis", 0, 1, True),
    ("trail_atr", 1.0, 12.0, False),
    ("trail_pct", 0.03, 0.35, False),
    ("trail_activate_atr", 0.0, 6.0, False),
    ("heat_enabled", 0, 1, True),
    ("heat_ext_atr", 1.0, 12.0, False),
    ("heat_vol_ratio", 1.0, 5.0, False),
    ("heat_near_high_atr", 0.25, 5.0, False),
    ("heat_trail_mult", 0.20, 1.00, False),
    ("time_exit_index", 0, 5, True),
    ("time_exit_gain_atr", 0.50, 4.0, False),
    ("cooldown_sessions", 0, 42, True),
    ("reentry_enabled", 0, 1, True),
    ("reentry_buffer_atr", 0.0, 4.0, False),
    ("reentry_wait_index", 0, 5, True),
)
BOUNDS = np.array([(p[1], p[2]) for p in PARAMETERS], float)
INTEGRAL = np.array([p[3] for p in PARAMETERS], bool)
NAMES = tuple(p[0] for p in PARAMETERS)
STATE_FLAT, STATE_PENDING, STATE_LONG = 0, 1, 2
EXIT_STOP, EXIT_TIME = 1, 3


@dataclass(frozen=True)
class Spec:
    """A predeclared structural domain: candidate menus plus fitted parameter bounds.

    The short-range domain was frozen as the first GLD lifecycle study. The
    long-range domain keeps the identical state machine and objective but searches
    six-to-thirty-six month lookbacks, much wider initial stops and wider/longer
    trailing distances. The domain is a predeclared experiment design choice; every
    behavioral threshold inside it is still fitted on pre-2023 data.
    """

    name: str
    windows: tuple
    tails: tuple
    atr_periods: tuple
    vol_periods: tuple
    time_limits: tuple
    reentry_waits: tuple
    parameters: tuple
    drift_block_cap: int = 63
    shortvol_cap: int = 63

    @property
    def bounds(self):
        return np.array([(p[1], p[2]) for p in self.parameters], float)

    @property
    def integral(self):
        return np.array([p[3] for p in self.parameters], bool)

    @property
    def names(self):
        return tuple(p[0] for p in self.parameters)

    def canonical(self, parameters):
        p = np.asarray(parameters, float).copy()
        if p.shape != (len(self.parameters),) or not np.isfinite(p).all():
            raise ValueError("Invalid lifecycle parameter vector")
        bounds = self.bounds
        p = np.clip(p, bounds[:, 0], bounds[:, 1])
        integral = self.integral
        p[integral] = np.round(p[integral])
        return p

    def describe(self, parameters):
        p = self.canonical(parameters)
        out = {name: (int(v) if integ else float(v))
               for name, v, integ in zip(self.names, p, self.integral, strict=True)}
        out.update(tail=self.tails[int(p[1])], atr_period=self.atr_periods[int(p[4])],
                   volume_reference=self.vol_periods[int(p[9])],
                   trail_basis_name=("atr_from_high", "percent_from_high")[int(p[12])],
                   time_limit_sessions=self.time_limits[int(p[21])],
                   reentry_wait_sessions=self.reentry_waits[int(p[26])],
                   domain=self.name)
        return out


SHORT_SPEC = Spec("short_range", WINDOWS, TAILS, ATR_PERIODS, VOL_PERIODS, TIME_LIMITS,
                  REENTRY_WAITS, PARAMETERS)

LONG_WINDOWS = (126, 189, 252, 378, 504, 756)
LONG_TAILS = (0.05, 0.10, 0.15, 0.20)
LONG_ATR_PERIODS = (20, 40, 60, 120)
LONG_VOL_PERIODS = (63, 126, 252)
LONG_TIME_LIMITS = (0, 126, 252, 504)
LONG_REENTRY_WAITS = (0, 126, 252, 378, 504, 756)
LONG_PARAMETERS = (
    ("width_cap", 0.10, 0.80, False),
    ("tail_index", 0, 3, True),
    ("drift_max", 0.08, 0.60, False),
    ("vol_ratio_cap", 0.50, 1.60, False),
    ("atr_index", 0, 3, True),
    ("breakout_buffer_atr", 0.0, 1.50, False),
    ("confirm_sessions", 1, 8, True),
    ("volume_shortcut", 0, 1, True),
    ("volume_ratio", 1.0, 3.0, False),
    ("volref_index", 0, 2, True),
    ("initial_stop_atr", 4.0, 20.0, False),
    ("band_fail_atr", -1.0, 8.0, False),
    ("trail_basis", 0, 1, True),
    ("trail_atr", 3.0, 20.0, False),
    ("trail_pct", 0.08, 0.50, False),
    ("trail_activate_atr", 0.0, 12.0, False),
    ("heat_enabled", 0, 1, True),
    ("heat_ext_atr", 2.0, 16.0, False),
    ("heat_vol_ratio", 1.0, 5.0, False),
    ("heat_near_high_atr", 0.25, 6.0, False),
    ("heat_trail_mult", 0.20, 1.00, False),
    ("time_exit_index", 0, 3, True),
    ("time_exit_gain_atr", 0.50, 6.0, False),
    ("cooldown_sessions", 0, 126, True),
    ("reentry_enabled", 0, 1, True),
    ("reentry_buffer_atr", 0.0, 6.0, False),
    ("reentry_wait_index", 0, 5, True),
)
LONG_SPEC = Spec("long_range", LONG_WINDOWS, LONG_TAILS, LONG_ATR_PERIODS, LONG_VOL_PERIODS,
                 LONG_TIME_LIMITS, LONG_REENTRY_WAITS, LONG_PARAMETERS,
                 drift_block_cap=189, shortvol_cap=252)


def canonical(parameters, spec=SHORT_SPEC):
    return spec.canonical(parameters)


def describe(parameters, spec=SHORT_SPEC):
    return spec.describe(parameters)


@dataclass(frozen=True)
class Features:
    """Immutable per-session features. All band/statistic features are shifted one session."""

    spec: Spec
    days: np.ndarray
    close: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray
    atr: dict
    volmed: dict
    width: dict
    drift: dict
    shortvol: dict
    longvol: dict
    upper: dict
    lower: dict

    @classmethod
    def build(cls, data, spec=SHORT_SPEC):
        c = np.asarray(data["close"], float)
        o = np.asarray(data["open"], float)
        h = np.asarray(data["high"], float)
        lo = np.asarray(data["low"], float)
        v = np.asarray(data["volume"], float)
        days = np.asarray(data["days"])
        if days.dtype.kind in "US":
            days = np.asarray(days, dtype="datetime64[D]")
        if not (len(c) == len(o) == len(h) == len(lo) == len(v) == len(days)):
            raise ValueError("Inconsistent input lengths")
        if not (np.isfinite(c).all() and np.isfinite(o).all() and np.isfinite(h).all()
                and np.isfinite(lo).all() and np.isfinite(v).all()):
            raise ValueError("Unsupported observations")
        if (c <= 0).any() or (o <= 0).any() or (h <= 0).any() or (lo <= 0).any() or (v < 0).any():
            raise ValueError("Unsupported price/volume values")
        if (h < c).any() or (lo > c).any() or (h < lo).any():
            raise ValueError("Inconsistent OHLC")
        x = pd.Series(np.log(c))
        r = x.diff()
        prev_c = np.r_[np.nan, c[:-1]]
        tr = np.maximum(h - lo, np.maximum(np.abs(h - prev_c), np.abs(lo - prev_c)))
        atr = {period: pd.Series(tr).rolling(period).mean().to_numpy()
               for period in spec.atr_periods}
        volmed = {p: pd.Series(v).rolling(p).median().shift(1).to_numpy()
                  for p in spec.vol_periods}
        width, upper, lower = {}, {}, {}
        for tail in spec.tails:
            width[tail], upper[tail], lower[tail] = {}, {}, {}
            for length in spec.windows:
                roll = x.rolling(length, min_periods=length)
                lowq = roll.quantile(tail).shift(1).to_numpy()
                highq = roll.quantile(1.0 - tail).shift(1).to_numpy()
                width[tail][length] = highq - lowq
                upper[tail][length] = np.exp(highq)
                lower[tail][length] = np.exp(lowq)
        drift, shortvol, longvol = {}, {}, {}
        for length in spec.windows:
            block = min(spec.drift_block_cap, max(10, length // 4))
            med = x.rolling(block).median()
            drift[length] = (med - med.shift(length - block)).abs().shift(1).to_numpy()
            short = min(spec.shortvol_cap, max(5, length // 3))
            shortvol[length] = r.rolling(short).std().shift(1).to_numpy()
            longvol[length] = r.rolling(length).std().shift(1).to_numpy()
        return cls(spec=spec, days=days, close=c, open=o, high=h, low=lo, volume=v,
                   atr=atr, volmed=volmed, width=width, drift=drift, shortvol=shortvol,
                   longvol=longvol, upper=upper, lower=lower)

    def truncated(self, last_date):
        """Return a copy truncated strictly through ``last_date`` (inclusive)."""
        stamp = np.datetime64(last_date, "D") if not isinstance(last_date, np.datetime64) else last_date
        keep = np.flatnonzero(self.days <= stamp)
        if len(keep) == 0:
            raise ValueError("Truncation removes every observation")
        end = int(keep[-1]) + 1
        cut = lambda a: np.asarray(a)[:end].copy()
        return Features(spec=self.spec, days=cut(self.days), close=cut(self.close),
                        open=cut(self.open), high=cut(self.high), low=cut(self.low),
                        volume=cut(self.volume),
                        atr={k: cut(a) for k, a in self.atr.items()},
                        volmed={k: cut(a) for k, a in self.volmed.items()},
                        width={t: {l: cut(a) for l, a in d.items()} for t, d in self.width.items()},
                        drift={l: cut(a) for l, a in self.drift.items()},
                        shortvol={l: cut(a) for l, a in self.shortvol.items()},
                        longvol={l: cut(a) for l, a in self.longvol.items()},
                        upper={t: {l: cut(a) for l, a in d.items()} for t, d in self.upper.items()},
                        lower={t: {l: cut(a) for l, a in d.items()} for t, d in self.lower.items()})


def prepare(features: Features, parameters):
    """Compute the causal daily range/trigger state shared by all exit rules."""
    spec = features.spec
    p = spec.canonical(parameters)
    tail = spec.tails[int(p[1])]
    width_cap = float(p[0])
    drift_max = float(p[2])
    vol_ratio_cap = float(p[3])
    buffer = float(p[5])
    n = len(features.close)
    L_selected = np.zeros(n, np.int16)
    valid = np.zeros(n, bool)
    U = np.full(n, np.nan)
    D = np.full(n, np.nan)
    W = np.full(n, np.nan)
    drift = np.full(n, np.nan)
    vol_ratio = np.full(n, np.nan)
    atr = features.atr[spec.atr_periods[int(p[4])]]
    atr_prev = np.r_[np.nan, atr[:-1]]
    for length in spec.windows[::-1]:
        w = features.width[tail][length]
        dr = features.drift[length]
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = features.shortvol[length] / features.longvol[length]
        qualifies = ((w <= width_cap) & (dr <= drift_max * w) & (ratio <= vol_ratio_cap)
                     & np.isfinite(w) & np.isfinite(dr) & np.isfinite(ratio))
        take = qualifies & ~valid
        if take.any():
            L_selected[take] = length
            U[take] = features.upper[tail][length][take]
            D[take] = features.lower[tail][length][take]
            W[take] = w[take]
            drift[take] = dr[take]
            vol_ratio[take] = ratio[take]
            valid |= take
    boundary = np.full(n, np.nan)
    boundary[1:] = U[1:] + buffer * atr_prev[1:]
    cross = np.zeros(n, bool)
    cross[1:] = ((features.close[1:] > boundary[1:])
                 & (features.close[:-1] <= boundary[1:])
                 & np.isfinite(boundary[1:]))
    cross_idx = np.flatnonzero(cross)
    volmed = features.volmed[spec.vol_periods[int(p[9])]]
    return dict(parameters=p, decoded=spec.describe(p), L=L_selected, valid=valid, upper=U,
                lower=D, width=W, drift=drift, vol_ratio=vol_ratio, atr=atr,
                boundary=boundary, cross=cross, cross_idx=cross_idx, volmed=volmed)
def simulate(features: Features, prepared: dict, start: int = 252, end: int | None = None,
             cost_bp: float = 5.0, target: float = 1.0, delay: int = 0, trace: bool = False):
    """Run the lifecycle on causal data. Decisions at close, fills at the next open(s).

    A closed breakout episode can be re-engaged (``reentry_enabled``) while the
    original trend keeps making new closing highs: after ``reentry_wait_sessions``
    at most, a close above the previous episode peak plus
    ``reentry_buffer_atr * ATR`` re-enters at the next open. This holds a persistent
    multi-leg breakout without pretending a new tight range formed.
    """
    p = prepared["parameters"]
    spec = features.spec
    n = len(features.close)
    end = n if end is None else int(end)
    start = max(1, int(start))
    c = features.close
    o = features.open
    v = features.volume
    atr = prepared["atr"]
    volmed = prepared["volmed"]
    upper = prepared["upper"]
    lower = prepared["lower"]
    boundary = prepared["boundary"]
    cross_idx = prepared["cross_idx"]
    initial_stop = float(p[10])
    band_fail = float(p[11])
    trail_basis = int(p[12])
    trail_atr = float(p[13])
    trail_pct = float(p[14])
    trail_activate = float(p[15])
    heat_enabled = int(p[16])
    heat_ext = float(p[17])
    heat_vol = float(p[18])
    heat_near = float(p[19])
    heat_mult = float(p[20])
    time_limit = spec.time_limits[int(p[21])]
    time_gain = float(p[22])
    cooldown = int(p[23])
    reentry_enabled = int(p[24])
    reentry_buffer = float(p[25])
    reentry_wait = spec.reentry_waits[int(p[26])]
    confirm_required = int(p[6])
    volume_shortcut = int(p[7])
    volume_ratio = float(p[8])
    cost_rate = cost_bp / 10000.0
    nav = np.full(n, np.nan)
    weight = np.zeros(n, np.float32)
    cash = 1.0
    q = 0.0
    reset_until = -1
    reentry = None
    episodes = []
    if trace:
        states = np.zeros(n, np.int8)
        reason = np.zeros(n, np.int8)
        stop_trace = np.full(n, np.nan)
        stop_initial = np.full(n, np.nan)
        stop_band = np.full(n, np.nan)
        stop_trail = np.full(n, np.nan)
        level_trace = np.full(n, np.nan)
        entry_trace = np.full(n, np.nan)
        peak_trace = np.full(n, np.nan)
        drawdown_trace = np.full(n, np.nan)
        heat_trace = np.zeros(n, np.int8)
        hold_trace = np.zeros(n, np.int32)
    else:  # pragma: no cover - trace buffers are unused on the fast path
        states = reason = stop_trace = stop_initial = stop_band = stop_trail = None
        level_trace = entry_trace = peak_trace = drawdown_trace = heat_trace = hold_trace = None
    t = start
    while t < end:
        ready = None
        # ---------------------------- continuation re-entry ---------------------------
        if reentry_enabled and reentry is not None:
            if reentry_wait <= 0 or (t - reentry["exit_signal"]) > reentry_wait:
                reentry = None
            else:
                trigger = reentry["peak"] + reentry_buffer * (atr[t - 1] if t > 0 else np.nan)
                if np.isfinite(trigger) and c[t] > trigger:
                    ready = dict(crossing=t, confirmation=t, u=reentry["u"], d=reentry["d"],
                                 atr_entry=atr[t], trigger=float(trigger), reentry=True)
        # ------------------------------- range breakout -------------------------------
        if ready is None:
            j = int(np.searchsorted(cross_idx, max(t, reset_until + 1), side="left"))
            next_cross = int(cross_idx[j]) if j < len(cross_idx) else end
            if next_cross > t:
                if reentry is not None:
                    nav[t] = cash
                    t += 1
                    continue
                nav[t:min(next_cross, end)] = cash
                t = next_cross
            if t >= end:
                break
            if not (np.isfinite(boundary[t]) and np.isfinite(atr[t - 1]) and np.isfinite(upper[t])):
                nav[t] = cash
                t += 1
                continue
            u_frozen = upper[t]
            d_frozen = lower[t]
            atr_signal = atr[t]
            level = boundary[t]
            crossing = t
            confirmed = -1
            if volume_shortcut and np.isfinite(volmed[t]) and v[t] >= volume_ratio * volmed[t]:
                confirmed = t
            count = 1
            probe = t + 1
            while confirmed < 0 and probe < end:
                if c[probe] <= level:
                    break
                count += 1
                if volume_shortcut and np.isfinite(volmed[probe]) and v[probe] >= volume_ratio * volmed[probe]:
                    confirmed = probe
                elif count >= confirm_required:
                    confirmed = probe
                probe += 1
            if confirmed < 0:
                nav[t:min(probe, end)] = cash
                if trace and probe > t + 1:
                    states[t:probe] = STATE_PENDING
                    level_trace[t:probe] = level
                t = max(probe, t + 1)
                continue
            fill = confirmed + 1 + delay
            if fill >= end:
                nav[t:end] = cash
                break
            ready = dict(crossing=crossing, confirmation=confirmed, u=u_frozen,
                         d=d_frozen, atr_entry=atr_signal, trigger=level, reentry=False,
                         fill=fill)
            reentry = None
        # --------------------------------- common entry -------------------------------
        fill = ready.get("fill", ready["confirmation"] + 1 + delay)
        if fill >= end:
            nav[t:end] = cash
            break
        if trace:
            states[t:ready["confirmation"] + 1] = STATE_PENDING
            level_trace[t:ready["confirmation"] + 1] = ready["trigger"]
        nav[t:fill] = cash
        t = fill
        entry = float(o[fill])
        notional = target * cash
        fee = notional * cost_rate
        q = notional / entry
        cash = cash - notional - fee
        atr_entry = float(ready["atr_entry"])
        u_frozen = float(ready["u"])
        d_frozen = float(ready["d"])
        peak = float(c[fill])
        init_stop = entry - initial_stop * atr_entry
        band_stop = u_frozen - band_fail * atr_entry if band_fail >= 0 else -np.inf
        stop = max(init_stop, band_stop)
        trail_stop = np.nan
        heated = False
        nav[t] = cash + q * c[t]
        weight[t] = q * c[t] / nav[t]
        if trace:
            states[t] = STATE_LONG
            entry_trace[t] = entry
            stop_trace[t] = stop
            stop_initial[t] = init_stop
            stop_band[t] = band_stop
            peak_trace[t] = peak
            hold_trace[t] = 0
        episode = dict(entry_index=fill, crossing=int(ready["crossing"]),
                       confirmation=int(ready["confirmation"]), entry=entry, u=u_frozen,
                       d=d_frozen, atr=atr_entry, trigger=float(ready["trigger"]),
                       initial_stop=init_stop,
                       band_stop=(band_stop if np.isfinite(band_stop) else None),
                       reentry=bool(ready["reentry"]))
        t = fill + 1
        exited = False
        while t < end:
            peak = max(peak, float(c[t]))
            atr_now = atr[t]
            if heat_enabled and not heated and np.isfinite(atr_now):
                if (c[t] >= u_frozen + heat_ext * atr_entry
                        and np.isfinite(volmed[t]) and v[t] >= heat_vol * volmed[t]
                        and c[t] >= peak - heat_near * atr_now):
                    heated = True
            if peak >= entry + trail_activate * atr_entry and np.isfinite(atr_now):
                mult = heat_mult if heated else 1.0
                candidate = (peak - trail_atr * mult * atr_now if trail_basis == 0
                             else peak * (1.0 - trail_pct * mult))
                if candidate > stop:
                    stop = candidate
                    trail_stop = candidate
            reason_code = 0
            if c[t] < stop:
                reason_code = EXIT_STOP
            elif time_limit > 0 and (t - fill) >= time_limit and peak < entry + time_gain * atr_entry:
                reason_code = EXIT_TIME
            nav_here = cash + q * c[t]
            nav[t] = nav_here
            weight[t] = q * c[t] / nav_here if nav_here > 0 else 0.0
            if trace:
                states[t] = STATE_LONG
                stop_trace[t] = stop
                stop_initial[t] = init_stop
                stop_band[t] = band_stop
                stop_trail[t] = trail_stop
                entry_trace[t] = entry
                peak_trace[t] = peak
                drawdown_trace[t] = c[t] / peak - 1.0
                heat_trace[t] = int(heated)
                hold_trace[t] = t - fill
                level_trace[t] = ready["trigger"]
            if reason_code:
                if t + 1 < end:
                    exit_price = float(o[t + 1])
                    cash += q * exit_price * (1.0 - cost_rate)
                    q = 0.0
                    nav[t + 1] = cash
                    episode.update(exit_signal=t, exit_index=t + 1, exit_price=exit_price,
                                   exit_reason=reason_code, peak=peak, final_stop=stop,
                                   heated=bool(heated), hold_sessions=(t + 1 - fill))
                    episodes.append(episode)
                    if trace:
                        reason[t] = reason_code
                    if reentry_enabled:
                        reentry = dict(peak=float(peak), exit_signal=t, u=u_frozen, d=d_frozen)
                    reset_until = t + cooldown
                    t += 1
                    exited = True
                    break
                else:
                    t = end
                    break
            t += 1
        if not exited and q > 0.0:
            episode.update(exit_signal=None, exit_index=None, exit_price=None, exit_reason=None,
                           peak=peak, final_stop=stop, heated=bool(heated),
                           hold_sessions=(end - 1 - fill))
            episodes.append(episode)
            q = 0.0
            cash = nav[end - 1]
            break
    if trace:
        missing = np.flatnonzero(np.isnan(nav))
        inside = missing[missing >= start]
        if len(inside):
            nav[inside] = cash
        out = dict(nav=nav, weight=weight, state=states, reason=reason, stop=stop_trace,
                   stop_initial=stop_initial, stop_band=stop_band, stop_trail=stop_trail,
                   level=level_trace, entry=entry_trace, peak=peak_trace,
                   drawdown=drawdown_trace, heat=heat_trace, hold=hold_trace,
                   range=dict(L=prepared["L"], upper=prepared["upper"], lower=prepared["lower"],
                              width=prepared["width"], drift=prepared["drift"],
                              vol_ratio=prepared["vol_ratio"], boundary=prepared["boundary"],
                              atr=prepared["atr"], volmed=prepared["volmed"],
                              cross=prepared["cross"], valid=prepared["valid"]),
                   episodes=episodes, start=start)
    else:
        missing = np.flatnonzero(np.isnan(nav))
        inside = missing[missing >= start]
        if len(inside):
            nav[inside] = cash
        out = dict(nav=nav, weight=weight, episodes=episodes, start=start)
    return out


def buy_hold(features: Features, start: int, end: int | None = None, cost_bp: float = 5.0):
    n = len(features.close)
    end = n if end is None else int(end)
    start = int(start)
    entry = float(features.open[start])
    cost_rate = cost_bp / 10000.0
    q = 1.0 / (entry * (1.0 + cost_rate) / (1.0 - 0.0))
    q = (1.0 - cost_rate) / entry
    nav = np.full(n, np.nan)
    nav[start:] = q * features.close[start:]
    weight = np.zeros(n, np.float32)
    weight[start:] = 1.0
    return dict(nav=nav, weight=weight)


def stats(nav, weight, start, end):
    """Performance statistics on the [start, end) slice; zero risk-free rate."""
    start, end = int(start), int(end)
    a = np.asarray(nav[start:end], float)
    if len(a) < 3 or not np.isfinite(a).all():
        return dict(cagr=-1.0, sharpe=0.0, maxdd=-1.0, calmar=-1.0,
                    exposure=0.0, sessions=0, ann_vol=0.0)
    ret = a[1:] / a[:-1] - 1.0
    sessions = len(a) - 1
    years = sessions / 252.0
    cagr = float((a[-1] / a[0]) ** (1.0 / years) - 1.0)
    sd = float(ret.std(ddof=1)) if sessions > 2 else 0.0
    sharpe = float(ret.mean() / sd * np.sqrt(252.0)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(a)
    dd = float((a / peak - 1.0).min())
    return dict(cagr=cagr, sharpe=sharpe, maxdd=dd, calmar=float(cagr / max(0.03, -dd)),
                exposure=float(np.asarray(weight[start:end], float).mean()),
                sessions=int(sessions), ann_vol=float(sd * np.sqrt(252.0)))


def utility(rule_stats, buyhold_stats):
    """45% scaled excess CAGR, 40% excess Sharpe, 15% excess regularized Calmar."""
    dcagr = np.clip((rule_stats["cagr"] - buyhold_stats["cagr"]) / 0.10, -3.0, 3.0)
    dsharpe = np.clip(rule_stats["sharpe"] - buyhold_stats["sharpe"], -3.0, 3.0)
    dcalmar = np.clip(rule_stats["calmar"] - buyhold_stats["calmar"], -3.0, 3.0)
    return float(0.45 * dcagr + 0.40 * dsharpe + 0.15 * dcalmar)


def block_bounds(start, end, blocks=3):
    start, end = int(start), int(end)
    size = end - start
    return [(start + (i * size) // blocks, start + ((i + 1) * size) // blocks) for i in range(blocks)]


def evaluate(features: Features, parameters, start: int, end: int, cost_bp: float = 5.0,
             delay: int = 0, blocks: int = 3):
    """Full evidence record for one parameter vector on one fixed window."""
    prepared = prepare(features, parameters)
    sim = simulate(features, prepared, start=start, end=end, cost_bp=cost_bp, delay=delay)
    bh = buy_hold(features, start=start, end=end, cost_bp=cost_bp)
    full = stats(sim["nav"], sim["weight"], start, end)
    bh_full = stats(bh["nav"], bh["weight"], start, end)
    block_rows = []
    for b0, b1 in block_bounds(start, end, blocks):
        rs = stats(sim["nav"], sim["weight"], b0, b1)
        bs = stats(bh["nav"], bh["weight"], b0, b1)
        block_rows.append(dict(start=b0, end=b1, rule=rs, buyhold=bs, utility=utility(rs, bs)))
    block_utils = [row["utility"] for row in block_rows]
    closed = [e for e in sim["episodes"] if e["exit_signal"] is not None]
    open_episodes = [e for e in sim["episodes"] if e["exit_signal"] is None]
    scarcity = max(0.0, 10.0 - len(closed)) / 10.0
    low_exposure = max(0.0, 0.20 - full["exposure"]) / 0.20
    robust = (0.5 * utility(full, bh_full) + 0.5 * float(np.median(block_utils))
              - 0.25 * float(np.std(block_utils)))
    fitness = float(robust - 0.10 * scarcity - 0.30 * low_exposure)
    return dict(parameters=np.asarray(parameters, float).copy(), full=full, buyhold=bh_full,
                blocks=block_rows, utility=utility(full, bh_full), robust=float(robust),
                fitness=fitness, n_closed=len(closed), n_open=len(open_episodes),
                episodes=sim["episodes"], scarcity=scarcity, low_exposure=low_exposure)
