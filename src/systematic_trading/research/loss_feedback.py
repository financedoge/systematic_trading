"""Causal single-loss/streak feedback experiments on frozen market signals.

Research only. Close decisions fill at a later open; cash/share accounting and
fresh shadow recovery are explicit. No online refit or broker authority.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from . import coupled_trends
from .strategy_health import ClosedTrade, HealthController, Mode

VERSION = "loss-feedback-v1"
ARMS = ("fixed", "streak", "severity")


def calibrate(f, classification, *, cost_bp=5):
    """Winner dispersion from completed training trades only, with coverage."""
    result = coupled_trends.simulate(f, classification, cost_bp=cost_bp)
    fee = cost_bp / 10000
    outcomes = np.array([e['exit_price']/e['entry']*(1-fee)/(1+fee)-1
                         for e in result['episodes'] if e['exit_index'] is not None])
    gains = outcomes[outcomes > 0]
    return dict(winning_trades=len(gains), completed_trades=len(outcomes),
                winner_sigma=float(np.std(gains, ddof=1)) if len(gains) >= 5 else None,
                winner_mean=float(np.mean(gains)) if len(gains) else None,
                all_trade_sigma=float(np.std(outcomes, ddof=1)) if len(outcomes) >= 2 else None,
                training_end=str(f.days[-1]), cost_bp=cost_bp)


class LossController(HealthController):
    def observe_loss(self, trade, *, severity=False, losing_stop=False):
        decision = super().observe(trade)
        if trade.shadow:
            return decision
        if severity:
            if self.mode != Mode.PAUSED:
                self._change(Mode.PAUSED, trade.known_session)
            return replace(decision, mode=Mode.PAUSED, risk_multiplier=0.,
                           allow_new_entry=False, request_refit=True, reason="single_large_loss")
        if losing_stop and self.mode == Mode.NORMAL:
            self._change(Mode.DEFENSIVE, trade.known_session)
            return replace(decision, mode=Mode.DEFENSIVE, risk_multiplier=.5,
                           reason="losing_protective_exit")
        return decision


def simulate(f, cl, calibration, *, start, arm="severity", cost_bp=5, delay=0):
    if arm not in ARMS or not isinstance(delay, int) or delay < 0 or not 0 <= cost_bp < 10000:
        raise ValueError("Invalid arm/friction")
    if start < 0 or start >= len(f.days)-1:
        raise ValueError("Need signal anchor and evaluation sessions")
    p, n, lag = cl['parameters'], len(f.days), 1+delay
    fee = cost_bp/10000
    sigma_g = calibration['winner_sigma']
    if sigma_g is not None and (not np.isfinite(sigma_g) or sigma_g < 0):
        raise ValueError("Invalid training winner dispersion")
    threshold = max(sigma_g, 2*fee, 1e-6) if sigma_g is not None else None
    reference = coupled_trends.simulate(f, cl, start=start, cost_bp=cost_bp, delay=delay)
    shadow_exits = {e['exit_index']: e for e in reference['episodes'] if e['exit_index'] is not None}
    controller = LossController("frozen-policy")
    nav = np.full(n, np.nan)
    desired, held, exposure = np.zeros(n), np.zeros(n, bool), np.zeros(n)
    stops = np.full(n, np.nan)
    modes = np.full(n, "normal", dtype="U12")
    reasons = np.full(n, "", dtype="U32")
    entry_risks = np.full(n, np.nan)
    targets, episodes, events, health_events, fills = {}, [], [], [], []
    cash, units, target, armed = 1., 0., False, True
    target_weight = 0.
    level = peak = entry_open = entry_risk = np.nan
    episode = None

    def decision_record(d, t, source):
        if d.reason != "continue":
            health_events.append(dict(session=int(t), day=str(f.days[t]), mode=str(d.mode),
                reason=d.reason, source=source, loss_streak=d.loss_streak,
                review_requested=d.request_refit, earliest_effective_session=d.earliest_effective_session))

    for t in range(start, n):
        if t in targets:
            order = targets[t]
            if order['side'] == 'buy':
                if units:
                    raise ValueError("Overlapping entry")
                budget = order['weight']*cash
                units = budget/(f.open[t]*(1+fee))
                cash -= budget
                entry_open = float(f.open[t])
                entry_risk = entry_open*cl['sigma']
                level = entry_open-order['distance']*entry_risk
                peak = entry_open
                episode = dict(entry_index=t, entry=float(entry_open), entry_signal=order['signal'],
                    entry_weight=order['weight'], initial_risk_fraction=order['distance']*cl['sigma'],
                    exit_index=None, exit_price=None, exit_signal=None, exit_reason=None,
                    entry_mode=order['mode'])
                episodes.append(episode)
                fills.append(dict(session=t, side='buy', units=float(units), price=float(f.open[t]),
                                  fee=float(units*f.open[t]*fee)))
            else:
                if not units or episode is None:
                    raise ValueError("Exit without a position")
                proceeds = units*f.open[t]
                fills.append(dict(session=t, side='sell', units=float(units), price=float(f.open[t]),
                                  fee=float(proceeds*fee)))
                cash += proceeds*(1-fee)
                units = 0.
                outcome = f.open[t]/entry_open*(1-fee)/(1+fee)-1
                episode.update(exit_index=t, exit_price=float(f.open[t]), exit_signal=order['signal'],
                               exit_reason=order['reason'], net_return=float(outcome))
                if arm != 'fixed':
                    trade = ClosedTrade(f"actual-{t}", "frozen-policy", episode['entry_index'], t, t,
                                        float(outcome), episode['initial_risk_fraction'])
                    large = arm == 'severity' and (order['reason'] == 'large_mark_loss' or
                        (threshold is not None and outcome < -threshold))
                    d = controller.observe_loss(trade, severity=large,
                        losing_stop=arm == 'severity' and order['reason'] == 'protection' and outcome < 0)
                    decision_record(d, t, 'actual')
                level = peak = np.nan

        # The frozen reference continues regardless of our actual allocations.
        if arm != 'fixed' and controller.mode == Mode.PAUSED and t in shadow_exits:
            e = shadow_exits[t]
            if e['entry_index'] > max(controller.phase_started, controller.shadow_available):
                risk = p['wide'] if p['context'] and cl['aligned'][e['entry_signal']] else p['tight']
                outcome = e['exit_price']/e['entry']*(1-fee)/(1+fee)-1
                trade = ClosedTrade(f"shadow-{t}", "frozen-policy", e['entry_index'], t, t,
                                    float(outcome), float(risk*cl['sigma']), True)
                decision_record(controller.observe_loss(trade), t, 'shadow')

        mode = controller.mode if arm != 'fixed' else Mode.NORMAL
        modes[t] = str(mode)
        active = units > 0
        held[t] = active
        if cl['fast_probability'][t, 2] < p['reset']:
            armed = True
        defensive = mode in (Mode.DEFENSIVE, Mode.PROBATION)
        multiplier = (p['wide'] if p['context'] and cl['aligned'][t] else p['tight'])
        if defensive:
            multiplier *= .5
        fast_down = cl['fast_down'][t] or (defensive and cl['fast_probability'][t, 0] >= .6)
        stop_hit = active and f.close[t] < level
        mark_loss = (arm == 'severity' and active and threshold is not None and
                     f.close[t]/entry_open*(1-fee)/(1+fee)-1 < -threshold)
        if target and (fast_down or stop_hit or mark_loss):
            target, armed = False, False
            reason = 'large_mark_loss' if mark_loss else 'protection' if stop_hit else 'fast_down'
            reasons[t] = reason
            order = dict(side='sell', reason=reason, signal=t)
            targets[t+lag] = order
            events.append(dict(day=t, side='sell', fill=t+lag, reason=reason))
        elif not target and not active and armed and cl['eligible'][t] and mode != Mode.PAUSED:
            target, armed = True, False
            weight = {Mode.NORMAL: 1., Mode.DEFENSIVE: .5, Mode.PROBATION: .25}[mode]
            target_weight = weight
            targets[t+lag] = dict(side='buy', weight=weight, distance=multiplier, signal=t, mode=str(mode))
            reasons[t] = 'fast_up'
            events.append(dict(day=t, side='buy', fill=t+lag, reason='fast_up', weight=weight))
        if active:
            stops[t] = level
            entry_risks[t] = episode['initial_risk_fraction']
            peak = max(peak, f.close[t])
            level = max(level, peak-multiplier*entry_risk)
        if target:
            desired[t] = target_weight
        nav[t] = cash+units*f.close[t]
        exposure[t] = units*f.close[t]/nav[t]
    return dict(nav=nav, desired=desired, held=held, exposure=exposure, stop=stops, modes=modes,
                reason=reasons, episodes=episodes, events=events, health_events=health_events,
                fills=fills, threshold=threshold, initial_risk=entry_risks)
