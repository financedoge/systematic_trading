"""Research-only strategy-health state machine; no order or fitting authority.

Events are completed, net-of-cost trades. A decision is usable no earlier than
the session after its evidence becomes known. Shadow results can restore a paused
strategy only if their entries occurred after the pause/candidate was available.
This module does not simulate the trades changed by its decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, log1p


class Mode(StrEnum):
    NORMAL = "normal"
    DEFENSIVE = "defensive"
    PAUSED = "paused"
    PROBATION = "probation"


@dataclass(frozen=True)
class HealthConfig:
    defensive_losses: int = 3
    pause_losses: int = 4
    defensive_recovery_wins: int = 2
    shadow_trades: int = 4
    shadow_wins: int = 3
    probation_trades: int = 3
    probation_wins: int = 2
    probation_pause_losses: int = 2
    defensive_risk: float = .5
    probation_risk: float = .25
    trade_half_life: float = 4.

    def __post_init__(self):
        counts = (self.defensive_losses, self.pause_losses,
                  self.defensive_recovery_wins, self.shadow_trades,
                  self.shadow_wins, self.probation_trades,
                  self.probation_wins, self.probation_pause_losses)
        if any(not isinstance(x, int) or isinstance(x, bool) or x < 1 for x in counts):
            raise ValueError("Counts must be positive integers")
        if not self.defensive_losses < self.pause_losses:
            raise ValueError("Defensive threshold must precede pause")
        if self.shadow_wins > self.shadow_trades or self.probation_wins > self.probation_trades:
            raise ValueError("Recovery wins cannot exceed its observation count")
        if not 0 < self.probation_risk <= self.defensive_risk <= 1:
            raise ValueError("Invalid risk multipliers")
        if not isfinite(self.trade_half_life) or self.trade_half_life <= 0:
            raise ValueError("Invalid trade half life")


@dataclass(frozen=True)
class ClosedTrade:
    trade_id: str
    policy_id: str
    entry_session: int
    exit_session: int
    known_session: int
    net_return: float
    initial_risk_fraction: float
    shadow: bool = False

    def validate(self):
        if not self.trade_id or not self.policy_id:
            raise ValueError("Trade and policy identities are required")
        if any(not isinstance(x, int) or isinstance(x, bool)
               for x in (self.entry_session, self.exit_session, self.known_session)):
            raise ValueError("Sessions must be integer calendar indices")
        if not 0 <= self.entry_session <= self.exit_session <= self.known_session:
            raise ValueError("Entry, exit and known sessions must be chronological")
        if not isfinite(self.net_return) or self.net_return <= -1:
            raise ValueError("Invalid funded net trade return")
        if not isfinite(self.initial_risk_fraction) or self.initial_risk_fraction <= 0:
            raise ValueError("Entry-time risk must be positive and known")


@dataclass(frozen=True)
class HealthDecision:
    mode: Mode
    risk_multiplier: float
    allow_new_entry: bool
    request_refit: bool
    earliest_effective_session: int
    reason: str
    policy_id: str
    loss_streak: int
    ewma_r: float | None
    ewma_win_rate: float | None


class HealthController:
    """One controller per ETF/strategy; market-regime labels are separate.

    Actual outcomes govern trading modes. During a pause only a single declared
    shadow candidate supplies recovery evidence. Refit requests are events, not
    automatic replacement permission. A new candidate must pass fresh shadow
    observations; fitting to the triggering losses never counts as recovery.
    """

    def __init__(self, policy_id: str, config: HealthConfig | None = None):
        if not policy_id:
            raise ValueError("Policy identity required")
        self.config = config or HealthConfig()
        self.policy_id = policy_id
        self.shadow_policy_id = policy_id
        self.mode = Mode.NORMAL
        self.loss_streak = self.win_streak = 0
        self.last_known = -1
        self.phase_started = -1
        self.shadow_available = -1
        self.phase_r: list[float] = []
        self.phase_log: list[float] = []
        self.candidate_staged = False
        self.seen: set[str] = set()
        self._mass = self._r_sum = self._win_sum = 0.

    def stage_shadow_candidate(self, policy_id: str, *, fit_cutoff: int, available_session: int):
        """Declare one refit before observing its new forward trades."""
        if self.mode != Mode.PAUSED or not policy_id or self.candidate_staged:
            raise ValueError("A candidate can only be staged during a pause")
        if fit_cutoff < 0 or fit_cutoff >= available_session or available_session < self.last_known:
            raise ValueError("Candidate must be available after its training cutoff")
        self.shadow_policy_id = policy_id
        self.shadow_available = available_session
        self.phase_r = []
        self.phase_log = []
        self.candidate_staged = True

    def _change(self, mode: Mode, session: int):
        self.mode = mode
        self.phase_started = session
        self.phase_r = []
        self.phase_log = []
        self.win_streak = 0
        if mode == Mode.PAUSED:
            self.shadow_policy_id = self.policy_id
            self.shadow_available = session
            self.candidate_staged = False
        elif mode in (Mode.NORMAL, Mode.PROBATION):
            self.loss_streak = 0

    def observe(self, trade: ClosedTrade) -> HealthDecision:
        trade.validate()
        if trade.trade_id in self.seen:
            raise ValueError("Duplicate outcome")
        if trade.known_session < self.last_known:
            raise ValueError("Outcomes must arrive in known-time order")
        expected = self.shadow_policy_id if trade.shadow else self.policy_id
        if trade.policy_id != expected:
            raise ValueError("Unexpected policy version")
        if trade.shadow != (self.mode == Mode.PAUSED):
            raise ValueError("Use actual outcomes while active, shadow outcomes while paused")
        if trade.shadow and trade.entry_session <= max(self.phase_started, self.shadow_available):
            raise ValueError("Recovery must use fresh post-pause/candidate entries")
        if self.mode == Mode.PROBATION and trade.entry_session <= self.phase_started:
            raise ValueError("Probation requires entries after recovery evidence")
        self.seen.add(trade.trade_id)
        self.last_known = trade.known_session
        r = trade.net_return / trade.initial_risk_fraction
        cfg = self.config
        request = False
        reason = "continue"
        if trade.shadow:
            self.phase_r.append(r)
            self.phase_log.append(log1p(trade.net_return))
            sample = self.phase_r[-cfg.shadow_trades:]
            if (len(sample) == cfg.shadow_trades and
                    sum(x > 0 for x in sample) >= cfg.shadow_wins and sum(sample) > 0
                    and sum(self.phase_log[-cfg.shadow_trades:]) > 0):
                self.policy_id = self.shadow_policy_id
                self._change(Mode.PROBATION, trade.known_session)
                reason = "fresh_shadow_recovery"
        else:
            decay = 2 ** (-1 / cfg.trade_half_life)
            self._mass = decay * self._mass + 1
            self._r_sum = decay * self._r_sum + r
            self._win_sum = decay * self._win_sum + (r > 0)
            self.loss_streak = self.loss_streak + 1 if r < 0 else 0
            self.win_streak = self.win_streak + 1 if r > 0 else 0
            self.phase_r.append(r)
            self.phase_log.append(log1p(trade.net_return))
            if self.mode == Mode.PROBATION:
                if self.loss_streak >= cfg.probation_pause_losses:
                    self._change(Mode.PAUSED, trade.known_session)
                    request, reason = True, "probation_failed"
                else:
                    sample = self.phase_r[-cfg.probation_trades:]
                    if (len(sample) == cfg.probation_trades and
                            sum(x > 0 for x in sample) >= cfg.probation_wins and sum(sample) > 0
                            and sum(self.phase_log[-cfg.probation_trades:]) > 0):
                        self._change(Mode.NORMAL, trade.known_session)
                        reason = "probation_passed"
            elif self.loss_streak >= cfg.pause_losses:
                self._change(Mode.PAUSED, trade.known_session)
                request, reason = True, "four_losses_refit_review"
            elif self.mode == Mode.NORMAL and self.loss_streak >= cfg.defensive_losses:
                self._change(Mode.DEFENSIVE, trade.known_session)
                reason = "three_losses_defensive"
            elif (self.mode == Mode.DEFENSIVE and self.win_streak >= cfg.defensive_recovery_wins
                  and sum(self.phase_r) > 0 and sum(self.phase_log) > 0):
                self._change(Mode.NORMAL, trade.known_session)
                reason = "defensive_recovery"
        multiplier = {Mode.NORMAL: 1., Mode.DEFENSIVE: cfg.defensive_risk,
                      Mode.PAUSED: 0., Mode.PROBATION: cfg.probation_risk}[self.mode]
        return HealthDecision(self.mode, multiplier, self.mode != Mode.PAUSED,
                              request, trade.known_session + 1, reason, self.policy_id,
                              self.loss_streak, self._r_sum / self._mass if self._mass else None,
                              self._win_sum / self._mass if self._mass else None)


def loss_streaks(net_returns: list[float]) -> list[int]:
    """Diagnostic only: a zero net outcome breaks a consecutive-loss run."""
    streak, result = 0, []
    for value in net_returns:
        if not isfinite(value):
            raise ValueError("Closed outcomes cannot be missing")
        streak = streak + 1 if value < 0 else 0
        result.append(streak)
    return result
