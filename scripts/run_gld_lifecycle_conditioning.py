"""Deep per-ETF stable-signal refit, then life-cycle conditioning of FR25/M1.

Stages
------
refit : per-ETF short-range and long-range fits on pre-2023 sessions only, with a
        deeper candidate set and an explicit two-era stability requirement
        (era 1: 2005-2015, era 2: 2016-2022). Saves stable panel signals.
condition : apply the stable life-cycle state as an eligibility filter on the frozen
        FR25/M1 decisions (renormalise or cash variants), compare with frozen SOTA
        and matched random filters, and test pre-2023-calibrated conditional
        overlays. All 2023+ results are development retests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
VAR = ROOT / "var" / "research" / "gld-lifecycle-conditioning-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-conditioning-20261019-v1"
POOL_VAR = ROOT / "var" / "research" / "gld-lifecycle-pool-20261019-v1"
SCANNER_VAR = ROOT / "var" / "research" / "gld-lifecycle-daily-scanner-20261019-v1"
V2 = ROOT / "var" / "research" / "range-breakout-20261018-v2"
SHORT_STUDY = ROOT / "var" / "research" / "gld-lifecycle-20261019-v1"
LONG_STUDY = ROOT / "var" / "research" / "gld-longrange-lifecycle-20261019-v1"
OOS_START = "2023-01-03"
ERA1_END = "2015-12-31"
ERA2_START = "2016-01-01"
IS_END = "2022-12-30"
WARMUP = 252
FRICTIONS = ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1))
N_RANDOM = 300
N_MUTATIONS = 60
TOP_SCREEN = 20
MIN_TRADES_PER_ERA = 2
MIN_TOTAL_TRADES = 8
MIN_EXPOSURE = 0.10
WORKERS = min(14, max(2, (mp.cpu_count() or 4) - 1))

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(V2))
from systematic_trading.research import range_lifecycle as rl  # noqa: E402
from run_gld_lifecycle_pool import (ASSET_CLASS, load_asset, load_panel, load_recipe,  # noqa: E402
                                    panel_days, list_assets)


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


def gld_anchors():
    short = list(read_json(SHORT_STUDY / "selection.json")["chosen"]["parameter_vector"])
    if len(short) == len(rl.SHORT_SPEC.parameters) - 3:
        short += [0, 0.0, 0]
    long = list(read_json(LONG_STUDY / "selection.json")["chosen"]["parameter_vector"])
    return {"short": rl.SHORT_SPEC.canonical(short), "long": rl.LONG_SPEC.canonical(long)}


def windows(features):
    days = features.days
    end = int(np.flatnonzero(days <= np.datetime64(IS_END))[-1]) + 1
    era1 = None
    if (days <= np.datetime64(ERA1_END)).any() and (days >= np.datetime64("2005-01-01")).any():
        era1 = (WARMUP, int(np.flatnonzero(days <= np.datetime64(ERA1_END))[-1]) + 1)
    era2 = (int(np.flatnonzero(days >= np.datetime64(ERA2_START))[0]), end)
    return (WARMUP, end), era1, era2


def candidate_vectors(spec, anchor, rng):
    low, high = spec.bounds[:, 0], spec.bounds[:, 1]
    random = rng.uniform(low, high, (N_RANDOM, len(spec.parameters)))
    mutated = [anchor]
    for _ in range(N_MUTATIONS):
        step = rng.normal(0.0, 0.08, len(spec.parameters)) * (high - low)
        mutated.append(np.clip(anchor + step, low, high))
    vectors = np.vstack([random, np.asarray(mutated)])
    return np.array([spec.canonical(row) for row in vectors])


def fit_domain(features, spec, anchor, rng):
    full, era1, era2 = windows(features)
    short_history = (full[1] - full[0] < 600
                     or era1 is None or era1[1] - era1[0] < 250
                     or era2[1] - era2[0] < 250)
    if short_history:
        evaluation = rl.evaluate(features, anchor, *full, cost_bp=5.0)
        return dict(parameters=anchor, stable=False, fallback=True, era1=None, era2=None,
                    full=evaluation["full"], n_closed=int(evaluation["n_closed"]),
                    exposure=float(evaluation["full"]["exposure"]), final_score=None)
    vectors = candidate_vectors(spec, anchor, rng)
    screened = []
    for vector in vectors:
        f1 = rl.evaluate(features, vector, *era1, cost_bp=5.0)
        f2 = rl.evaluate(features, vector, *era2, cost_bp=5.0)
        screened.append((min(f1["fitness"], f2["fitness"]), f1["fitness"], f2["fitness"],
                         vector, f1["n_closed"], f2["n_closed"]))
    screened.sort(key=lambda row: -row[0])
    finals = []
    for _, f1, f2, vector, n1, n2 in screened[:TOP_SCREEN]:
        scores = [rl.evaluate(features, vector, *full, cost_bp=cost, delay=delay)["fitness"]
                  for cost, delay in FRICTIONS]
        final = rl.evaluate(features, vector, *full, cost_bp=5.0)
        stable = (f1 > 0 and f2 > 0 and n1 >= MIN_TRADES_PER_ERA
                  and n2 >= MIN_TRADES_PER_ERA and final["n_closed"] >= MIN_TOTAL_TRADES
                  and final["full"]["exposure"] >= MIN_EXPOSURE)
        finals.append(dict(parameter_vector=vector.tolist(), final_score=float(min(scores)),
                           era1_fitness=float(f1), era2_fitness=float(f2),
                           era1_trades=int(n1), era2_trades=int(n2),
                           n_closed=int(final["n_closed"]),
                           exposure=float(final["full"]["exposure"]),
                           stable=bool(stable)))
    stable_rows = [row for row in finals if row["stable"]]
    pool = stable_rows if stable_rows else finals
    chosen = max(pool, key=lambda row: row["final_score"])
    vector = spec.canonical(chosen["parameter_vector"])
    full_eval = rl.evaluate(features, vector, *full, cost_bp=5.0)
    return dict(parameters=vector, stable=bool(chosen["stable"]), fallback=False,
                era1=dict(fitness=chosen["era1_fitness"], trades=chosen["era1_trades"]),
                era2=dict(fitness=chosen["era2_fitness"], trades=chosen["era2_trades"]),
                full=full_eval["full"], n_closed=int(chosen["n_closed"]),
                exposure=float(chosen["exposure"]),
                final_score=float(chosen["final_score"]))


def score_signals(features, spec, params, pdays):
    prepared = rl.prepare(features, params)
    sim = rl.simulate(features, prepared, start=WARMUP, cost_bp=5.0, trace=True)
    n = len(features.days)
    active = np.zeros(n, bool)
    score = np.zeros(n)
    for t in range(n):
        active[t] = int(sim["state"][t]) == rl.STATE_LONG
        level, atr = sim["level"][t], prepared["atr"][t]
        if active[t] and np.isfinite(level) and np.isfinite(atr) and atr > 0:
            score[t] = max(0.0, float((features.close[t] - level) / atr))
    lookup = {str(np.datetime64(d, "D")): i for i, d in enumerate(features.days)}
    panel_active = np.zeros(len(pdays), bool)
    panel_score = np.zeros(len(pdays))
    for i, day in enumerate(pdays):
        j = lookup.get(str(np.datetime64(day, "D")))
        if j is not None:
            panel_active[i] = active[j]
            panel_score[i] = score[j]
    return panel_active, panel_score, sim, prepared


def refit_asset(symbol):
    data = load_asset(symbol)
    panel = load_panel()
    pdays = panel_days(panel)
    rng = np.random.default_rng(50_000 + sum(ord(c) for c in symbol))
    anchors = gld_anchors()
    result = dict(symbol=symbol, class_=ASSET_CLASS.get(symbol, "Other"))
    arrays = {}
    for kind, spec, anchor in (("short", rl.SHORT_SPEC, anchors["short"]),
                               ("long", rl.LONG_SPEC, anchors["long"])):
        features = rl.Features.build(data, spec)
        fit = fit_domain(features, spec, anchor, rng)
        active, score, sim, prepared = score_signals(features, spec, fit["parameters"], pdays)
        arrays[f"{kind}_active"] = active.astype(np.int8)
        arrays[f"{kind}_score"] = score.astype(np.float32)
        result[kind] = dict(parameters=fit["parameters"].tolist(),
                            decoded=spec.describe(fit["parameters"]),
                            stable=fit["stable"], fallback=fit["fallback"],
                            era1=fit.get("era1"), era2=fit.get("era2"),
                            is_metrics=fit["full"], n_closed=fit.get("n_closed"),
                            exposure=fit.get("exposure"),
                            final_score=fit.get("final_score"))
    return result, arrays


def refit():
    VAR.mkdir(parents=True, exist_ok=True)
    (VAR / "fit").mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    assets = list_assets(panel)
    results, arrays = {}, {}
    with mp.Pool(WORKERS) as pool:
        for i, (result, asset_arrays) in enumerate(pool.imap_unordered(refit_asset, assets)):
            results[result["symbol"]] = result
            for key, value in asset_arrays.items():
                arrays.setdefault(key, {})[result["symbol"]] = value
            print(f"[{i + 1}/{len(assets)}] {result['symbol']} refit", flush=True)
    symbols = sorted(results)
    out = {key: np.vstack([by_symbol[s] for s in symbols]) for key, by_symbol in arrays.items()}
    out["symbols"] = np.array(symbols)
    np.savez_compressed(VAR / "fit" / "stable-panel-signals.npz", **out)
    write_json(VAR / "fit" / "per-asset.json", results)
    stable_short = sum(1 for s in symbols if results[s]["short"]["stable"])
    stable_long = sum(1 for s in symbols if results[s]["long"]["stable"])
    write_json(VAR / "fit" / "summary.json", dict(
        assets=len(symbols), stable_short=stable_short, stable_long=stable_long,
        fallback_short=sum(1 for s in symbols if results[s]["short"]["fallback"]),
        fallback_long=sum(1 for s in symbols if results[s]["long"]["fallback"]),
        two_era_requirement=(f"era1 2005-2015 and era2 2016-2022 both positive fitness, "
                             f">={MIN_TRADES_PER_ERA} closed trades per era, "
                             f">={MIN_TOTAL_TRADES} total and >={MIN_EXPOSURE:.0%} exposure"),
    ))
    print(json.dumps(read_json(VAR / "fit" / "summary.json"), indent=1))


# --------------------------------------------------------------------------------------
# Conditioning of FR25 / M1
# --------------------------------------------------------------------------------------
def load_stable_signals():
    d = np.load(VAR / "fit" / "stable-panel-signals.npz", allow_pickle=True)
    symbols = [str(s) for s in d["symbols"]]
    return symbols, {k: d[k] for k in d.files if k != "symbols"}


def monthly_decision_indices(panel):
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    initial = int(np.flatnonzero(np.array(days) <= "2022-12-30")[-1])
    indices = [initial]
    previous = days[initial][:7]
    for t in range(initial + 1, len(days)):
        month = days[t][:7]
        if month != previous and t - 1 > initial:
            indices.append(t - 1)
            previous = month
    return np.array(indices, dtype=int)


def breadth_series(panel, signals):
    """Pre-2023-calibrated life-cycle breadth: number of assets with a stable union signal."""
    active = (signals["short_active"] > 0) | (signals["long_active"] > 0)
    return active.sum(axis=1)


def condition_targets(panel, order, active, base_weights, indices, mode, variant):
    """Filter frozen target weights by life-cycle activity at the decision close."""
    targets = np.zeros((panel["close"].shape[0], len(order) + 1))
    for t in indices:
        weights = np.array([base_weights[t, order.index(s)] for s in order])
        held = np.flatnonzero(weights > 0)
        keep = np.array([j for j in held if active[t, j]], dtype=int)
        if len(keep) == 0:
            continue
        if variant == "cash":
            targets[t, keep] = weights[keep]
        elif variant == "renormalise":
            total = weights[keep].sum()
            targets[t, keep] = weights[keep] / total * 0.98
        else:
            raise ValueError(variant)
    return targets


def random_filter_targets(panel, order, active, base_weights, indices, variant, seed):
    rng = np.random.default_rng(seed)
    targets = np.zeros((panel["close"].shape[0], len(order) + 1))
    for t in indices:
        weights = np.array([base_weights[t, order.index(s)] for s in order])
        held = np.flatnonzero(weights > 0)
        if len(held) == 0:
            continue
        keep_count = int(active[t, held].sum())
        if keep_count == 0:
            continue
        keep = rng.choice(held, size=min(keep_count, len(held)), replace=False)
        if variant == "cash":
            targets[t, keep] = weights[keep]
        else:
            targets[t, keep] = weights[keep] / weights[keep].sum() * 0.98
    return targets


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


def load_m1_targets(panel):
    mapping = np.load(V2 / "pool" / "mappings.npz")
    weights = mapping["M1_monthly__weights"][:, :-1]
    indices = mapping["M1_monthly__indices"]
    return weights, indices


def condition():
    sys.path.insert(0, str(V2))
    from run_range_breakout import Replay  # noqa: E402
    VAR.mkdir(parents=True, exist_ok=True)
    (VAR / "condition").mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    recipe = load_recipe()
    order = [str(s) for s in panel["symbols"]]
    symbols, signals = load_stable_signals()
    signals = {k: np.column_stack([signals[k][symbols.index(s)] for s in order]) for k in signals}
    union = ((signals["short_active"] > 0) | (signals["long_active"] > 0))
    short_only = signals["short_active"] > 0
    long_only = signals["long_active"] > 0
    replay = Replay(panel, recipe, OOS_START)
    days = panel_days(panel)
    indices = monthly_decision_indices(panel)
    fr25 = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    m1_weights, m1_indices = load_m1_targets(panel)
    # Benchmarks.
    benchmark_stems = {"FR25 SOTA": "FR25_c5d0", "M1 momentum control": "M1_monthly_c5d0",
                       "Equal weight": "equal_weight_c5d0", "URTH": "URTH_c5d0",
                       "FR25 (10bp)": "FR25_c10d0", "FR25 (20bp)": "FR25_c20d0",
                       "FR25 (+1 delay)": "FR25_c5d1"}
    benchmarks = {}
    for label, stem in benchmark_stems.items():
        d = np.load(V2 / "pool" / "paths" / f"{stem}.npz")
        benchmarks[label] = dict(nav=d["nav"], exposure=d["exposure"],
                                 metrics=metrics(d["nav"], d["exposure"]))
    # Integrity: replay frozen FR25 targets.
    fr25_replay, _, _ = replay.run(fr25, indices, 5.0, 0)
    integrity = dict(fr25_max_relative_deviation=float(
        np.abs(fr25_replay["nav"] / benchmarks["FR25 SOTA"]["nav"] - 1.0).max()))
    results, daily = {}, {}
    # Conditioned FR25 variants.
    for signal_name, active in (("union", union), ("short", short_only), ("long", long_only)):
        for variant in ("renormalise", "cash"):
            targets = condition_targets(panel, order, active, panel["fr25"], indices, "fr25", variant)
            for cost, delay in FRICTIONS:
                compact, _, fills = replay.run(targets, indices, cost, delay)
                key = f"FR25 {signal_name} {variant} | {cost:g}bp d{delay}"
                results[key] = dict(kind="conditioned", source=signal_name, variant=variant,
                                    cost_bp=cost, delay=delay, fills=int(fills),
                                    indices=int(len(indices)),
                                    metrics=metrics(compact["nav"], compact["exposure"],
                                                    compact["turnover"], compact["fees"]))
                if cost == 5.0 and delay == 0:
                    daily[key] = compact["nav"]
    # Matched random-filter controls for the renormalised union filter.
    for seed in (7, 11, 23):
        targets = random_filter_targets(panel, order, union, panel["fr25"], indices,
                                        "renormalise", seed)
        compact, _, fills = replay.run(targets, indices, 5.0, 0)
        key = f"FR25 random matched filter seed{seed} | 5bp d0"
        results[key] = dict(kind="control", source="random", variant="renormalise",
                            cost_bp=5.0, delay=0, fills=int(fills),
                            indices=int(len(indices)),
                            metrics=metrics(compact["nav"], compact["exposure"],
                                            compact["turnover"], compact["fees"]))
        daily[key] = compact["nav"]
    # M1 conditioned (renormalised, union), if the frozen mapping layout matches.
    if m1_weights.shape[0] == panel["close"].shape[0]:
        m1_targets = np.column_stack([m1_weights, np.zeros(panel["close"].shape[0])])
        for signal_name, active in (("union", union), ("short", short_only)):
            targets = np.zeros_like(m1_targets)
            for t in m1_indices:
                weights = m1_targets[t, :-1]
                held = np.flatnonzero(weights > 0)
                keep = np.array([j for j in held if active[t, j]], dtype=int)
                if len(keep):
                    targets[t, keep] = weights[keep] / weights[keep].sum() * weights[held].sum()
            compact, _, fills = replay.run(targets, m1_indices, 5.0, 0)
            key = f"M1 {signal_name} renormalise | 5bp d0"
            results[key] = dict(kind="conditioned", source=signal_name, variant="renormalise",
                                cost_bp=5.0, delay=0, fills=int(fills),
                                indices=int(len(m1_indices)),
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            daily[key] = compact["nav"]
    # Pre-2023 calibration of the life-cycle breadth threshold (median monthly breadth).
    breadth = breadth_series(panel, signals)
    pre_mask = (days <= np.datetime64("2022-12-30"))
    pre_breadth = breadth[pre_mask]
    threshold = float(np.median(pre_breadth))
    # Conditional overlay: 20% short-only Rule A sleeve only in months where the
    # pre-2023-calibrated breadth condition is true.
    scanner = pd.read_csv(SCANNER_VAR / "daily-nav.csv", parse_dates=["date"])
    sleeve = scanner["equal_split|short"].to_numpy(float)
    fr25_nav = benchmarks["FR25 SOTA"]["nav"]
    sleeve_ret = sleeve[1:] / sleeve[:-1] - 1.0
    fr25_ret = fr25_nav[1:] / fr25_nav[:-1] - 1.0
    oos_days = days[-len(fr25_nav):]
    # Daily hold mask from month-end decisions (condition known at the decision close,
    # applied from the next session -> no same-day look-ahead).
    decision_dates = pd.to_datetime(panel["days"])
    mask = np.zeros(len(fr25_nav), dtype=bool)
    cursor = 0
    for i, day in enumerate(oos_days):
        while cursor + 1 < len(indices) and decision_dates[indices[cursor + 1]] < pd.Timestamp(day):
            cursor += 1
        mask[i] = bool(breadth[indices[cursor]] >= threshold)
    overlay_ret = fr25_ret + np.where(mask[1:], 0.2, 0.0) * (sleeve_ret - fr25_ret)
    overlay_nav = np.r_[fr25_nav[0], fr25_nav[0] * np.cumprod(1.0 + overlay_ret)]
    unconditional_ret = fr25_ret + 0.2 * (sleeve_ret - fr25_ret)
    unconditional_nav = np.r_[fr25_nav[0], fr25_nav[0] * np.cumprod(1.0 + unconditional_ret)]
    conditional = metrics(overlay_nav, np.ones(len(overlay_nav)))
    unconditional = metrics(unconditional_nav, np.ones(len(unconditional_nav)))
    overlay_diagnostics = dict(
        breadth_threshold=threshold,
        pre_2023_months=int(pre_mask.sum()),
        share_of_months_condition_true=float(np.mean(mask)),
        conditional=conditional, unconditional=unconditional,
        sleeve_source="Rule A short-only daily NAV from the daily-scanner study",
        capital_to_sleeve=0.20,
    )
    daily["Conditional overlay 20% Rule A short"] = overlay_nav
    daily["Unconditional overlay 20% Rule A short"] = unconditional_nav
    # Results and annual table.
    annual = {}
    for label, nav in daily.items():
        annual[label] = {}
        for year in (2023, 2024, 2025, 2026):
            mask_year = (oos_days >= np.datetime64(f"{year}-01-01")) & (
                oos_days <= np.datetime64(f"{year}-12-31"))
            idx = np.flatnonzero(mask_year)
            if len(idx) < 20:
                annual[label][str(year)] = None
                continue
            s, e = int(idx[0]), int(idx[-1]) + 1
            annual[label][str(year)] = float(nav[e - 1] / nav[s] - 1.0)
    evidence = dict(
        identity="gld-lifecycle-conditioning-20261019-v1",
        protocol=dict(
            authority="Research only; no monitoring, promotion, funding or broker action.",
            refit=(f"Per-ETF refit on pre-2023 only: {N_RANDOM} random vectors + GLD vector + "
                   f"{N_MUTATIONS} anchor mutations; screen by worst of the two eras; top "
                   f"{TOP_SCREEN} replayed at 5/10/20bp and +1 delay; stability requires positive "
                   f"fitness and >= {MIN_TRADES_PER_ERA} closed trades in both 2005-2015 and "
                   f"2016-2022, >= {MIN_TOTAL_TRADES} total and >= {MIN_EXPOSURE:.0%} exposure."),
            conditioning=("At each FR25/M1 monthly decision, names without a stable life-cycle "
                          "signal are either removed and the rest renormalised to 98% or removed "
                          "and left in cash; matched random filters remove the same number of names."),
            conditional_overlay=("20% capital to the Rule A short-only daily sleeve only in months "
                                 "where the number of stable union signals is at or above the "
                                 "pre-2023 median monthly breadth; compare with the unconditional "
                                 "20% overlay and FR25."),
            frictions=[dict(cost_bp=c, delay=d) for c, d in FRICTIONS],
        ),
        fit=read_json(VAR / "fit" / "summary.json"),
        benchmarks={k: v["metrics"] for k, v in benchmarks.items()},
        results=results, conditional_overlay=overlay_diagnostics,
        annual_returns=annual, integrity=integrity,
        chronology=dict(fit_end=IS_END, oos_start=OOS_START,
                        oos_end=str(np.datetime64(panel["days"][-1], "D"))),
    )
    write_json(VAR / "condition" / "evidence.json", evidence)
    nav_frame = {"date": oos_days.astype("datetime64[D]").astype(str).tolist()}
    for label, nav in daily.items():
        nav_frame[label] = nav
    for label in ("FR25 SOTA", "M1 momentum control", "Equal weight"):
        nav_frame[label] = benchmarks[label]["nav"]
    pd.DataFrame(nav_frame).to_csv(VAR / "condition" / "daily-nav.csv", index=False,
                                   float_format="%.4f")
    frame = []
    for key, row in results.items():
        m = row["metrics"]
        frame.append(dict(scenario=key, kind=row["kind"], source=row.get("source"),
                          variant=row.get("variant"), cost_bp=row["cost_bp"],
                          delay=row["delay"], fills=row["fills"], rebalances=row["indices"],
                          **m))
    pd.DataFrame(frame).to_csv(VAR / "condition" / "scenarios.csv", index=False)
    print(json.dumps(dict(
        fit=read_json(VAR / "fit" / "summary.json"),
        fr25=benchmarks["FR25 SOTA"]["metrics"],
        conditioned={k: {m: round(v, 4) for m, v in r["metrics"].items()}
                     for k, r in results.items() if "FR25 union renormalise | 5bp d0" in k},
        overlay=dict(threshold=threshold,
                     share=overlay_diagnostics["share_of_months_condition_true"],
                     conditional=conditional, unconditional=unconditional),
        integrity=integrity), indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["refit", "condition"])
    args = parser.parse_args()
    globals()[args.stage]()
