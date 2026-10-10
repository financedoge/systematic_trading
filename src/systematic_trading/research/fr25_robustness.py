"""P4.14 Part A — FR25 robustness stress over the published selection-blend evidence.

Analysis only: it reads the frozen study's published replays and never re-runs a
portfolio. The retention tolerance it applies was frozen in
``docs/signal-decay-and-alpha-plan.md`` **before** any statistic here was computed.

Part B of P4.14 (matched-availability placebo rank, data-through-2022 refit,
top-N and financial-weight sensitivity) cannot be evaluated from published
artifacts, because each perturbation changes which assets were selected and
therefore the realised path. It needs its own frozen study and is not attempted
here.

Not promotion evidence and not a deallocation: a reject result is a research
finding, and switching or deallocating stays an operator decision through the
existing allocation workflow.
"""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256
from systematic_trading.research.momentum_analysis import paired_bootstrap

STUDY_ROOT = Path("var/research/selection-blend-20261010-v1")
CANDIDATE_ARM = "FR25"
CONTROL_ARM = "CP"
COST_BPS = 5
DELAY = 0
EVALUATION = "evaluation"

# Frozen retention tolerance. Declared before outcomes; do not revise after
# results are seen.
TOLERANCE = dict(
    positive_year_share=2 / 3,
    block_for_lower_bound=6,
    placebo_percentile=0.90,
    selection_tolerance=Decimal("1e-12"),
)


def _arm_path(root: Path, arm: str) -> Path:
    return root / "python" / f"{arm}-cost{COST_BPS}-delay{DELAY}-{EVALUATION}.json"


def load(root: Path = STUDY_ROOT) -> dict:
    """Load the frozen reference pair and its input hashes."""
    candidate_path, control_path = _arm_path(root, CANDIDATE_ARM), _arm_path(root, CONTROL_ARM)
    if not candidate_path.exists() or not control_path.exists():
        raise FileNotFoundError("published evaluation replays for FR25 and CP are required")
    candidate = json.loads(candidate_path.read_text(encoding="utf8"))
    control = json.loads(control_path.read_text(encoding="utf8"))
    for name, arm in ((CANDIDATE_ARM, candidate), (CONTROL_ARM, control)):
        if not arm.get("complete"):
            raise ValueError(f"{name} replay is not marked complete")
        if not arm.get("decisions") or not arm.get("nav"):
            raise ValueError(f"{name} replay is missing decisions or NAV")
    dates_candidate = [row["date"] for row in candidate["nav"]]
    dates_control = [row["date"] for row in control["nav"]]
    if dates_candidate != dates_control:
        raise ValueError("reference pair does not share one valuation calendar")
    return dict(
        root=str(root),
        candidate=candidate, control=control,
        dates=dates_candidate,
        nav_candidate=[float(row["nav"]) for row in candidate["nav"]],
        nav_control=[float(row["nav"]) for row in control["nav"]],
        hashes={str(p.relative_to(root)): sha256(p) for p in (candidate_path, control_path)},
        protocol_sha256=sha256(root / "protocol.json"),
    )


def targets_by_decision(arm: dict) -> dict[str, dict[str, Decimal]]:
    """Per-decision target weights by symbol."""
    out = {}
    for day, entry in arm["decisions"].items():
        out[day] = {t["symbol"]: Decimal(str(t["target_weight"])) for t in entry["targets"]}
    return out


def changed_decisions(candidate: dict, control: dict, tolerance: Decimal | None = None) -> list[dict]:
    """Decisions where the candidate's target weights differ from the control's.

    The published ``selection_diagnostics`` file carries only aggregate counts, so
    the enabled selections are derived by diffing the two arms directly.
    """
    tolerance = TOLERANCE["selection_tolerance"] if tolerance is None else tolerance
    left, right = targets_by_decision(candidate), targets_by_decision(control)
    shared = sorted(set(left) & set(right))
    if len(shared) != len(left) or len(shared) != len(right):
        raise ValueError("reference pair does not share one decision calendar")
    changes = []
    for day in shared:
        symbols = set(left[day]) | set(right[day])
        deltas = {s: left[day].get(s, Decimal(0)) - right[day].get(s, Decimal(0)) for s in symbols}
        moved = {s: d for s, d in deltas.items() if abs(d) > tolerance}
        if moved:
            changes.append(dict(decision=day, changed=sorted(moved),
                                added=sorted(s for s, d in moved.items() if d > 0),
                                removed=sorted(s for s, d in moved.items() if d < 0)))
    return changes


def _log_returns(nav: list[float]) -> np.ndarray:
    values = np.asarray(nav, dtype=float)
    if np.any(values <= 0):
        raise ValueError("NAV series must be strictly positive")
    return np.diff(np.log(values))


def total_return(nav: list[float]) -> float:
    return nav[-1] / nav[0] - 1.0


def yearly_excess(dates: list[str], nav_candidate: list[float], nav_control: list[float]) -> list[dict]:
    """Per calendar year return for both arms and their difference.

    A year counts as complete only when the window actually reaches its end. The
    partial final year is reported but excluded from the retention test, so a
    strong stub year cannot carry the verdict.
    """
    rows = []
    for year in sorted({d[:4] for d in dates}):
        index = [i for i, d in enumerate(dates) if d.startswith(year)]
        if len(index) < 2:
            continue
        first, last = index[0], index[-1]
        candidate = nav_candidate[last] / nav_candidate[first] - 1.0
        control = nav_control[last] / nav_control[first] - 1.0
        complete = dates[last] >= f"{year}-12-20"
        rows.append(dict(year=year, sessions=len(index), complete=bool(complete),
                         first_session=dates[first], last_session=dates[last],
                         candidate=candidate, control=control, excess=candidate - control))
    return rows


def monthly_excess(dates: list[str], nav_candidate: list[float], nav_control: list[float]) -> dict[str, float]:
    """Month-end difference in return, the input to the paired block bootstrap."""
    months: dict[str, list[int]] = {}
    for i, day in enumerate(dates):
        months.setdefault(day[:7], []).append(i)
    out = {}
    previous: tuple[float, float] | None = None
    for month in sorted(months):
        last = months[month][-1]
        current = (nav_candidate[last], nav_control[last])
        if previous is not None:
            out[month] = (current[0] / previous[0] - 1.0) - (current[1] / previous[1] - 1.0)
        previous = current
    return out


def bootstrap(dates: list[str], nav_candidate: list[float], nav_control: list[float]) -> list[dict]:
    """Paired circular block bootstrap over the monthly differences."""
    monthly = monthly_excess(dates, nav_candidate, nav_control)
    matrix = np.array([[v] for v in monthly.values()], dtype=float)
    rows = paired_bootstrap(matrix)
    row = rows[0] if rows else {}
    return [dict(block=block, n=row.get("n"), mean_annual=row.get("mean_annual"),
                 ci95=row.get("ci95"), p=row.get("p")) for block in (3, 6, 12)]


def _bootstrap_by_block(dates, nav_candidate, nav_control) -> dict[int, dict]:
    monthly = monthly_excess(dates, nav_candidate, nav_control)
    values = list(monthly.values())
    out = {}
    for block in (3, 6, 12):
        matrix = np.array([[v] for v in values], dtype=float)
        row = paired_bootstrap(matrix, block=block)[0]
        out[block] = dict(n=row["n"], mean_annual=row["mean_annual"], ci95=row["ci95"], p=row["p"])
    return out


def leave_one_out(dates: list[str], nav_candidate: list[float], nav_control: list[float],
                  changes: list[dict]) -> dict:
    """Tile FR25's difference from CP at the changed selections, and drop one tile at a time.

    The window is tiled so that each tile begins at a changed decision and runs to
    the next changed decision (the last running to the end of the window). Tiles
    are disjoint, so their log-return differences telescope exactly to the total.

    Why tiles rather than months: a changed selection alters share counts and
    cash, and that difference persists and compounds through later intervals even
    after the two arms realign their target weights. A single-month interval would
    capture only the direct effect and would attribute the carry-over to periods
    where the arms held identical targets. Tiling at the changed selections keeps
    each selection's full downstream footprint inside its own tile, which is what
    a leave-one-out robustness screen needs.
    """
    deltas = _log_returns(nav_candidate) - _log_returns(nav_control)
    total_log = float(deltas.sum())
    positions = {d: i for i, d in enumerate(dates)}
    starts = sorted({positions[c["decision"]] for c in changes if c["decision"] in positions})
    if not starts:
        return dict(total_log_difference=total_log,
                    total_return_difference=total_return(nav_candidate) - total_return(nav_control),
                    pre_change_log_difference=total_log, changed_tiles_log_difference=0.0, tiles=[])

    by_start = {positions[c["decision"]]: c for c in changes if c["decision"] in positions}
    tiles, accounted = [], 0.0
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(dates)
        change = by_start[start]
        # Sized at the decision close, filled at the next open: the first
        # attributable session is the one after the decision date.
        first_attributable = start + 1
        if end <= first_attributable:
            continue
        piece = float(deltas[first_attributable:end].sum())
        accounted += piece
        tiles.append(dict(decision=change["decision"], sessions=end - first_attributable,
                          through=dates[end] if end < len(dates) else dates[-1],
                          log_difference=piece,
                          added=change["added"], removed=change["removed"]))
    return dict(
        total_log_difference=total_log,
        total_return_difference=total_return(nav_candidate) - total_return(nav_control),
        pre_change_log_difference=total_log - accounted,
        changed_tiles_log_difference=accounted,
        contributions=sorted(tiles, key=lambda row: -abs(row["log_difference"])),
    )


def concentration(attribution: dict, years: list[dict]) -> dict:
    """How much of the edge comes from how few places."""
    tiles = [row["log_difference"] for row in attribution["contributions"]]
    shared = attribution["changed_tiles_log_difference"]
    year_excess = [row["excess"] for row in years if row["complete"]]
    best_year = max(years, key=lambda r: abs(r["excess"])) if years else None
    return dict(
        tiles=len(tiles),
        positive_tiles=sum(1 for t in tiles if t > 0),
        best_tile_share_of_changed=(max(tiles) / shared) if tiles and shared else None,
        top_three_share_of_changed=(sum(sorted(tiles, reverse=True)[:3]) / shared) if tiles and shared else None,
        changed_tiles_share_of_total=(shared / attribution["total_log_difference"])
            if attribution["total_log_difference"] else None,
        best_year=(best_year or {}).get("year"),
        best_year_complete=(best_year or {}).get("complete"),
        best_year_excess=(best_year or {}).get("excess"),
        best_year_share_of_total=(abs(best_year["excess"]) / abs(attribution["total_return_difference"]))
            if best_year and attribution["total_return_difference"] else None,
        positive_complete_years=sum(1 for e in year_excess if e > 0),
        complete_years=len(year_excess),
    )


def assess(attribution: dict, years: list[dict], bootstrap_by_block: dict[int, dict],
           placebo_percentile: float | None = None) -> dict:
    """Apply the frozen retention tolerance. Returns preserve / reject / inconclusive."""
    complete = [row for row in years if row["complete"]]
    positive_years = sum(1 for row in complete if row["excess"] > 0)
    share = (positive_years / len(complete)) if complete else None
    test_years = bool(complete) and share is not None and share >= TOLERANCE["positive_year_share"]
    leave_one_out_ok = all(
        (attribution["total_return_difference"] - row["log_difference"]) > 0
        for row in attribution["contributions"]
    ) and attribution["total_return_difference"] > 0
    block = TOLERANCE["block_for_lower_bound"]
    interval = bootstrap_by_block.get(block, {})
    lower = (interval.get("ci95") or [None])[0]
    interval_ok = lower is not None and lower > 0
    placebo_ok = None if placebo_percentile is None else (attribution["total_log_difference"] > placebo_percentile)

    passed = [test_years, leave_one_out_ok, interval_ok] + ([placebo_ok] if placebo_ok is not None else [])
    if all(passed) and placebo_ok is not None:
        status = "preserve"
    elif attribution["total_return_difference"] <= 0:
        status = "reject"
    elif not leave_one_out_ok:
        status = "reject"
    else:
        status = "inconclusive"
    return dict(
        status=status,
        positive_complete_years=positive_years, complete_years=len(complete), positive_year_share=share,
        years_test=test_years, leave_one_out_test=leave_one_out_ok, interval_test=interval_ok,
        placebo_test=placebo_ok,
        placebo_note=("Part B has not been run, so the placebo test is unavailable. Without it the item "
                      "can be reported as inconclusive at best, and never as preserved."
                      if placebo_ok is None else None),
        checks=dict(
            positive_year_share_required=TOLERANCE["positive_year_share"],
            block_for_lower_bound=block, interval_lower_bound=lower,
            total_return_difference=attribution["total_return_difference"],
            worst_single_selection=min((r["log_difference"] for r in attribution["contributions"]), default=None),
        ),
    )


def analyse(root: Path = STUDY_ROOT) -> dict:
    """Full Part A record, ready to publish or report."""
    data = load(root)
    changes = changed_decisions(data["candidate"], data["control"])
    years = yearly_excess(data["dates"], data["nav_candidate"], data["nav_control"])
    attribution = leave_one_out(data["dates"], data["nav_candidate"], data["nav_control"], changes)
    blocks = _bootstrap_by_block(data["dates"], data["nav_candidate"], data["nav_control"])
    verdict = assess(attribution, years, blocks)
    return dict(
        version="fr25-robustness-part-a-v1",
        part="A — analysis of published evidence; no portfolio was re-run",
        arm=CANDIDATE_ARM, control=CONTROL_ARM, cost_bps=COST_BPS, delay=DELAY,
        window=EVALUATION,
        first_session=data["dates"][0], last_session=data["dates"][-1],
        sessions=len(data["dates"]),
        decisions=len(data["candidate"]["decisions"]),
        changed_selection_count=len(changes),
        changed_selections=changes,
        input_hashes=data["hashes"], parent_protocol_sha256=data["protocol_sha256"],
        tolerance={k: (str(v) if isinstance(v, Decimal) else v) for k, v in TOLERANCE.items()},
        total_return=dict(candidate=total_return(data["nav_candidate"]),
                          control=total_return(data["nav_control"]),
                          difference=attribution["total_return_difference"]),
        yearly=years,
        bootstrap=blocks,
        attribution=attribution,
        concentration=concentration(attribution, years),
        verdict=verdict,
        part_b_outstanding=[
            "matched-availability placebo rank (needs a re-run)",
            "data-through-2022 refit (needs a re-run)",
            "top-N and financial-ridge-weight sensitivity (needs a re-run)",
        ],
        limitations=[
            "This is an attribution of the realised path, not a counterfactual re-run. Dropping a changed "
            "selection removes its interval's realised difference; it does not re-simulate what the "
            "portfolio would have held instead.",
            "**The attribution is path-dependent, and the direct interval difference understates a "
            "selection's effect.** A changed selection alters share counts and cash, and that difference "
            "persists and compounds through later intervals even after the two arms realign their target "
            "weights. So a small changed-interval total is evidence that the effect works through the "
            "position path, not evidence that the selections do not matter.",
            "Intervals between changed decisions are disjoint and their log-return differences telescope to "
            "the total, so the decomposition is exact in log terms and approximate when read as percentage "
            "points.",
            "The evaluation window was already inspected when FR25 was chosen, so nothing here is "
            "out-of-sample evidence.",
            "A year counts as complete only when the window reaches its end; the partial final year is "
            "reported but excluded from the retention test.",
            "Part B is not run, so no placebo comparison exists and the frozen tolerance cannot be fully "
            "satisfied. Absence of a placebo result is not evidence in FR25's favour.",
        ],
    )
