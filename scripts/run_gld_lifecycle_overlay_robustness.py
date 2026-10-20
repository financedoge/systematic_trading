"""Cost- and delay-charged robustness of the conditional 80/20 FR25 + Rule A short overlay.

The overlay is implemented as a single portfolio in the shared application accounting
engine: 80% of the target budget follows the frozen FR25 decision weights, 20% follows the
Rule A short-only daily sleeve. Every inter-sleeve and intra-sleeve trade is charged, and
execution delay is explicit. Two rebalancing clocks are compared:

fixed_monthly  : adopt the blended target only at FR25 month-end decisions (sleeve snapshot
                 frozen between month-ends) -- the fixed-interval control.
dynamic        : adopt at month-end anchors and whenever the latest theoretical blended
                 target differs from the last adopted target by an L1 threshold (0/5/10%).

Also compares conditional vs unconditional and randomly counterfactual conditions (same
number of true months), and reports multiple risk-adjusted measures against the frozen FR25
SOTA path at matching frictions.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
VAR = ROOT / "var" / "research" / "gld-lifecycle-overlay-robustness-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-overlay-robustness-20261019-v1"
COND_VAR = ROOT / "var" / "research" / "gld-lifecycle-conditioning-20261019-v1"
V2 = ROOT / "var" / "research" / "range-breakout-20261018-v2"
OOS_START = "2023-01-03"
FRICTIONS = ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1))
THRESHOLDS = (0.0, 0.05, 0.10)
RANDOM_SEEDS = (7, 11, 23)
SLEEVE_WEIGHT = 0.20

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(V2))
from run_gld_lifecycle_pool import load_panel, load_recipe  # noqa: E402
from run_gld_lifecycle_conditioning import (monthly_decision_indices,  # noqa: E402
                                            load_stable_signals)
import run_gld_lifecycle_daily_scanner as scanner  # noqa: E402


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def metrics(nav, exposure, turnover=None, fees=None):
    nav = np.asarray(nav, float)
    ret = nav[1:] / nav[:-1] - 1.0
    years = len(ret) / 252.0
    cagr = (nav[-1] / nav[0]) ** (1.0 / years) - 1.0
    sd = ret.std(ddof=1)
    sharpe = ret.mean() / sd * np.sqrt(252.0) if sd > 0 else 0.0
    downside = ret[ret < 0]
    sortino = (ret.mean() / downside.std(ddof=1) * np.sqrt(252.0)) if len(downside) > 1 else 0.0
    peak = np.maximum.accumulate(nav)
    dd = float((nav / peak - 1.0).min())
    out = dict(cagr=float(cagr), sharpe=float(sharpe), sortino=float(sortino), maxdd=dd,
               calmar=float(cagr / max(0.03, -dd)),
               volatility=float(sd * np.sqrt(252.0)),
               exposure=float(np.asarray(exposure).mean()), sessions=int(len(ret)))
    if turnover is not None:
        out["annual_turnover"] = float(np.mean(turnover) * 252.0)
    if fees is not None:
        out["annual_cost_bps"] = float(np.mean(np.asarray(fees) / nav) * 252.0 * 10000.0)
    return out


def build_inputs():
    panel = load_panel()
    order = [str(s) for s in panel["symbols"]]
    # Sleeve: exact Rule A short-only daily targets from the daily-scanner study.
    panel_s, order_s, signals = scanner.load_daily_signals()
    active, score = scanner.combined_events(signals, "short")
    sleeve_targets, sleeve_indices, _ = scanner.build_targets(
        panel_s, order_s, active, score, "equal_split")
    # Condition: stable union breadth from the conditioning study, threshold calibrated pre-2023.
    symbols, stable = load_stable_signals()
    stable = {k: np.column_stack([stable[k][symbols.index(s)] for s in order]) for k in stable}
    breadth = ((stable["short_active"] > 0) | (stable["long_active"] > 0)).sum(axis=1)
    days = pd.to_datetime(panel["days"]).to_numpy()
    pre = days <= np.datetime64("2022-12-30")
    threshold = float(np.median(breadth[pre]))
    monthly = monthly_decision_indices(panel)
    condition = {int(t): bool(breadth[t] >= threshold) for t in monthly}
    return panel, order, monthly, condition, threshold, sleeve_targets, sleeve_indices


def sleeve_state_series(n, sleeve_targets, sleeve_indices):
    """Last adopted sleeve target at each session (cash before the first entry)."""
    rows = np.zeros((n, sleeve_targets.shape[1]))
    cursor = 0
    current = np.zeros(sleeve_targets.shape[1])
    for t in range(n):
        while cursor < len(sleeve_indices) and sleeve_indices[cursor] <= t:
            current = sleeve_targets[sleeve_indices[cursor]]
            cursor += 1
        rows[t] = current
    return rows


def blend(fr25_row, sleeve_row):
    return 0.8 * fr25_row + SLEEVE_WEIGHT * sleeve_row


def build_scenarios(panel, order, monthly, condition, sleeve_targets, sleeve_indices,
                    random_condition):
    n = panel["close"].shape[0]
    n_cols = len(order) + 1
    fr25 = np.column_stack([panel["fr25"], np.zeros(n)])
    sleeve_state = sleeve_state_series(n, sleeve_targets, sleeve_indices)
    monthly_set = set(int(t) for t in monthly)
    start = int(monthly[0])
    scenarios = {}

    def fr25_target(day):
        return fr25[day]

    def sleeve_target(day):
        return sleeve_state[day]

    # Fixed monthly: adopt blended target only at month-end decisions.
    for label, cond in (("fixed_monthly_conditional", condition),
                        ("fixed_monthly_unconditional", None)):
        targets = np.zeros((n, n_cols))
        indices = []
        for t in monthly:
            target = fr25_target(t)
            if cond is None or cond[int(t)]:
                target = blend(target, sleeve_target(t))
            targets[t] = target
            indices.append(int(t))
        scenarios[label] = (targets, np.array(indices))

    # Dynamic: month-end anchors plus target-change adoption intra-month.
    for label, cond in (("dynamic_conditional", condition),
                        ("dynamic_unconditional", None)):
        for threshold in THRESHOLDS:
            targets = np.zeros((n, n_cols))
            indices = []
            adopted = np.zeros(n_cols)
            fr25_current = np.zeros(n_cols)
            for day in range(start, n):
                if day in monthly_set:
                    fr25_current = fr25_target(day)
                desired = fr25_current.copy()
                use_sleeve = cond is None or cond[int(monthly[np.searchsorted(
                    np.array(monthly), day, side="right") - 1])]
                if use_sleeve:
                    desired = blend(desired, sleeve_target(day))
                if day in monthly_set or np.abs(desired - adopted).sum() >= threshold - 1e-12:
                    targets[day] = desired
                    indices.append(day)
                    adopted = desired.copy()
            scenarios[f"{label}_t{threshold:.2f}"] = (targets, np.array(indices))
    # Random-condition counterfactuals: same number of true months, shuffled labels.
    month_truth = np.array([condition[int(t)] for t in monthly])
    for seed in RANDOM_SEEDS:
        rng = np.random.default_rng(seed)
        shuffled = month_truth.copy()
        rng.shuffle(shuffled)
        random_condition[seed] = {int(t): bool(v) for t, v in zip(monthly, shuffled)}
        cond = random_condition[seed]
        for label, threshold in ((f"dynamic_random_seed{seed}_t0.00", 0.0),):
            targets = np.zeros((n, n_cols))
            indices = []
            adopted = np.zeros(n_cols)
            fr25_current = np.zeros(n_cols)
            for day in range(start, n):
                if day in monthly_set:
                    fr25_current = fr25_target(day)
                desired = fr25_current.copy()
                month_pos = int(np.searchsorted(np.array(monthly), day, side="right") - 1)
                use_sleeve = bool(cond[int(monthly[month_pos])]) if month_pos >= 0 else False
                if use_sleeve:
                    desired = blend(desired, sleeve_target(day))
                if day in monthly_set or np.abs(desired - adopted).sum() >= threshold - 1e-12:
                    targets[day] = desired
                    indices.append(day)
                    adopted = desired.copy()
            scenarios[label] = (targets, np.array(indices))
    return scenarios


def main():
    VAR.mkdir(parents=True, exist_ok=True)
    (VAR / "results").mkdir(exist_ok=True)
    sys.path.insert(0, str(V2))
    from run_range_breakout import Replay  # noqa: E402
    panel, order, monthly, condition, threshold, sleeve_targets, sleeve_indices = build_inputs()
    recipe = load_recipe()
    replay = Replay(panel, recipe, OOS_START)
    random_condition = {}
    scenarios = build_scenarios(panel, order, monthly, condition, sleeve_targets,
                                sleeve_indices, random_condition)
    # Benchmarks.
    benchmark_paths = {"FR25 SOTA": "FR25_c5d0", "FR25 10bp": "FR25_c10d0",
                       "FR25 20bp": "FR25_c20d0", "FR25 +1 delay": "FR25_c5d1",
                       "Equal weight": "equal_weight_c5d0", "URTH": "URTH_c5d0"}
    benchmarks = {}
    for label, stem in benchmark_paths.items():
        d = np.load(V2 / "pool" / "paths" / f"{stem}.npz")
        benchmarks[label] = metrics(d["nav"], d["exposure"])
    # Integrity: replay frozen FR25 targets.
    fr25 = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    fr25_replay, _, _ = replay.run(fr25, monthly, 5.0, 0)
    frozen_fr25 = np.load(V2 / "pool" / "paths" / "FR25_c5d0.npz")["nav"]
    integrity = dict(fr25_max_relative_deviation=float(
        np.abs(fr25_replay["nav"] / frozen_fr25 - 1.0).max()))
    results, daily = {}, {}
    for label, (targets, indices) in scenarios.items():
        for cost, delay in FRICTIONS:
            compact, _, fills = replay.run(targets, indices, cost, delay)
            key = f"{label} | {cost:g}bp d{delay}"
            results[key] = dict(scenario=label, cost_bp=cost, delay=delay,
                                fills=int(fills), rebalances=int(len(indices)),
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            if cost == 5.0 and delay == 0:
                daily[label] = compact["nav"]
    # Multi-measure gate versus frozen FR25 (same friction: 5bp/d0 and matched 10/20/delay).
    base = benchmarks["FR25 SOTA"]
    gate_rows = []
    for label in scenarios:
        row = results.get(f"{label} | 5bp d0")
        if not row:
            continue
        m = row["metrics"]
        gate = dict(
            scenario=label,
            beats_sharpe=m["sharpe"] > base["sharpe"],
            beats_maxdd=m["maxdd"] > base["maxdd"],
            beats_calmar=m["calmar"] > base["calmar"],
            beats_return=m["cagr"] > base["cagr"],
            n_measures=int(sum([m["sharpe"] > base["sharpe"], m["maxdd"] > base["maxdd"],
                                m["calmar"] > base["calmar"]])),
        )
        gate_rows.append(gate)
    gate_rows.sort(key=lambda r: -r["n_measures"])
    # Candidate dossier for the conditional overlay (best conditional scenario only).
    def m_of(label, cost=5.0, delay=0):
        return results.get(f"{label} | {cost:g}bp d{delay}", {}).get("metrics")

    conditional_labels = [label for label in daily if "conditional" in label]
    ranked = []
    for label in conditional_labels:
        m = m_of(label)
        if not m:
            continue
        score = int(m["sharpe"] > base["sharpe"]) + int(m["maxdd"] > base["maxdd"]) + \
            int(m["calmar"] > base["calmar"])
        ranked.append((score, m["calmar"], m["sharpe"], label))
    ranked.sort(reverse=True)
    best_label = ranked[0][3] if ranked else None

    def gate_at(label, bench_label, cost, delay):
        m = m_of(label, cost, delay)
        b = benchmarks[bench_label]
        if not m:
            return None
        return dict(
            scenario=label, benchmark=bench_label, cost_bp=cost, delay=delay,
            sharpe=m["sharpe"] > b["sharpe"], maxdd=m["maxdd"] > b["maxdd"],
            calmar=m["calmar"] > b["calmar"], sortino=m["sortino"] > b["sortino"],
            cagr=m["cagr"] > b["cagr"],
            n_risk_measures=int(sum([m["sharpe"] > b["sharpe"], m["maxdd"] > b["maxdd"],
                                     m["calmar"] > b["calmar"],
                                     m["sortino"] > b["sortino"]])),
        )

    robustness = dict(
        base=gate_at(best_label, "FR25 SOTA", 5.0, 0),
        cost_10bp=gate_at(best_label, "FR25 10bp", 10.0, 0),
        cost_20bp=gate_at(best_label, "FR25 20bp", 20.0, 0),
        delay_1=gate_at(best_label, "FR25 +1 delay", 5.0, 1),
    )
    candidate = dict(
        status="research_candidate_for_monitoring_review",
        name="FR25 80/20 + Rule A short-only conditional overlay",
        authority=("Research only. Adding a monitored strategy requires an app-tracked "
                   "versioned strategy, paper-trading evidence, operator approval and a "
                   "capital/monitoring decision; none of that is done here."),
        scenario=best_label,
        threshold=threshold,
        condition_share=float(np.mean(list(condition.values()))),
        best_5bp=results.get(f"{best_label} | 5bp d0", {}).get("metrics"),
        gate=next((r for r in gate_rows if r["scenario"] == best_label), None),
        robustness_versus_matched_fr25=robustness,
        prerequisites=[
            "Explicit cost-charged overlay with delay sensitivity (this study).",
            "Out-of-sample/matched-control edge larger than random timing controls.",
            "Paper-trading evidence through the app's tracked-strategy pipeline.",
            "Versioned specification + operator approval + rollback plan.",
        ],
    )
    evidence = dict(
        identity="gld-lifecycle-overlay-robustness-20261019-v1",
        protocol=dict(
            authority="Research only; no monitoring, promotion, funding or broker action.",
            construction=("80% of the target budget follows frozen FR25 monthly weights; "
                          f"{SLEEVE_WEIGHT:.0%} follows the Rule A short-only daily sleeve. "
                          "Blended targets are executed through the shared application "
                          "accounting engine, so every rebalance and inter-sleeve flow is "
                          "charged; delay is explicit."),
            condition=("Sleeve is enabled only in months whose stable union-signal breadth "
                       "is at or above the pre-2023 median; condition known at the decision "
                       "close."),
            clocks=["fixed_monthly (month-end only)", "dynamic target-change triggers 0/5/10% L1"],
            controls=["unconditional sleeve", "random-condition counterfactuals (same count)"],
            frictions=[dict(cost_bp=c, delay=d) for c, d in FRICTIONS],
            no_oos_tuning="Thresholds, weights, clocks, controls and frictions are predeclared.",
        ),
        threshold=threshold,
        condition_share=float(np.mean(list(condition.values()))),
        benchmarks=benchmarks,
        results=results,
        gate=gate_rows,
        best_conditional=best_label,
        candidate=candidate,
        integrity=integrity,
    )
    write_json(VAR / "evidence.json", evidence)
    pd.DataFrame([dict(scenario=k, **v["metrics"], fills=v["fills"],
                       rebalances=v["rebalances"], cost_bp=v["cost_bp"], delay=v["delay"])
                  for k, v in results.items()]).to_csv(
        VAR / "scenarios.csv", index=False)
    daily_frame = {"date": [str(d)[:10] for d in panel["days"][-len(frozen_fr25):]]}
    for label, nav in daily.items():
        daily_frame[label] = nav
    for label in ("FR25 SOTA", "FR25 10bp", "FR25 20bp", "FR25 +1 delay", "Equal weight"):
        daily_frame[label] = np.load(V2 / "pool" / "paths" / f"{benchmark_paths[label]}.npz")["nav"]
    pd.DataFrame(daily_frame).to_csv(VAR / "daily-nav.csv", index=False, float_format="%.4f")
    write_json(VAR / "candidate.json", candidate)
    summary = dict(
        threshold=threshold,
        condition_share=float(np.mean(list(condition.values()))),
        best_conditional=best_label,
        best_5bp=results.get(f"{best_label} | 5bp d0", {}).get("metrics"),
        fr25=base,
        gate=[{k: v for k, v in row.items() if k != "scenario"} | {"scenario": row["scenario"]}
              for row in gate_rows],
        integrity=integrity,
    )
    print(json.dumps(summary, indent=1, default=_jsonable))


if __name__ == "__main__":
    main()
