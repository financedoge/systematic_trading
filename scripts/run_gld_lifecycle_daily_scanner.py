"""Daily opportunity-scanner / CTA-style portfolios from the two lifecycle signals.

Two predeclared daily rules on the 52-ETF pool, using the sealed per-ETF
short-range/long-range signals fitted on pre-2023 sessions only:

Rule A (equal re-split): existing holdings stay until their lifecycle signal exits.
When a new ETF entry signal fires, all current holdings are rebalanced to equal
weights (capacity 6); exits drop the name and the rest are re-equalised. Empty
book -> 100% cash/government proxy.

Rule B (1/6 slot CTA): up to six concurrent holdings, each new entry takes one
1/6 slot and the remaining 1/6 slots stay in the cash/government proxy. Exits
return that slot to the proxy; other holdings keep their 1/6.

Signals are daily close-time events (union of short and long sleeves), fills are
next-open, costs per side, no shorting or leverage. Research only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
VAR = ROOT / "var" / "research" / "gld-lifecycle-daily-scanner-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-daily-scanner-20261019-v1"
POOL_VAR = ROOT / "var" / "research" / "gld-lifecycle-pool-20261019-v1"
V2 = ROOT / "var" / "research" / "range-breakout-20261018-v2"
OOS_START = "2023-01-03"
FRICTIONS = ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1))
CASH_SYMBOLS = {"BIL": "T-bill 1-3m (base)", "SHY": "1-3y Treasury", "IEF": "7-10y Treasury"}
SLOT_OPTIONS = (4, 6, 8)

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(V2))
from run_gld_lifecycle_pool import load_panel, load_recipe, load_signals, panel_days  # noqa: E402


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False, default=_jsonable),
                          encoding="utf-8")


def _jsonable(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_daily_signals():
    panel = load_panel()
    symbols, signals_by = load_signals()
    order = [str(s) for s in panel["symbols"]]
    signals = {}
    for key, value in signals_by.items():
        signals[key] = np.column_stack([value[symbols.index(s)] for s in order])
    return panel, order, signals


def combined_events(signals, source):
    if source == "union":
        active = (signals["short_active"] > 0) | (signals["long_active"] > 0)
    elif source == "short":
        active = signals["short_active"] > 0
    elif source == "long":
        active = signals["long_active"] > 0
    else:
        raise ValueError(source)
    score = np.where(signals["short_active"] > 0, signals["short_score"], 0.0) + \
            np.where(signals["long_active"] > 0, signals["long_score"], 0.0)
    return active, score


def build_targets(panel, order, active, score, rule, cash_symbol="BIL", slots=6):
    """Daily event-driven target weights for the equal-split or 1/6-slot CTA rule."""
    n = panel["close"].shape[0]
    n_assets = len(order)
    start_decision = int(np.flatnonzero(np.array([str(np.datetime64(d, "D")) for d in panel["days"]])
                                       <= "2022-12-30")[-1])
    cash_index = order.index(cash_symbol)
    budget = 0.98
    targets = np.zeros((n, n_assets + 1))
    indices = []
    holdings: list[int] = []

    def rank_candidates(day, candidates):
        return sorted(candidates, key=lambda j: (-(score[day, j]), order[j]))

    def assign(day):
        row = np.zeros(n_assets + 1)
        if rule == "equal_split":
            if holdings:
                weight = budget / len(holdings)
                for j in holdings:
                    row[j] = weight
            else:
                row[cash_index] = budget
        elif rule == "slots":
            slot = budget / slots
            for j in holdings:
                row[j] = slot
            row[cash_index] = max(0.0, budget - slot * len(holdings))
        else:
            raise ValueError(rule)
        targets[day, :-1] = row[:-1]
        return row

    def accept(day, candidates):
        capacity = slots if rule == "slots" else slots
        room = capacity - len(holdings)
        if room <= 0:
            return False
        for j in rank_candidates(day, candidates):
            if len(holdings) < capacity and j not in holdings:
                holdings.append(j)
        return True

    # The OOS account starts flat at the beginning of the window. Names already
    # active on 2022-12-30 have no fresh entry signal inside the window and are
    # therefore not back-filled; the first OOS entries populate the book.
    holdings.clear()
    row = assign(start_decision)
    indices.append(start_decision)
    adopted = row.copy()
    holdings_count = np.zeros(n, dtype=int)
    invested = np.zeros(n)
    holdings_count[start_decision] = len(holdings)
    invested[start_decision] = row[:n_assets].sum()
    entry_events = 0
    exit_events = 0
    for day in range(start_decision + 1, n):
        changed = False
        exited = [j for j in holdings if not active[day, j]]
        if exited:
            for j in exited:
                holdings.remove(j)
            exit_events += len(exited)
            changed = True
        new = [j for j in np.flatnonzero(active[day]) if j != cash_index
               and active[day - 1, j] == 0 and j not in holdings]
        if new:
            before = len(holdings)
            accept(day, new)
            entry_events += len(holdings) - before
            changed = changed or len(holdings) != before
        row = assign(day)
        holdings_count[day] = len(holdings)
        invested[day] = row[:n_assets].sum()
        if np.abs(row - adopted).sum() > 1e-12:
            indices.append(day)
            adopted = row.copy()
    behavior = dict(holdings_count=holdings_count, invested=invested,
                    entry_events=int(entry_events), exit_events=int(exit_events),
                    average_holdings=float(holdings_count[start_decision:].mean()),
                    share_flat=float((holdings_count[start_decision:] == 0).mean()),
                    share_full=float((holdings_count[start_decision:] >= (slots if rule == "slots" else 6)).mean()),
                    average_invested=float(invested[start_decision:].mean()))
    return targets, np.array(indices, dtype=int), behavior


def metrics(nav, exposure, turnover=None, fees=None):
    nav = np.asarray(nav, float)
    ret = nav[1:] / nav[:-1] - 1.0
    years = len(ret) / 252.0
    cagr = (nav[-1] / nav[0]) ** (1.0 / years) - 1.0
    sd = ret.std(ddof=1)
    sharpe = ret.mean() / sd * np.sqrt(252.0) if sd > 0 else 0.0
    peak = np.maximum.accumulate(nav)
    dd = float((nav / peak - 1.0).min())
    out = dict(cagr=float(cagr), sharpe=float(sharpe), maxdd=dd,
               calmar=float(cagr / max(0.03, -dd)),
               volatility=float(sd * np.sqrt(252.0)),
               exposure=float(np.asarray(exposure).mean()), sessions=int(len(ret)))
    if turnover is not None:
        out["annual_turnover"] = float(np.mean(turnover) * 252.0)
    if fees is not None:
        out["annual_cost_bps"] = float(np.mean(np.asarray(fees) / nav) * 252.0 * 10000.0)
    return out


def holdings_timeline(panel, order, active, targets, indices, cash_symbol="BIL"):
    rows = []
    cash_index = order.index(cash_symbol)
    for t in indices:
        held = [order[j] for j in np.flatnonzero(targets[t, :-1] > 0)]
        rows.append(dict(date=str(np.datetime64(panel["days"][t], "D")),
                         holdings=len(held), names=";".join(held),
                         invested=float(1.0 - targets[t, cash_index])))
    return rows


def main():
    VAR.mkdir(parents=True, exist_ok=True)
    (VAR / "results").mkdir(exist_ok=True)
    sys.path.insert(0, str(V2))
    from run_range_breakout import Replay  # noqa: E402
    panel = load_panel()
    recipe = load_recipe()
    order, signals = None, None
    panel_, order, signals = load_daily_signals()
    replay = Replay(panel_, recipe, OOS_START)
    days = panel_days(panel_)
    # Frozen benchmark paths.
    benchmark_paths = {"FR25 SOTA": "FR25_c5d0", "Equal-weight pool": "equal_weight_c5d0",
                       "URTH": "URTH_c5d0", "BIL": "BIL_c5d0",
                       "FR25 (10bp)": "FR25_c10d0", "FR25 (20bp)": "FR25_c20d0",
                       "FR25 (+1 delay)": "FR25_c5d1"}
    benchmarks = {}
    for label, stem in benchmark_paths.items():
        data = np.load(V2 / "pool" / "paths" / f"{stem}.npz")
        benchmarks[label] = dict(nav=data["nav"], exposure=data["exposure"],
                                 metrics=metrics(data["nav"], data["exposure"]))
    benchmarks["BIL"]["metrics"]["annual_turnover"] = 0.0
    benchmarks["BIL"]["metrics"]["annual_cost_bps"] = 0.0
    event_cache = {}
    results, daily, holdings_rows = {}, {}, {}
    base_runs = []
    for source in ("union", "short", "long"):
        event_cache[source] = combined_events(signals, source)
        for rule in ("equal_split", "slots"):
            active, score = event_cache[source]
            targets, indices, behavior = build_targets(panel_, order, active, score, rule)
            base_runs.append((f"{rule}|{source}", rule, source, targets, indices, behavior))
    for label, rule, source, targets, indices, behavior in base_runs:
        for cost, delay in FRICTIONS:
            compact, _, fills = replay.run(targets, indices, cost, delay)
            key = f"{label} | {cost:g}bp d{delay}"
            results[key] = dict(rule=rule, source=source, cost_bp=cost, delay=delay,
                                fills=int(fills), rebalances=int(len(indices)),
                                behavior=behavior,
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            if cost == 5.0 and delay == 0:
                daily[label] = compact["nav"]
                holdings_rows[label] = holdings_timeline(panel_, order, None, targets, indices)
    # Slot and cap sensitivity (union signals).
    active, score = event_cache["union"]
    for slots in (4, 8):
        for rule in ("equal_split", "slots"):
            targets, indices, behavior = build_targets(panel_, order, active, score, rule,
                                                       slots=slots)
            compact, _, fills = replay.run(targets, indices, 5.0, 0)
            key = f"{rule}|union slots{slots} | 5bp d0"
            results[key] = dict(rule=rule, source="union", cost_bp=5.0, delay=0,
                                slots=slots, fills=int(fills), rebalances=int(len(indices)),
                                behavior=behavior,
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            if rule == "equal_split":
                daily[f"{rule}|union slots{slots}"] = compact["nav"]
    # Cash-proxy sensitivity for the two base union rules.
    for cash_symbol in ("SHY", "IEF"):
        for rule in ("equal_split", "slots"):
            targets, indices, behavior = build_targets(panel_, order, active, score, rule,
                                                       cash_symbol=cash_symbol)
            compact, _, fills = replay.run(targets, indices, 5.0, 0)
            key = f"{rule}|union cash{cash_symbol} | 5bp d0"
            results[key] = dict(rule=rule, source="union", cost_bp=5.0, delay=0,
                                cash=cash_symbol, fills=int(fills),
                                rebalances=int(len(indices)), behavior=behavior,
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            daily[key] = compact["nav"]
    # Annual returns from the daily NAV series.
    annual = {}
    for label, nav in daily.items():
        annual[label] = {}
        for year in (2023, 2024, 2025, 2026):
            mask = (days[-len(nav):] >= np.datetime64(f"{year}-01-01")) & (
                days[-len(nav):] <= np.datetime64(f"{year}-12-31"))
            idx = np.flatnonzero(mask)
            if len(idx) < 20:
                annual[label][str(year)] = None
                continue
            s, e = int(idx[0]), int(idx[-1]) + 1
            annual[label][str(year)] = float(nav[e - 1] / nav[s] - 1.0)
    # Correlations with FR25 and URTH.
    rule_returns = {}
    for label, nav in daily.items():
        rule_returns[label] = np.diff(nav) / nav[:-1]
    correlations = {}
    for label, returns in rule_returns.items():
        row = {}
        for bench in ("FR25 SOTA", "URTH", "BIL"):
            bench_returns = np.diff(benchmarks[bench]["nav"]) / benchmarks[bench]["nav"][:-1]
            row[bench] = float(np.corrcoef(returns, bench_returns)[0, 1])
        correlations[label] = row
    # Base integrity check on the FR25 replay.
    fr25_targets = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    monthly = []
    previous_month = "2022-12"
    days_str = [str(np.datetime64(d, "D")) for d in panel["days"]]
    initial = int(np.flatnonzero(np.array(days_str) <= "2022-12-30")[-1])
    monthly.append(initial)
    for t in range(initial + 1, len(days_str)):
        if days_str[t][:7] != previous_month:
            monthly.append(t - 1)
            previous_month = days_str[t][:7]
    fr25_replay, _, _ = replay.run(fr25_targets, np.array(monthly), 5.0, 0)
    fr25_frozen = benchmarks["FR25 SOTA"]["nav"]
    integrity = dict(fr25_max_relative_deviation=float(
        np.abs(fr25_replay["nav"] / fr25_frozen - 1.0).max()))
    protocol = dict(
        identity="gld-lifecycle-daily-scanner-20261019-v1",
        authority="Research only; no monitoring, promotion, funding or broker action.",
        question=("Do daily, event-driven equal-split and 1/6-slot CTA-style portfolios built "
                  "from the sealed two-horizon ETF lifecycle signals deliver a useful "
                  "long-only daily strategy?"),
        design=dict(
            signals=("Per-ETF short-range and long-range lifecycle parameters sealed on "
                     "pre-2023 sessions in the 52-ETF pool study; union of both sleeves as the "
                     "default entry signal, with short-only and long-only attribution."),
            rule_equal_split=("Existing holdings persist until their lifecycle signal exits. A new "
                              "entry triggers an equal-weight re-split of all holdings (capacity 6); "
                              "an exit drops the name and the remainder is re-equalised. Empty "
                              "book = 100% cash proxy."),
            rule_slots=("At most six concurrent holdings; each new entry takes one 1/6 slot and "
                        "the unused slots stay in the cash proxy. An exit returns its slot to the "
                        "proxy; other holdings keep their 1/6."),
            cash_proxy=("BIL (1-3 month T-bill) is the base cash/government proxy; SHY (1-3y) and "
                        "IEF (7-10y) are reported as sensitivity. GOVY itself is not in the "
                        "audited pool."),
            timing="Daily close signals; next-open fills; costs per traded side.",
            capacities=[4, 6, 8],
            frictions=[dict(cost_bp=c, delay=d) for c, d in FRICTIONS],
            no_oos_tuning="Rules, capacities, cash proxy and frictions are predeclared; 2023+ "
                          "outcomes are not used to choose them.",
        ),
        chronology=dict(fit_end="2022-12-30", oos_start=OOS_START,
                        oos_end=str(np.datetime64(panel["days"][-1], "D")),
                        oos_sessions=int(len(panel["days"]) - initial - 1)),
        limitations=[
            "Signals come from the deliberately shallow per-ETF pool fits; a deeper per-ETF "
            "fit or the GLD-transfer vector would change the entry stream.",
            "The 2023-2026 interval has been inspected in prior research; results are "
            "development retests.",
            "Long-only, no shorting, no leverage; cash proxy earns its own ETF return; BIL/SHY/"
            "IEF results are not cash-yield-adjusted.",
            "FR25 is shown as a reference benchmark, not as the target of this daily CTA design.",
        ],
    )
    evidence = dict(identity=protocol["identity"], protocol=protocol,
                    results=results, benchmarks={k: v["metrics"] for k, v in benchmarks.items()},
                    annual_returns=annual, correlations=correlations,
                    integrity=integrity,
                    holdings={k: v for k, v in holdings_rows.items()})
    write_json(VAR / "evidence.json", evidence)
    nav_frame = {"date": [str(np.datetime64(d, "D")) for d in panel["days"][initial + 1:]]}
    for label, nav in daily.items():
        nav_frame[label] = nav
    for label in ("FR25 SOTA", "Equal-weight pool", "URTH", "BIL"):
        nav_frame[label] = benchmarks[label]["nav"]
    pd.DataFrame(nav_frame).to_csv(VAR / "daily-nav.csv", index=False, float_format="%.4f")
    with open(VAR / "holdings.json", "w", encoding="utf-8") as handle:
        json.dump(holdings_rows, handle, indent=1)
    print(json.dumps({k: {**{m: round(v, 4) for m, v in r["metrics"].items()},
                          "entries": r["behavior"]["entry_events"],
                          "exits": r["behavior"]["exit_events"],
                          "average_holdings": round(r["behavior"]["average_holdings"], 2)}
                      for k, r in results.items() if r["cost_bp"] == 5 and r["delay"] == 0},
                     indent=1))
    print(json.dumps({k: {m: round(v, 3) for m, v in val["metrics"].items()}
                      for k, val in benchmarks.items()}, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all", choices=["all"])
    args = parser.parse_args()
    main()
