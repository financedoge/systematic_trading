"""P4.15 — turnover and breakeven-IC gate (standing pre-test).

Registered 2026-10-10 in ``docs/signal-decay-and-alpha-plan.md`` and frozen here
before any later item in the programme consumes it. The question it answers, for a
candidate overlay and before any portfolio work: **how much turnover does the
mapping imply, what does that cost at the frozen 5bp, and what IC must the signal
earn to survive it?**

One implementation of the cost arithmetic. ``breakeven_ic`` delegates to
``signal_decay.breakeven_ic`` so the programme keeps a single definition; the gate
adds the implied-turnover mapping, the frozen thresholds and the verdict.

Two turnover conventions exist in this programme and they are **not**
interchangeable:

* **traded-notional turnover** = traded notional / pre-trade NAV, accumulated over a
  replay and annualised (:func:`systematic_trading.research.momentum_analysis.statistics`).
  This is what the cost is actually charged on, it is the measure behind the plan's
  "~8x turnover and ~40bp annual drag", and it is the gate's convention.
* **selection-change proxy** = the fraction of the top-slot set replaced per decision,
  annualised (:func:`systematic_trading.research.signal_decay_job.turnover_and_sigma`).
  It ignores rebalancing drift, cash-flow trades and intra-rebalance adjustments, so
  it understates the first. It is a decay diagnostic, not a cost basis.

The implied measure below is the gate's screening basis and was **calibrated** against
the programme's own frozen replays rather than assumed. Measured result over 217
replays (see :mod:`systematic_trading.research.turnover_gate_analysis`): the implied
number tracks the measured traded-notional turnover to within 3.5%, and it is very
slightly **conservative** — measured/implied has a median of 0.985 with an
interquartile range of [0.984, 0.986] — because the engine trades to targets only in
whole adjusted units and beyond its target tolerance, so sub-threshold target changes
never trade while the mapping still counts them. Screening therefore uses the implied
value **directly and with no correction factor**: that choice produced zero false
passes across the 217 replays, while applying the median ratio introduced one. A
candidate whose cost profile sits within a few percent of the ceiling must still be
replayed before a decision is taken.
"""
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from systematic_trading.research.signal_decay import breakeven_ic

VERSION = 'turnover-gate-v1'
FROZEN_COST_BPS = 5.0
SESSIONS_PER_YEAR = 252
DEFAULT_PERIOD_SESSIONS = 21

# The strongest IC this programme has measured (m1_total, recent, P4.13). A candidate
# that declares no IC of its own is judged against it, and a signal weaker than the
# best one measured here cannot clear a cost that this fails.
PROGRAMME_REFERENCE_IC = 0.0943

# Frozen before the calibration study was run, and not revised after it.
THRESHOLDS = dict(
    version=VERSION,
    cost_bps=FROZEN_COST_BPS,
    period_sessions=DEFAULT_PERIOD_SESSIONS,
    # The monitored strategy's measured drag on the traded-notional convention is
    # 40.4bp (8.07x at 5bp), so the ceiling is that drag rounded to 40bp. The 10%
    # tolerance covers the gap between the implied mapping and a measured replay, and
    # it is disclosed rather than tuned: a candidate at 45bp is rejected.
    max_annual_cost_bps=40.0,
    cost_tolerance=0.10,
    # The breakeven formula deliberately omits the selection-intensity multiplier and
    # ignores estimation error, so the required cushion is 3x. The monitored signal
    # clears it by ~15x; Alpha101's median archetype does not clear it at all.
    min_ic_margin=3.0,
)


def implied_turnover(weights_by_decision: Mapping[str, Mapping[str, Any]]) -> dict:
    """Implied annual one-way turnover from a signal-to-position mapping.

    ``weights_by_decision`` maps a decision date to that decision's target weights by
    symbol. The first decision is charged as establishing the book from cash, which is
    how the traded-notional convention charges it. The result assumes every target
    change trades; measured against 217 frozen replays it lands within 3.5% of the
    traded-notional figure and is very slightly conservative, which is why it is used
    for screening without a correction factor.
    """
    days = sorted(weights_by_decision)
    if len(days) < 2:
        raise ValueError('Implied turnover needs at least two decisions to annualise')
    if len(days) != len(set(days)):
        raise ValueError('Decision calendar contains duplicates')
    traded, rows = 0.0, []
    previous: dict[str, float] | None = None
    for day in days:
        weights = {str(s): float(w) for s, w in weights_by_decision[day].items()}
        if any(not _finite(w) for w in weights.values()):
            raise ValueError('Nonfinite target weight on ' + day)
        if any(w < 0 for w in weights.values()):
            raise ValueError('Long-only gate: negative target weight on ' + day)
        if previous is None:
            moved = sum(abs(w) for w in weights.values())
        else:
            moved = sum(abs(weights.get(s, 0.0) - previous.get(s, 0.0))
                        for s in set(weights) | set(previous))
        if moved > 2.0 + 1e-9:
            raise ValueError('Turnover above two times NAV on a single decision: ' + day)
        traded += moved
        rows.append(dict(decision=day, traded_notional=moved, gross=sum(weights.values())))
        previous = weights
    span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days / 365.25
    if span <= 0:
        raise ValueError('Decision calendar does not span a positive period')
    return dict(version=VERSION, decisions=len(days), first=days[0], last=days[-1], years=span,
                total_traded_notional=traded, annual_turnover=traded / span,
                mean_traded_per_decision=traded / len(days),
                max_traded_per_decision=max(row['traded_notional'] for row in rows), rows=rows)


def annual_cost_bps(turnover: float, cost_bps: float = FROZEN_COST_BPS) -> float:
    """Annual trading drag in basis points, on the traded-notional convention."""
    if turnover is None or turnover < 0 or not _finite(turnover):
        raise ValueError('Turnover must be finite and non-negative')
    if cost_bps is None or cost_bps < 0 or not _finite(cost_bps):
        raise ValueError('Cost must be finite and non-negative')
    return float(turnover) * float(cost_bps)


def calibrate(implied: float, measured: float) -> dict:
    """The measured replay beside the implied mapping.

    Which way the gap points is an empirical question, not an assumption: the
    calibration study measures it on the programme's own replays and reports the
    direction, so a candidate can be screened on the conservative side.
    """
    if implied is None or implied <= 0:
        raise ValueError('Calibration needs a positive implied turnover')
    if measured is None or measured < 0:
        raise ValueError('Calibration needs a non-negative measured turnover')
    return dict(implied_turnover=float(implied), measured_turnover=float(measured),
                measured_over_implied=float(measured) / float(implied),
                implied_is_conservative=bool(measured <= implied))


def screen(
    annual_turnover: float,
    *,
    sigma: float | None,
    candidate_ic: float | None = None,
    cost_bps: float = FROZEN_COST_BPS,
    period_sessions: int = DEFAULT_PERIOD_SESSIONS,
    thresholds: Mapping[str, Any] = THRESHOLDS,
) -> dict:
    """The frozen two-test verdict for one candidate cost profile.

    Test 1 — cost ceiling: the annual drag at the frozen cost must not exceed the
    monitored book's drag plus the disclosed tolerance.
    Test 2 — IC margin: the candidate's IC must exceed the breakeven IC by the
    frozen factor.

    A missing dispersion cannot be judged and returns ``insufficient`` rather than a
    silent pass.
    """
    cost = annual_cost_bps(annual_turnover, cost_bps)
    ceiling = float(thresholds['max_annual_cost_bps']) * (1.0 + float(thresholds['cost_tolerance']))
    ic = PROGRAMME_REFERENCE_IC if candidate_ic is None else float(candidate_ic)
    breakeven = breakeven_ic(annual_turnover, sigma, cost_bps=cost_bps, period_sessions=period_sessions)
    margin = None if breakeven in (None, 0) else ic / breakeven
    if breakeven is None or sigma is None or sigma <= 0:
        status, cost_test, margin_test = 'insufficient', cost <= ceiling, None
        reasons = ['forward-return dispersion is unavailable, so the IC requirement cannot be judged']
    else:
        cost_test = bool(cost <= ceiling)
        margin_test = bool(margin >= float(thresholds['min_ic_margin']))
        status = 'pass' if (cost_test and margin_test) else 'reject'
        reasons = []
        if not cost_test:
            reasons.append(f'annual cost {cost:.1f}bp exceeds the {ceiling:.1f}bp ceiling')
        if not margin_test:
            reasons.append(f'IC margin {margin:.2f}x is below the required '
                           f'{float(thresholds["min_ic_margin"]):.1f}x against a breakeven IC of {breakeven:.4f}')
        if not reasons:
            reasons.append(f'cost {cost:.1f}bp is inside the ceiling and the IC margin {margin:.2f}x clears '
                           f'the requirement')
    return dict(version=VERSION, status=status, cost_test=cost_test, margin_test=margin_test,
                annual_turnover=float(annual_turnover), annual_cost_bps=cost, cost_ceiling_bps=ceiling,
                breakeven_ic=breakeven, candidate_ic=ic, ic_margin=margin,
                sigma=sigma, cost_bps=cost_bps, period_sessions=period_sessions,
                thresholds=dict(thresholds), reasons=reasons)


def archetypes() -> list[dict]:
    """The registered Alpha101 turnover archetypes, from the plan's Appendix A."""
    return [dict(name='alpha101 fastest', annual_turnover=404.0, source='tau=1.604, holding 0.62 sessions'),
            dict(name='alpha101 median', annual_turnover=120.0, source='tau=0.475, holding 2.10 sessions'),
            dict(name='alpha101 slowest', annual_turnover=40.0, source='tau=0.157, holding 6.37 sessions'),
            dict(name='monitored strategy', annual_turnover=8.07, source='measured traded notional / NAV, FR25')]


def assess_archetypes(*, sigma: float, candidate_ic: float | None = None,
                      cost_bps: float = FROZEN_COST_BPS) -> list[dict]:
    """Apply the frozen gate to each registered archetype."""
    return [dict(entry, **screen(entry['annual_turnover'], sigma=sigma, candidate_ic=candidate_ic,
                                 cost_bps=cost_bps)) for entry in archetypes()]


def format_bps(value: float | None) -> str:
    return 'n/a' if value is None else f'{value:,.1f}bp'


def format_multiple(value: float | None) -> str:
    return 'n/a' if value is None else f'{value:,.2f}x'


def weights_from_targets(targets: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Target rows to a weight mapping, for use with :func:`implied_turnover`."""
    out: dict[str, float] = {}
    for row in targets:
        symbol, weight = str(row['symbol']), Decimal(str(row['target_weight']))
        if not weight.is_finite() or weight < 0:
            raise ValueError('Long-only gate: invalid target weight for ' + symbol)
        out[symbol] = float(weight)
    return out


def _finite(value: float) -> bool:
    return value == value and value not in (float('inf'), float('-inf'))
