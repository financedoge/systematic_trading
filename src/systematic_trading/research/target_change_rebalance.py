"""Finite research adoption policy; deliberately has no holdings or broker input."""
from datetime import date
from decimal import Decimal as D

import numpy as np


def target_weights(row):
    targets = row['targets']
    weights = {t['symbol']: D(str(t['target_weight'])) for t in targets}
    if (len(weights) != len(targets) or 'CASH' in weights
            or any(not w.is_finite() or w < 0 for w in weights.values())
            or sum(weights.values()) > 1):
        raise ValueError('Invalid long-only target vector')
    weights['CASH'] = 1 - sum(weights.values())
    return weights


def distance(left, right):
    return sum(abs(left.get(s, D(0)) - right.get(s, D(0))) for s in left.keys() | right.keys())


def adoption_schedule(tape, monthly, policy, *, switches=None):
    """Keys are intended next-open sessions; known_through is the signal close.

    Missing targets fail closed, including a scheduled adoption. Logical adoption
    updates the anchor before any execution, independent of cash and rounding.
    Walk-forward switches are effective only at the named monthly event.
    """
    if not tape or sorted(tape) != list(tape):
        raise ValueError('A nonempty ordered target tape is required')
    monthly = set(monthly)
    switches = switches or {}
    if not set(switches) <= monthly:
        raise ValueError('Policy switches must occur at monthly events')
    anchor = None
    decisions, ledger = {}, []
    for day, row in tape.items():
        if row['signal_session'] != day or row['known_through'] >= day:
            raise ValueError('Target availability violation')
        if day in switches:
            policy = switches[day]
        if policy not in ('monthly', 'daily') and not D(policy) > 0:
            raise ValueError('Positive threshold required')
        latest = target_weights(row)
        gap = distance(latest, anchor) if anchor is not None else None
        crossed = gap is not None and policy not in ('monthly', 'daily') and gap > D(policy)
        reasons = (['initial'] if anchor is None else [])
        if day in monthly:
            reasons.append('monthly')
        if policy == 'daily':
            reasons.append('daily')
        if crossed:
            reasons.append('threshold')
        adopt = bool(reasons)
        ledger.append(dict(signal_session=day, known_through=row['known_through'], policy=policy,
            distance=None if gap is None else str(gap), adopted=adopt,
            primary_reason=('initial' if anchor is None else 'monthly' if day in monthly else reasons[0]) if adopt else None,
            reasons=reasons, anchor_before=None if anchor is None else {s:str(w) for s,w in anchor.items()},
            latest={s:str(w) for s,w in latest.items()}))
        if adopt:
            decisions[day] = row
            anchor = latest
    return decisions, ledger


def execution_schedule(decisions, sessions, delay):
    if delay not in (0, 1):
        raise ValueError('Unregistered delay')
    index = {d:i for i,d in enumerate(sessions)}
    executed, pending = {}, []
    for day, row in decisions.items():
        i = index.get(day)
        if i is None or i + delay >= len(sessions):
            pending.append(row)
        else:
            executed[sessions[i+delay]] = row
    return executed, pending


def window_metrics(economic, start, end, *, initial=1_000_000, turnover_by_day=None):
    """Include the opening NAV immediately before the requested window."""
    all_rows = economic['nav']
    indices = [i for i,r in enumerate(all_rows) if start <= r['date'] <= end]
    if len(indices) < 2:
        raise ValueError('Insufficient window')
    first, last = indices[0], indices[-1]
    opening = float(all_rows[first-1]['nav']) if first else initial
    nav = np.array([opening] + [float(r['nav']) for r in all_rows[first:last+1]])
    returns = nav[1:]/nav[:-1]-1
    years = (date.fromisoformat(all_rows[last]['date']) - date.fromisoformat(all_rows[first]['date'])).days/365.25
    vol = float(returns.std(ddof=1))
    turnover = sum((turnover_by_day or {}).get(r['date'], 0.) for r in all_rows[first:last+1])
    return dict(start=all_rows[first]['date'], end=all_rows[last]['date'], opening_nav=opening,
        closing_nav=float(nav[-1]), cagr=float((nav[-1]/opening)**(1/years)-1),
        sharpe=float(returns.mean()/vol*np.sqrt(252)) if vol else 0.,
        max_drawdown=float(np.min(nav/np.maximum.accumulate(nav)-1)),
        annual_turnover=turnover/years, sessions=len(returns))


def guards(candidate, baseline, minimum_sharpe):
    return (candidate['sharpe'] - baseline['sharpe'] >= minimum_sharpe
        and candidate['cagr'] >= baseline['cagr'] - .005
        and candidate['max_drawdown'] >= baseline['max_drawdown'] - .02)


def select_threshold(grid, metrics):
    """metrics[policy][scenario]; stress positivity is strict, as registered."""
    passing = {}
    for x in grid:
        passing[x] = guards(metrics[x]['5-0'], metrics['monthly']['5-0'], .05) and all(
            guards(metrics[x][s], metrics['monthly'][s], 0.)
            and metrics[x][s]['sharpe'] > metrics['monthly'][s]['sharpe'] for s in ('10-0','5-1'))
    eligible = [x for i,x in enumerate(grid) if passing[x] and any(
        passing[grid[j]] for j in (i-1,i+1) if 0 <= j < len(grid))]
    plateau = []
    if eligible:
        best = max(metrics[x]['5-0']['sharpe'] for x in eligible)
        plateau = [x for x in eligible if metrics[x]['5-0']['sharpe'] >= best-.02]
    selected = min(plateau, key=lambda x:(metrics[x]['5-0']['annual_turnover'], -D(x))) if plateau else 'monthly'
    return dict(selected=selected, passing=passing, eligible=eligible, plateau=plateau, metrics=metrics)
