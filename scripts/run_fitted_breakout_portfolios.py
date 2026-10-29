"""Incremental selection/overlay tests from sealed corrected per-ETF fits."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_fitted_breakout_signals as analysis
import fit_breakout_signal_audit as study
from retest_fr25_lifecycle_review import metrics

OUTPUT, WORK, ROOT = study.OUTPUT, study.WORK, study.ROOT
PRIMARY = "overlay_dynamic"


def read_signals():
    analysis.verified_fits()
    manifest = json.loads((OUTPUT / "signal-manifest.json").read_text())
    if study.digest(WORK / "signals.npz") != manifest["signals.npz"]:
        raise ValueError("Signals changed")
    with np.load(WORK / "signals.npz", allow_pickle=False) as a:
        return {k: a[k].copy() for k in a.files}


def cross_sectional_ic(panel, signals):
    rows = []
    symbols, days = list(panel["symbols"]), panel["days"]
    keep = [j for j, s in enumerate(symbols) if s != "BIL"]
    bill = symbols.index("BIL")
    for era, lo, hi, suffix in (("late", "2023-01-03", "2026-10-12", "refit"), ("early", "2020-01-02", "2022-12-30", "early")):
        end = int(np.flatnonzero(days <= hi)[-1]) + 1
        for horizon in (5, 21, 63):
            labels = np.column_stack([study.stats.forward_returns(panel["open"][:end, j], panel["close"][:end, j],
                panel["open"][:end, bill], panel["close"][:end, bill], horizon) for j in keep])
            for domain in ("short", "long"):
                for score_name in (("state", "extension") if era == "late" else ("state",)):
                    values = signals[domain + ("_extension" if score_name == "extension" else "_" + suffix)][:, keep]
                    daily = []
                    for t in np.flatnonzero((days[:end] >= lo) & (days[:end] <= hi)):
                        x, y = values[t], labels[t]
                        valid = np.isfinite(x) & np.isfinite(y)
                        if valid.sum() < 10 or np.ptp(x[valid]) == 0 or np.ptp(y[valid]) == 0:
                            continue
                        rank_x, rank_y = pd.Series(x[valid]).rank(), pd.Series(y[valid]).rank()
                        daily.append(float(np.corrcoef(rank_x, rank_y)[0, 1]))
                    mean_test = study.stats.hac_regression(daily, np.empty((len(daily), 0)), lag=horizon)
                    rows.append(dict(era=era, domain=domain, score=score_name, horizon=horizon,
                        mean_ic=float(np.mean(daily)) if daily else None,
                        p=mean_test["p"][0] if mean_test else None, sessions=len(daily)))
    return rows


def overlay_targets(panel, multiplier, clock):
    monthly = study.frozen._monthly_indices(panel)
    anchors = set(map(int, monthly))
    n, m = panel["close"].shape
    weights, theory = np.zeros((n, m + 1)), np.zeros((n, m + 1))
    adopted, core = np.zeros(m + 1), np.zeros(m)
    bill = list(panel["symbols"]).index("BIL")
    indices = []
    for t in range(monthly[0], n):
        if t in anchors:
            core = panel["fr25"][t].copy()
        desired = np.r_[core * multiplier[t], 0.]
        desired[bill] += core.sum() - desired.sum()
        theory[t] = desired
        if t in anchors or (clock == "dynamic" and study.frozen.target_distance(desired, adopted) >= .10 - 1e-12):
            indices.append(t)
            weights[t] = desired
            adopted = desired.copy()
    return weights, np.array(indices, int), theory


def mappings(panel, signals):
    n, m = panel["close"].shape
    monthly = study.frozen._monthly_indices(panel)
    core = np.column_stack([panel["fr25"], np.zeros(n)])
    urth = np.zeros_like(core)
    urth[monthly[0], -1] = .98
    result = {"FR25": (core, monthly, None), "URTH": (urth, monthly[:1], None)}
    scores = study.br.momentum_score(panel["close"])
    eligible = panel["admitted"] & ((signals["short_refit"] + signals["long_refit"]) > 0)
    for clock in ("dynamic", "monthly"):
        result["selection_" + clock] = study.br.select_targets(panel, eligible, scores, monthly, clock=clock)
        result["momentum_" + clock] = study.br.select_targets(panel, panel["admitted"], scores, monthly, clock=clock)
        for source, prefix in (("refit", "overlay_"), ("original", "original_overlay_")):
            multiplier = .5 + .25 * signals["short_" + source] + .25 * signals["long_" + source]
            result[prefix + clock] = overlay_targets(panel, multiplier, clock)
    constant = np.tile(.5 + .25 * signals["prior_frequency"].sum(axis=0), (n, 1))
    result["constant_overlay_monthly"] = overlay_targets(panel, constant, "monthly")
    start = int(monthly[0])
    blocks = [np.arange(t, min(t + 21, n)) for t in range(start, n, 21)]
    for seed in (7, 11, 23):
        order = np.random.default_rng(seed).permutation(len(blocks))
        ix = np.concatenate([blocks[i] for i in order])
        multiplier = np.ones((n, m))
        multiplier[start:] = .5 + .25 * signals["short_refit"][ix] + .25 * signals["long_refit"][ix]
        for clock in ("dynamic", "monthly"):
            result[f"placebo_{seed}_{clock}"] = overlay_targets(panel, multiplier, clock)
    return result


def main():
    if (OUTPUT / "portfolio-results.json").exists():
        raise ValueError("Preserve completed evidence")
    signals = read_signals()
    panel = study.frozen._load_panel()
    study.write(OUTPUT / "cross-sectional-ic.json", cross_sectional_ic(panel, signals))
    recipe = json.loads(study.frozen.RECIPE_PATH.read_text())
    replay = study.frozen._Replay(panel, recipe, "2023-01-03")
    dates = [str(panel["days"][replay.indices[0] - 1]), *map(str, replay.days)]
    scenarios = mappings(panel, signals)
    rows, paths = [], {"dates": dates}
    for name, (weights, indices, theoretical) in scenarios.items():
        for cost, delay in study.FRICTIONS:
            result, fills = replay.run_result(weights, indices, cost, delay)
            payload = study.frozen.report_payload(replay, result, fills)
            nav = np.array([float(r["nav_cnh"]) for r in payload["nav_series"]])
            row = dict(scenario=name, cost_bp=cost, delay=delay, **metrics(nav, dates, fills), yearly={},
                       rebalances=len(result.proposals), fills=len(fills))
            for year in ("2023", "2024", "2025", "2026"):
                ix = [i for i, d in enumerate(dates) if i > 0 and d.startswith(year)]
                lo, hi = ix[0] - 1, ix[-1] + 1
                row["yearly"][year] = metrics(nav[lo:hi], dates[lo:hi], fills)
            key = f"late_{name}_c{cost}d{delay}"
            paths[key] = nav
            rows.append(row)
            if cost == 5 and delay == 0 and name in {PRIMARY, "FR25", "URTH", "selection_dynamic", "constant_overlay_monthly"}:
                study.write(WORK / (name + "-calculation.json"), dict(payload, accounting_currency="USD",
                    latest_targets=[] if theoretical is None else [dict(symbol=s, target_weight=str(w))
                        for s, w in zip(replay.symbols, theoretical[-1], strict=True) if w > 0]))
            print(name, cost, delay, round(row["cagr"] * 100, 2), round(row["sharpe"], 3), flush=True)
    gates = []
    for name in ("selection_dynamic", "selection_monthly", "overlay_dynamic", "overlay_monthly"):
        for cost, delay in study.FRICTIONS:
            candidate = next(r for r in rows if (r["scenario"], r["cost_bp"], r["delay"]) == (name, cost, delay))
            base = next(r for r in rows if (r["scenario"], r["cost_bp"], r["delay"]) == ("FR25", cost, delay))
            comparisons = dict(sharpe=candidate["sharpe"] > base["sharpe"], cagr=candidate["cagr"] >= base["cagr"] - .01,
                               drawdown=candidate["max_drawdown"] >= base["max_drawdown"])
            gates.append(dict(scenario=name, cost_bp=cost, delay=delay, **comparisons, passed=all(comparisons.values())))
            bill = panel["close"][replay.indices[0] - 1:, list(panel["symbols"]).index("BIL")]
            candidate["alpha_vs_FR25"] = study.stats.alpha(paths[f"late_{name}_c{cost}d{delay}"], paths[f"late_FR25_c{cost}d{delay}"], bill)
    read_signals()
    study.write(OUTPUT / "portfolio-results.json", dict(protocol_sha256=study.digest(OUTPUT / "protocol.json"), results=rows, gates=gates,
        script_sha256=study.digest(Path(__file__)), primary=PRIMARY))
    np.savez_compressed(WORK / "mappings.npz", **{k + "_weights": v[0] for k, v in scenarios.items()},
                        **{k + "_indices": v[1] for k, v in scenarios.items()})
    np.savez_compressed(WORK / "nav.npz", **paths)
    print("Complete", len(rows), "portfolio cases", flush=True)


if __name__ == "__main__":
    main()
