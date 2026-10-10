"""Signal-health projection: joins published decay evidence to allocation state.

One source of truth for the dashboard panel, the operator warning and the durable
alert, so the three can never disagree about whether a strategy's key signal has
decayed.

Decision support only. Nothing here changes a target, an allocation, an approval
or a broker record.
"""
from __future__ import annotations

from decimal import Decimal
import json

SEVERITY = {"insufficient": 0, "healthy": 1, "weakening": 2, "decayed": 3}
LABEL = {"insufficient": "Insufficient evidence", "healthy": "Healthy",
         "weakening": "Weakening", "decayed": "Decayed"}


def report(analytics):
    """The last published decay report, or None when it has never run."""
    documents = analytics.document("signal-decay/report", "report")
    if not documents:
        return None
    payload = documents[0].get("payload")
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) and parsed.get("signals") else None


def worst(records) -> str:
    """Most severe status across a strategy's key signals."""
    statuses = [r.get("status", "insufficient") for r in records]
    return max(statuses, key=lambda s: SEVERITY.get(s, 0)) if statuses else "insufficient"


def _allocations(state):
    """Active allocation weights by strategy key, from the control state."""
    active = (state or {}).get("active") or {}
    weights = {}
    for row in active.get("allocations") or []:
        key = row.get("strategy_key")
        if not key:
            continue
        try:
            weights[key] = weights.get(key, Decimal(0)) + Decimal(str(row.get("weight", "0")))
        except (ArithmeticError, ValueError):
            continue
    return weights


def health(report_data, state, definitions=None):
    """Per-strategy decay status joined to the current allocation.

    ``state`` is ``portfolio.strategy_allocation.control_state`` output. A row is
    flagged ``funded`` when the strategy currently carries allocation weight, so
    the operator can tell a live holding from a monitored-but-unfunded recipe.
    Only the *active* allocation counts; a pending change is not yet at risk.
    """
    if not report_data:
        return []
    records = {r["name"]: r for r in report_data.get("signals", [])}
    weights = _allocations(state)
    active_keys = set(weights)
    sota_key = (state or {}).get("sota_key")
    rows = []
    for key, names in (report_data.get("key_signals") or {}).items():
        present = [records[n] for n in names if n in records]
        if not present:
            continue
        status = worst(present)
        weight = weights.get(key)
        rows.append(dict(
            strategy_key=key,
            name=(definitions or {}).get(key, key),
            status=status,
            label=LABEL.get(status, status),
            funded=bool(weight and weight > 0),
            allocation_weight=None if weight is None else str(weight),
            is_active=key in active_keys,
            is_sota=key == sota_key,
            signals=[dict(name=r["name"], label=r["label"], status=r["status"],
                          reason=r["reason"], long_run_ic=r["long_run_ic"],
                          recent_ic=r["recent_ic"], ic_ir=r["ic_ir"], hit_rate=r["hit_rate"],
                          half_life_sessions=r["half_life_sessions"],
                          breakeven_ic=r["breakeven_ic"], ic_curve=r["ic_curve"],
                          observations=r["observations"]) for r in present],
            reason="; ".join(f"{r['label']}: {r['reason']}" for r in present
                             if r["status"] == status),
        ))
    rows.sort(key=lambda row: (-SEVERITY.get(row["status"], 0), not row["funded"], row["strategy_key"]))
    return rows


def warnings(rows):
    """Decayed or weakening strategies that currently carry allocation.

    Unfunded strategies are reported in the panel but deliberately do not raise an
    operator warning: nothing is at risk until capital is committed.
    """
    flagged = []
    for row in rows:
        if row["status"] in {"decayed", "weakening"} and row["funded"]:
            weight = Decimal(row["allocation_weight"] or "0")
            flagged.append(dict(
                kind="decayed" if row["status"] == "decayed" else "weakening",
                strategy_key=row["strategy_key"],
                name=row["name"],
                status=row["status"],
                label=row["label"],
                allocation_weight=str(weight),
                allocation_pct=f"{weight:.1%}",
                is_active=row["is_active"],
                is_sota=row["is_sota"],
                reason=row["reason"],
                message=(f"{row['name']} holds {weight:.1%} of the portfolio and its key signal is "
                         f"{row['label'].lower()}: {row['reason']}"),
            ))
    return flagged


def coverage_gaps(report_data):
    """Signals the strategies use that the diagnostic cannot yet measure."""
    return list((report_data or {}).get("coverage_gaps") or [])


def headline(report_data, rows):
    """Compact summary for a panel header or an API response."""
    if not report_data:
        return dict(available=False,
                    message="No signal-decay publication yet. The diagnostic has not completed a run.")
    counts = {name: 0 for name in SEVERITY}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return dict(
        available=True,
        decisions=report_data.get("decisions"),
        first_decision=report_data.get("first_decision"),
        last_decision=report_data.get("last_decision"),
        batch=report_data.get("batch"),
        horizons=report_data.get("horizons"),        counts=counts,
        funded_at_risk=sum(1 for row in rows if row["funded"] and row["status"] in {"decayed", "weakening"}),
        coverage_gap_count=len(coverage_gaps(report_data)),
    )
