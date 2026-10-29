"""Bounded, predeclared correction retest; no broker or publication writes."""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trading.research import fr25_lifecycle_conditional as strategy  # noqa: E402

OUTPUT = ROOT / "research/fr25-lifecycle-review-20261020-v1"
WORK = ROOT / "var/research/fr25-lifecycle-review-20261020-v1"
FRICTIONS = [(c, d) for c in (5, 10, 20) for d in (0, 1)]
SEEDS = (7, 11, 23)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def protocol():
    return dict(
        identity=OUTPUT.name, implementation=strategy.VERSION,
        code_hashes={name: digest(ROOT / name) for name in (
            "scripts/retest_fr25_lifecycle_review.py",
            "src/systematic_trading/research/fr25_lifecycle_conditional.py",
            "src/systematic_trading/research/range_lifecycle.py",
            "src/systematic_trading/backtest/engine.py",
            "src/systematic_trading/backtest/accounting.py",
            "src/systematic_trading/portfolio/proposals.py")},
        question="Does the corrected, fixed conditional overlay improve matched FR25 risk-adjusted outcomes after costs and delay?",
        primary="conditional_dynamic_0.10", no_selection="Do not choose a new winner from this retest.",
        period="2023-01-03 to 2026-10-12; initial cash anchor 2022-12-30",
        data=strategy.verified_input_provenance(),
        universe="All 52 supported ETFs in the pinned panel; URTH is a benchmark only.",
        construction="Preserve FR25 cash. ON: 0.8*FR25 + 0.2*Rule A. OFF: FR25. Final 45% name cap; excess cash.",
        rule_a="Start flat. Short lifecycle-state 0->1 entries ranked by frozen short+long extension scores; alphabetical tie-break; six slots; BIL when empty.",
        signal_clock="Use observed lifecycle held state at close, as in the original study. This already lags each underlying lifecycle confirmation; do not reinterpret it as a same-close entry signal.",
        condition="Frozen stable union breadth >= pre-2023 median 36/52, updated at month-end.",
        timing="Month-end anchors plus L1(theoretical, last adopted) including cash >= 10%. Monthly control; 0/5% sensitivities without selection.",
        execution="Freeze target and decision-close reference prices; rebalance then-held quantities at next open or +1 extra session. Daily open is a proxy; no queued-order, partial-fill or historical TWAP simulation.",
        controls=["FR25", "URTH", "equal_weight_52", "conditional_monthly",
                  "unconditional_dynamic_0.10", "unconditional_monthly", "random_condition_7/11/23_at_0.10"],
        frictions=[dict(cost_bp=c, extra_sessions=d) for c, d in FRICTIONS],
        random_controls="Shuffle monthly condition labels with fixed seeds, preserving count; same clock/threshold/friction as primary. Placebo diagnostics, not deployable future knowledge.",
        metrics="Include initial fill and cost. CAGR, net Sharpe, Sortino using root mean square negative returns over ALL sessions, max drawdown, unregularized Calmar; actual filled turnover/cost.",
        gate="Primary must beat matched FR25 Sharpe/Sortino/Calmar with drawdown no worse and CAGR loss <=1 percentage point at ALL six frictions. Report yearly comparisons; no tuning or significance claim.",
        chronology="Pre-2023 parameters unchanged. 2023, 2024, 2025, 2026-to-cutoff are inspected development diagnostics, not untouched validation.",
        authority="Research only; no promotion, monitoring membership, allocation, policy or broker changes.",
        limitations=["Frozen FR25 and breadth cannot extend beyond the panel. Full app monitoring extension remains open.",
                     "Audited prices do not establish historical availability; current cohort is not survivorship-free.",
                     "USD adjusted units; no CNH or raw-share execution certification.",
                     "Daily data cannot establish the production TWAP execution-clock edge."],
    )


def prepare():
    value = protocol()
    path = OUTPUT / "protocol.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != value:
        raise ValueError("Protocol changed; use a new study identity")
    write(path, value)
    print("Protocol frozen:", digest(path), flush=True)


def metrics(nav, dates, fills):
    nav = np.asarray(nav, float)
    ret = nav[1:] / nav[:-1] - 1
    years = len(ret) / 252
    cagr = float((nav[-1] / nav[0]) ** (1 / years) - 1)
    volatility = float(ret.std(ddof=1) * np.sqrt(252))
    downside = float(np.sqrt(np.mean(np.minimum(ret, 0) ** 2)) * np.sqrt(252))
    dd = float(np.min(nav / np.maximum.accumulate(nav) - 1))
    preceding = dict(zip(dates[1:], nav[:-1], strict=True))
    traded = sum(abs(f["quantity"]) * float(f["price"]) / preceding[f["date"]]
                 for f in fills if f["date"] in preceding)
    fees = sum(float(f["fee"]) / preceding[f["date"]] for f in fills if f["date"] in preceding)
    return dict(cagr=cagr, sharpe=float(ret.mean() * 252 / volatility) if volatility else 0.,
                sortino=float(ret.mean() * 252 / downside) if downside else None,
                max_drawdown=dd, calmar=cagr / abs(dd) if dd else None,
                annual_turnover=traded / years, annual_cost_bps=fees / years * 10000,
                sessions=len(ret), final_nav=float(nav[-1]))


def scenarios(panel, active, scores):
    n = len(panel["days"])
    monthly = strategy._monthly_indices(panel)
    fr25 = np.column_stack([panel["fr25"], np.zeros(n)])
    result = {"FR25": (fr25, monthly)}
    for trigger in (0., .05, .10):
        weights, indices, _ = strategy.build_targets(panel, active, scores, trigger=trigger)
        result[f"conditional_dynamic_{trigger:.2f}"] = weights, indices
    weights, indices, condition = strategy.build_targets(panel, active, scores, clock="monthly")
    result["conditional_monthly"] = weights, indices
    always = {int(t): True for t in monthly}
    for clock in ("dynamic", "monthly"):
        weights, indices, _ = strategy.build_targets(panel, active, scores, clock=clock, condition_override=always)
        result["unconditional_" + ("dynamic_0.10" if clock == "dynamic" else clock)] = weights, indices
    truth = np.array([condition[int(t)] for t in monthly])
    for seed in SEEDS:
        shuffled = truth.copy()
        np.random.default_rng(seed).shuffle(shuffled)
        override = dict(zip(map(int, monthly), map(bool, shuffled), strict=True))
        weights, indices, _ = strategy.build_targets(panel, active, scores, condition_override=override)
        result[f"random_condition_{seed}"] = weights, indices
    equal = np.zeros_like(fr25)
    equal[monthly, :-1] = .98 / len(panel["symbols"])
    result["equal_weight_52"] = equal, monthly
    urth = np.zeros_like(fr25)
    urth[monthly[0], -1] = .98
    result["URTH"] = urth, monthly[:1]
    return result


def gate(candidate, baseline):
    comparisons = dict(sharpe=candidate["sharpe"] > baseline["sharpe"],
                       sortino=candidate["sortino"] > baseline["sortino"],
                       calmar=candidate["calmar"] > baseline["calmar"],
                       drawdown=candidate["max_drawdown"] >= baseline["max_drawdown"],
                       return_guard=candidate["cagr"] >= baseline["cagr"] - .01)
    return dict(comparisons, passed=all(comparisons.values()))


def run():
    prepared = json.loads((OUTPUT / "protocol.json").read_text(encoding="utf-8"))
    if prepared != protocol():
        raise ValueError("Protocol or inputs changed")
    if (OUTPUT / "results.json").exists():
        raise ValueError("Results already exist; preserve this completed study")
    panel = strategy._load_panel()
    active, scores = strategy._sleeve_signals(panel, strategy.frozen_parameters())
    recipe = json.loads(strategy.RECIPE_PATH.read_text(encoding="utf-8"))
    replay = strategy._Replay(panel, recipe, strategy.OOS_START)
    dates = [str(panel["days"][replay.indices[0] - 1]), *map(str, replay.days)]
    mappings = scenarios(panel, active, scores)
    rows, paths, primary_payload = [], {}, None
    for name, (weights, indices) in mappings.items():
        for cost, delay in FRICTIONS:
            result, fills = replay.run_result(weights, indices, cost, delay)
            payload = strategy.report_payload(replay, result, fills)
            nav = np.array([float(r["nav_cnh"]) for r in payload["nav_series"]])
            row = dict(scenario=name, cost_bp=cost, delay=delay,
                       **metrics(nav, dates, fills), rebalances=len(result.proposals), fills=len(fills),
                       max_target_weight=float(weights.max()))
            row["yearly"] = {}
            for year in ("2023", "2024", "2025", "2026"):
                selected = [i for i, day in enumerate(dates) if day.startswith(year) and i > 0]
                lo, hi = selected[0] - 1, selected[-1] + 1
                row["yearly"][year] = metrics(nav[lo:hi], dates[lo:hi], fills)
            rows.append(row)
            key = f"{name}_c{cost}d{delay}"
            paths[key] = nav
            if name == prepared["primary"] and cost == 5 and delay == 0:
                _, _, _, theoretical = strategy.build_targets(panel, active, scores, return_theoretical=True)
                primary_payload = dict(payload, latest_targets=[
                    dict(symbol=s, target_weight=str(float(w)))
                    for s, w in zip(replay.symbols, theoretical[-1], strict=True) if w > 0],
                    input_provenance=prepared["data"], accounting_currency="USD")
                write(WORK / "primary-calculation.json", primary_payload)
            print(f"{key}: CAGR {row['cagr']:.4%}, Sharpe {row['sharpe']:.4f}", flush=True)
    gates = []
    for cost, delay in FRICTIONS:
        base = next(r for r in rows if r["scenario"] == "FR25" and r["cost_bp"] == cost and r["delay"] == delay)
        primary = next(r for r in rows if r["scenario"] == prepared["primary"] and r["cost_bp"] == cost and r["delay"] == delay)
        gates.append(dict(cost_bp=cost, delay=delay, **gate(primary, base)))
    evidence = dict(protocol_sha256=digest(OUTPUT / "protocol.json"), results=rows, gates=gates,
                    decision="research_gate_pass" if all(g["passed"] for g in gates) else "do_not_promote",
                    current_signal_extension="not_implemented", accounting_currency="USD")
    if prepared != protocol():
        raise ValueError("Inputs changed during study")
    write(OUTPUT / "results.json", evidence)
    with (OUTPUT / "scenarios.csv").open("w", newline="", encoding="utf-8") as stream:
        keys = [k for k in rows[0] if k != "yearly"]
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: r[k] for k in keys} for r in rows)
    WORK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(WORK / "nav.npz", dates=dates, **paths)
    np.savez_compressed(WORK / "mappings.npz",
                        **{k + "_weights": v[0] for k, v in mappings.items()},
                        **{k + "_indices": v[1] for k, v in mappings.items()})
    write(OUTPUT / "manifest.json", {p.name: digest(p) for p in OUTPUT.iterdir() if p.is_file()})
    print("Decision:", evidence["decision"], flush=True)


def native_checks():
    from systematic_trading.config import AppSettings
    from systematic_trading.research.momentum_replay import freeze_usd_bundle, native_parity
    if AppSettings().lean_runtime_backend != "native":
        raise ValueError("This study requires the accepted native Windows LEAN runtime")
    expected = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    if expected["protocol_sha256"] != digest(OUTPUT / "protocol.json") or protocol() != json.loads((OUTPUT / "protocol.json").read_text()):
        raise ValueError("Study inputs changed")
    contract = WORK / "native-contract"
    if not contract.exists():
        shutil.copytree(ROOT / "src/systematic_trading", contract / "source/systematic_trading",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        write(contract / "protocol.json", dict(initial_cash_usd="1000000",
              limitations=protocol()["limitations"]))
        write(contract / "input_manifest.json", dict(study_protocol=digest(OUTPUT / "protocol.json")))
    panel = strategy._load_panel()
    recipe = json.loads(strategy.RECIPE_PATH.read_text(encoding="utf-8"))
    replay = strategy._Replay(panel, recipe, strategy.OOS_START)
    mappings = np.load(WORK / "mappings.npz", allow_pickle=False)
    paths = np.load(WORK / "nav.npz", allow_pickle=False)
    receipts = []
    image = json.loads((ROOT / "config/strategy-monitoring.json").read_text())["calculation"]["image"]
    for name, delay in (("FR25", 0), ("conditional_monthly", 0),
                        ("conditional_dynamic_0.10", 0), ("conditional_dynamic_0.10", 1)):
        key = f"{name}_c5d{delay}"
        indices, weights = mappings[name + "_indices"], mappings[name + "_weights"]
        schedule = replay.decisions(weights, indices, delay)
        decision_indices = {str(panel["days"][t + 1 + delay]): int(t)
                            for t in indices if t + 1 + delay < len(panel["days"])}
        decisions = {str(day): dict(signal_session=str(panel["days"][decision_indices[str(day)]]),
                                   known_through=str(panel["days"][decision_indices[str(day)]]),
                                   targets=[t.model_dump(mode="json") for t in targets])
                     for day, targets in schedule.items()}
        quotes = {}
        from systematic_trading.backtest.accounting import quantize_money
        from decimal import Decimal
        close = np.column_stack([panel["close"], panel["urth_close"]])
        for j, symbol in enumerate(replay.symbols):
            quotes[symbol] = {}
            for day in replay.days:
                t = decision_indices.get(str(day))
                reference = quantize_money(Decimal(str(close[t, j]))) if t is not None else replay.reference[day][symbol]
                quotes[symbol][str(day)] = dict(open=str(replay.open[day][symbol]),
                                                close=str(replay.close[day][symbol]), reference=str(reference))
        bundle, output = WORK / "native-bundles" / key, WORK / "native" / key
        freeze_usd_bundle(bundle, contract, recipe, decisions, quotes, list(map(str, replay.days)), 5)
        receipt = native_parity(bundle, output, image, cpus="2")
        actual = json.loads((output / "economic.json").read_text())
        deviation = float(np.max(np.abs(np.array([float(r["nav"]) for r in actual["nav"]]) - paths[key][1:])))
        if deviation > .011:
            raise ValueError(f"Native study NAV mismatch: {key} {deviation}")
        receipts.append(dict(scenario=key, max_nav_difference=deviation,
                             bundle_sha256=digest(bundle / "manifest.json"),
                             run_receipt_sha256=digest(output / "run.json"),
                             status=receipt["status"]))
        print("Native parity:", key, deviation, flush=True)
        write(OUTPUT / "native-checks.json", receipts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "run", "native"))
    args = parser.parse_args()
    {"prepare": prepare, "run": run, "native": native_checks}[args.stage]()
