"""GLD range-lifecycle study: fit pre-2023, seal, evaluate 2023+ out of sample.

Stages
------
prepare : pin the audited GLD input, verify hashes, write the predeclared protocol.
fit     : parallel differential evolution on pre-2023 sessions only.
select  : replay finalists at the friction set, apply evidence guards and
          neighbourhood stability, then seal one parameter vector.
evaluate: run the sealed vector on the full history, emit IS/OOS evidence, the
          daily ledger and episode records. IS results must equal the sealed fit
          exactly (a causality check: 2023+ arrays do not influence pre-2023).
validate: fit 2005-2015, select, then evaluate 2016-2022 pseudo-out-of-sample.

Research only: no strategy monitoring, allocation, funding or broker authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
VAR = Path(os.environ.get("GLD_STUDY_VAR", str(ROOT / "var" / "research" /
                                              "gld-lifecycle-20261019-v1")))
PUB = Path(os.environ.get("GLD_STUDY_PUB", str(ROOT / "research" /
                                              "gld-lifecycle-20261019-v1")))
PINNED = ROOT / "var" / "research" / "range-breakout-20261018-v2"
ASSET = PINNED / "assets" / "GLD.npz"
PINNED_MANIFEST = PINNED / "input_manifest.json"
PINNED_PRICE_PIN = PINNED / "price_pin.json"
SOURCE_MODULE = ROOT / "src" / "systematic_trading" / "research" / "range_lifecycle.py"
SOURCE_RUNNER = Path(__file__)

sys.path.insert(0, str(ROOT / "src"))
from systematic_trading.research import range_lifecycle as rl  # noqa: E402

IS_END = "2022-12-30"
OOS_START = "2023-01-01"
FIT_FEATURE_FILE = "gld-features-is.npz"
FULL_FEATURE_FILE = "gld-features-full.npz"
WARMUP = 252
FRICTIONS = ((5.0, 0), (10.0, 0), (5.0, 1), (20.0, 0))
DE_SEEDS = 4
DE_POPSIZE = 20
DE_GENERATIONS = 110
TOP_K = 400
VALIDATION_FIT_END = "2015-12-31"
VALIDATION_OOS_START = "2016-01-01"
VALIDATION_OOS_END = "2022-12-30"
VALIDATION_SEEDS = 2
VALIDATION_POPSIZE = 16
VALIDATION_GENERATIONS = 80
WORKERS = min(14, max(2, (mp.cpu_count() or 4) - 2))
PILOT_STUDY = ROOT / "var" / "research" / "gld-lifecycle-20261019-v1"

SPEC_KIND = os.environ.get("GLD_STUDY_KIND", "short")
SPEC = rl.LONG_SPEC if SPEC_KIND == "long" else rl.SHORT_SPEC
DOMAIN_IS_LONG = SPEC_KIND == "long"
IDENTITY = os.environ.get(
    "GLD_STUDY_ID",
    "gld-longrange-lifecycle-20261019-v1" if DOMAIN_IS_LONG else "gld-lifecycle-20261019-v1")
DE_SEEDS = int(os.environ.get("GLD_DE_SEEDS", DE_SEEDS))
DE_POPSIZE = int(os.environ.get("GLD_DE_POPSIZE", DE_POPSIZE))
DE_GENERATIONS = int(os.environ.get("GLD_DE_GENERATIONS", DE_GENERATIONS))
TOP_K = int(os.environ.get("GLD_TOP_K", TOP_K))
VALIDATION_SEEDS = int(os.environ.get("GLD_VALIDATION_SEEDS", VALIDATION_SEEDS))
VALIDATION_GENERATIONS = int(os.environ.get("GLD_VALIDATION_GENERATIONS", VALIDATION_GENERATIONS))

QUESTION_TEXT = (
    "Does an explicit long-range-compression -> confirmed-breakout -> wide dynamic-trailing "
    "lifecycle identify GLD's multi-quarter regime breakouts early and ride them with much "
    "larger initial risk and trailing distances than the short-range variant?"
    if DOMAIN_IS_LONG else
    "Does an explicit tight-range -> confirmed-breakout -> dynamic-trailing-exit lifecycle "
    "identify GLD's regime breakouts early, hold them through noise, and exit near overheat "
    "using a drawdown-from-recent-high take profit?")
DIRECTION_TEXT = (
    "Second requested GLD strategy: same lifecycle and objective, but a predeclared long-range "
    "structural domain (126-756 session lookbacks, 4-20 ATR initial stops, 3-20 ATR / 8-50% "
    "trailing distances, 0-504 session time limits). Every behavioral threshold inside that "
    "domain is fitted on pre-2023 sessions. The short-range study remains the frozen comparison "
    "strategy; the two are combined only after both are sealed."
    if DOMAIN_IS_LONG else
    "GLD first; all behavioral thresholds fitted. The earlier arbitrary log(1.25) range limit, "
    "8-close confirmation, 5-session progress exit and tight ATR stop are replaced by fitted "
    "choices.")
LONG_DOMAIN_NOTE = (
    "Long-range domain: candidate windows 126-756 sessions; ATR periods 20-120; volume "
    "references 63-252; time limits 0/126/252/504; initial stops 4-20 ATR; failed-range floors "
    "-1 to 8 ATR; trailing 3-20 ATR or 8-50%; cooldown 0-126 sessions. The domain was "
    "predeclared before fitting and is the only structural difference from the short-range study."
    if DOMAIN_IS_LONG else
    "Short-range domain: the original predeclared menus and close/trail bounds of the first GLD "
    "lifecycle study, preserved exactly.")


def warm_start_anchors():
    """Earlier IS-only calibration vectors, made valid for the current search space.

    A warm start is used only for the short-range domain, from the earlier sealed
    pre-2023 vector. The long-range domain is a different structural search and
    starts cold.
    """
    if DOMAIN_IS_LONG:
        return []
    path = PILOT_STUDY / "selection.json"
    if not path.exists():
        return []
    base = list(read_json(path)["chosen"]["parameter_vector"])
    if len(base) == len(SPEC.parameters):
        return [base]
    if len(base) == len(SPEC.parameters) - 3:
        return [base + [0, 0.0, 0]]
    return []


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value))


def manifest(root, name, files):
    root = Path(root)
    rows = {}
    for f in files:
        f = Path(f)
        rows[str(f.relative_to(root)).replace("\\", "/")] = sha256(f)
    write_json(root / name, rows)
    return rows


def verify_manifest(root, name):
    root = Path(root)
    rows = read_json(root / name)
    for relative, digest in rows.items():
        if sha256(root / relative) != digest:
            raise ValueError(f"Manifest mismatch for {relative}")
    return rows


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
def load_pinned_gld():
    pinned = read_json(PINNED_MANIFEST)
    digest = sha256(ASSET)
    if pinned["assets/GLD.npz"] != digest:
        raise ValueError("Pinned GLD input hash mismatch")
    pin = read_json(PINNED_PRICE_PIN)
    d = np.load(ASSET, allow_pickle=True)
    data = {k: np.asarray(d[k]) for k in ("open", "high", "low", "close", "volume",
                                          "raw_close", "days")}
    if not np.allclose(data["close"], data["raw_close"]):
        raise ValueError("Adjusted and raw GLD closes differ")
    return data, dict(asset_sha256=digest, batch=pin["batch"], root=pin["root"],
                      through=pin["through"])


def export_features(features, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, days=features.days, open=features.open, high=features.high,
                        low=features.low, close=features.close, volume=features.volume)


def load_features(path):
    d = np.load(path, allow_pickle=True)
    return rl.Features.build({k: d[k] for k in ("open", "high", "low", "close", "volume", "days")},
                             SPEC)


def features_until(features, last_date):
    return features.truncated(np.datetime64(last_date, "D"))


def mapped_parameters(vector):
    """Sealed vectors from the 24-parameter study map onto the module with re-entry off."""
    values = list(vector)
    if len(values) == len(SPEC.parameters):
        return SPEC.canonical(values)
    if len(values) == len(SPEC.parameters) - 3:
        return SPEC.canonical(values + [0, 0.0, 0])
    raise ValueError(f"Unsupported parameter vector length {len(values)}")


# --------------------------------------------------------------------------------------
# Workers
# --------------------------------------------------------------------------------------
_WORKER = {}


def _init_worker(npz_path, start, end, cost, delay):
    _WORKER["features"] = load_features(npz_path)
    _WORKER["start"] = int(start)
    _WORKER["end"] = int(end)
    _WORKER["cost"] = float(cost)
    _WORKER["delay"] = int(delay)


def _compact(ev):
    return (float(ev["fitness"]), float(ev["full"]["cagr"]), float(ev["full"]["sharpe"]),
            float(ev["full"]["maxdd"]), float(ev["full"]["calmar"]),
            float(ev["full"]["exposure"]), int(ev["n_closed"]), float(ev["utility"]),
            float(ev["robust"]),
            float(np.median([b["utility"] for b in ev["blocks"]])),
            float(np.std([b["utility"] for b in ev["blocks"]])))


def _worker_eval(parameters):
    ev = rl.evaluate(_WORKER["features"], parameters, _WORKER["start"], _WORKER["end"],
                     cost_bp=_WORKER["cost"], delay=_WORKER["delay"])
    return _compact(ev)


def _worker_full(args):
    parameters, cost, delay = args
    features = _WORKER["features"]
    ev = rl.evaluate(features, parameters, _WORKER["start"], _WORKER["end"],
                     cost_bp=cost, delay=delay)
    return (float(ev["fitness"]), ev["full"], ev["buyhold"], int(ev["n_closed"]),
            int(ev["n_open"]), [b["utility"] for b in ev["blocks"]],
            ev["episodes"])


# --------------------------------------------------------------------------------------
# Differential evolution
# --------------------------------------------------------------------------------------
def differential_evolution(pool, seed, popsize, generations, d, record, anchors=()):
    bounds = SPEC.bounds
    integral = SPEC.integral
    rng = np.random.default_rng(seed)
    population = rng.uniform(bounds[:, 0], bounds[:, 1], (popsize * d, d))
    for j in range(d):
        if integral[j]:
            population[:, j] = rng.integers(int(bounds[j, 0]), int(bounds[j, 1]) + 1,
                                            population.shape[0])
    population = np.array([SPEC.canonical(row) for row in population])
    for row_index, anchor in enumerate(anchors):
        if row_index < len(population):
            population[row_index] = SPEC.canonical(anchor)
    rows = pool.map(_worker_eval, population)
    for row, rec in zip(population, rows):
        record(row, rec)
    scores = np.array([rec[0] for rec in rows], float)
    idx = int(np.argmax(scores))
    best = (population[idx].copy(), float(scores[idx]))
    for generation in range(generations):
        trials = np.empty_like(population)
        for i in range(population.shape[0]):
            r1, r2, r3 = rng.choice(population.shape[0], 3, replace=False)
            mutant = population[r1] + 0.7 * (population[r2] - population[r3])
            crossover = rng.random(d) < 0.9
            trials[i] = np.where(crossover, mutant, population[i])
        trials = np.array([SPEC.canonical(row) for row in trials])
        trial_rows = pool.map(_worker_eval, trials)
        trial_scores = np.array([rec[0] for rec in trial_rows], float)
        for row, rec in zip(trials, trial_rows):
            record(row, rec)
        take = trial_scores > scores
        population[take] = trials[take]
        scores[take] = trial_scores[take]
        idx = int(np.argmax(scores))
        if scores[idx] > best[1]:
            best = (population[idx].copy(), float(scores[idx]))
        if (generation + 1) % 10 == 0:
            print(f"  gen {generation + 1:3d}/{generations} best {best[1]:.4f} "
                  f"pop_mean {scores.mean():.4f}", flush=True)
    return best


def _new_history():
    return {k: [] for k in ("parameters", "fitness", "cagr", "sharpe", "maxdd", "calmar",
                            "exposure", "n_closed", "utility", "robust", "median_block",
                            "std_block", "seed")}


def _record(history, seed_index):
    def record(row, rec):
        history["parameters"].append(np.asarray(row, np.float32))
        for key, value in zip(("fitness", "cagr", "sharpe", "maxdd", "calmar", "exposure",
                               "n_closed", "utility", "robust", "median_block", "std_block"), rec):
            history[key].append(value)
        history["seed"].append(seed_index)
    return record


def _save_search(history, work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(work / "search.npz",
                        parameters=np.asarray(history["parameters"], np.float32),
                        fitness=np.asarray(history["fitness"], np.float32),
                        cagr=np.asarray(history["cagr"], np.float32),
                        sharpe=np.asarray(history["sharpe"], np.float32),
                        maxdd=np.asarray(history["maxdd"], np.float32),
                        calmar=np.asarray(history["calmar"], np.float32),
                        exposure=np.asarray(history["exposure"], np.float32),
                        n_closed=np.asarray(history["n_closed"], np.float32),
                        utility=np.asarray(history["utility"], np.float32),
                        robust=np.asarray(history["robust"], np.float32),
                        median_block=np.asarray(history["median_block"], np.float32),
                        std_block=np.asarray(history["std_block"], np.float32),
                        seed=np.asarray(history["seed"], np.int16))


def run_fit(stage_root, fit_features_path, start, end, seeds, popsize, generations,
            use_anchors=True):
    stage_root = Path(stage_root)
    work = stage_root / "fit"
    work.mkdir(parents=True, exist_ok=True)
    anchors_path = stage_root / "inputs" / "anchors.json"
    anchors = read_json(anchors_path) if (use_anchors and anchors_path.exists()) else []
    if anchors:
        print(f"warm-start anchors: {len(anchors)}", flush=True)
    d = len(SPEC.parameters)
    history = _new_history()
    seed_bests = []
    with mp.Pool(WORKERS, initializer=_init_worker,
                 initargs=(str(fit_features_path), start, end, 5.0, 0)) as pool:
        for seed_index in range(seeds):
            seed = 10_019 + 1_007 * seed_index
            print(f"seed {seed_index + 1}/{seeds} rng={seed} workers={WORKERS}", flush=True)
            best = differential_evolution(pool, seed, popsize, generations, d,
                                          _record(history, seed_index), anchors=anchors)
            seed_bests.append(dict(seed=seed, best_fitness=best[1],
                                   parameter_vector=best[0].tolist(),
                                   decoded=rl.describe(best[0], SPEC)))
    _save_search(history, work)
    parameters = np.asarray(history["parameters"], float)
    order = np.argsort(-np.asarray(history["fitness"], float))[:60]
    top = [dict(rank=i + 1, fitness=float(history["fitness"][j]),
                cagr=float(history["cagr"][j]), sharpe=float(history["sharpe"][j]),
                maxdd=float(history["maxdd"][j]), exposure=float(history["exposure"][j]),
                n_closed=int(history["n_closed"][j]),
                parameter_vector=parameters[j].tolist(),
                decoded=rl.describe(parameters[j], SPEC))
           for i, j in enumerate(order)]
    write_json(work / "seed_bests.json", seed_bests)
    write_json(work / "top60.json", top)
    print(f"evaluations={len(parameters)} best_fitness={max(history['fitness']):.4f}", flush=True)
    manifest(work, "manifest.json", [work / "search.npz", work / "top60.json",
                                     work / "seed_bests.json"])
    return top


# --------------------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------------------
def neighbourhood(pool, candidate, delta=0.05):
    p = SPEC.canonical(candidate)
    bounds = SPEC.bounds
    integral = SPEC.integral
    points = []
    for j in range(len(p)):
        lo, hi = bounds[j]
        if integral[j]:
            values = (p[j] - 1, p[j] + 1)
            for value in values:
                q = p.copy()
                q[j] = np.clip(value, lo, hi)
                points.append(q)
        else:
            for value in (p[j] - delta * (hi - lo), p[j] + delta * (hi - lo)):
                q = p.copy()
                q[j] = np.clip(value, lo, hi)
                points.append(q)
    base = pool.map(_worker_eval, [p])[0][0]
    rows = pool.map(_worker_eval, points)
    fraction = float(np.mean([rec[0] >= base - 0.15 for rec in rows]))
    return fraction, float(np.median([rec[0] for rec in rows])), float(base)


def run_select(stage_root, fit_features_path, start, end, frictions=FRICTIONS, top_k=TOP_K,
               sealed_name="selection.json"):
    stage_root = Path(stage_root)
    work = stage_root / "fit"
    verify_manifest(work, "manifest.json")
    search = np.load(work / "search.npz")
    parameters = search["parameters"].astype(float)
    fitness = search["fitness"].astype(float)
    features = load_features(fit_features_path)
    order = np.argsort(-fitness)[:top_k]
    buyhold = {}
    for cost, delay in frictions:
        bh = rl.buy_hold(features, start, end, cost_bp=cost)
        buyhold[(cost, delay)] = rl.stats(bh["nav"], bh["weight"], start, end)
    with mp.Pool(WORKERS, initializer=_init_worker,
                 initargs=(str(fit_features_path), start, end, 5.0, 0)) as pool:
        print(f"replaying {len(order)} finalists x {len(frictions)} frictions", flush=True)
        args = [(parameters[i], cost, delay) for i in order for cost, delay in frictions]
        results = pool.map(_worker_full, args)
        cursor = 0
        rows = []
        for i in order:
            scenarios = []
            block_episodes = None
            for cost, delay in frictions:
                rec = results[cursor]
                cursor += 1
                if block_episodes is None:
                    block_episodes = rec[6]
                scenarios.append(dict(cost_bp=cost, delay=delay, fitness=rec[0], rule=rec[1],
                                      n_closed=rec[3], n_open=rec[4],
                                      block_utilities=rec[5]))
            final_score = min(s["fitness"] for s in scenarios)
            base = scenarios[0]
            bounds = rl.block_bounds(start, end, 3)
            trades_per_block = [0, 0, 0]
            for episode in block_episodes:
                if episode["exit_index"] is None:
                    continue
                for b, (b0, b1) in enumerate(bounds):
                    if b0 <= episode["exit_index"] < b1:
                        trades_per_block[b] += 1
            evidence = (base["n_closed"] >= 10 and base["rule"]["exposure"] >= 0.20
                        and min(trades_per_block) >= 1)
            guards = all(
                s["rule"]["cagr"] >= buyhold[(s["cost_bp"], s["delay"])]["cagr"] - 0.02
                and s["rule"]["maxdd"] >= buyhold[(s["cost_bp"], s["delay"])]["maxdd"] - 0.05
                for s in scenarios)
            years = (end - start) / 252.0
            rows.append(dict(parameter_vector=parameters[i].tolist(),
                             decoded=rl.describe(parameters[i], SPEC),
                             screen_fitness=float(fitness[i]),
                             final_score=float(final_score),
                             evidence=bool(evidence), guards=bool(guards),
                             trades_per_block=trades_per_block,
                             annual_turnover=float(2.0 * base["n_closed"] / years),
                             scenarios=scenarios))
        qualified = [r for r in rows if r["evidence"] and r["guards"]]
        evidence_rows = [r for r in rows if r["evidence"]]
        pool_rows = qualified if qualified else evidence_rows
        fallback = not qualified
        if not pool_rows:
            pool_rows = sorted(rows, key=lambda r: -r["final_score"])[:1]
            fallback = True
        best_score = max(r["final_score"] for r in pool_rows)
        near_best = [r for r in pool_rows if r["final_score"] >= best_score - 0.05]
        print(f"guard-passing={len(qualified)} evidence={len(evidence_rows)} "
              f"near_best={len(near_best)} best={best_score:.4f}", flush=True)
        for row in near_best:
            fraction, median_neighbour, base = neighbourhood(pool, row["parameter_vector"])
            row["neighbour_fraction"] = fraction
            row["neighbour_median_fitness"] = median_neighbour
        near_best.sort(key=lambda r: (-r["neighbour_fraction"], r["annual_turnover"],
                                      -r["scenarios"][0]["rule"]["exposure"],
                                      r["parameter_vector"]))
        chosen = near_best[0]
    chosen["selection_pool"] = ("guards" if qualified else
                                ("evidence" if evidence_rows else "descriptive-fallback"))
    chosen["fallback"] = bool(fallback)
    chosen["selection_cost"] = dict(finalists=len(order), frictions=len(frictions),
                                    near_best=len(near_best))
    chosen["fit_window"] = dict(start=str(features.days[start]), end=str(features.days[end - 1]),
                                sessions=int(end - start))
    chosen["frictions"] = [dict(cost_bp=c, delay=d) for c, d in frictions]
    chosen["buyhold"] = {f"{c}:{d}": buyhold[(c, d)] for c, d in frictions}
    payload = dict(chosen=chosen, finalists=rows)
    out = stage_root / sealed_name
    write_json(out, payload)
    digest = sha256(out)
    write_json(stage_root / sealed_name.replace(".json", "_manifest.json"), {sealed_name: digest})
    print(json.dumps(dict(selected=chosen["decoded"], final_score=chosen["final_score"],
                          neighbour_fraction=chosen["neighbour_fraction"],
                          guards=chosen["guards"], evidence=chosen["evidence"],
                          pool=chosen["selection_pool"]), indent=1), flush=True)
    return chosen


# --------------------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------------------
def _episode_row(episode, days):
    row = dict(
        crossing_session=str(days[episode["crossing"]]),
        confirmation_session=str(days[episode["confirmation"]]),
        entry_session=str(days[episode["entry_index"]]),
        entry_price=float(episode["entry"]),
        frozen_upper=float(episode["u"]), frozen_lower=float(episode["d"]),
        frozen_atr=float(episode["atr"]), trigger=float(episode["trigger"]),
        initial_stop=float(episode["initial_stop"]),
        band_stop=None if episode["band_stop"] is None else float(episode["band_stop"]),
        hold_sessions=int(episode["hold_sessions"]), peak=float(episode["peak"]),
        heated=bool(episode["heated"]),
    )
    if episode["exit_signal"] is not None and episode["exit_index"] is not None:
        row.update(exit_session=str(days[episode["exit_signal"]]),
                   exit_index=int(episode["exit_index"]),
                   execution_session=str(days[episode["exit_index"]]),
                   exit_price=float(episode["exit_price"]),
                   exit_reason={1: "stop", 3: "time"}.get(int(episode["exit_reason"]),
                                                          str(episode["exit_reason"])),
                   gross_return=float(episode["exit_price"] / episode["entry"] - 1.0),
                   net_return=float((episode["exit_price"] / episode["entry"])
                                    * (1.0 - 0.0005) / (1.0 + 0.0005) - 1.0))
    else:
        row.update(exit_session=None, exit_index=None, execution_session=None,
                   exit_price=None, exit_reason="open at evaluation end",
                   gross_return=None, net_return=None)
    return row


def _trade_stats(episodes):
    closed = [e for e in episodes if e["gross_return"] is not None]
    if not closed:
        return dict(n=0)
    returns = np.array([e["gross_return"] for e in closed], float)
    holds = np.array([e["hold_sessions"] for e in closed], float)
    return dict(n=len(closed), win_rate=float((returns > 0).mean()),
                mean_gross=float(returns.mean()), median_gross=float(np.median(returns)),
                mean_win=float(returns[returns > 0].mean()) if (returns > 0).any() else None,
                mean_loss=float(returns[returns <= 0].mean()) if (returns <= 0).any() else None,
                mean_hold=float(holds.mean()), median_hold=float(np.median(holds)),
                max_hold=int(holds.max()), min_hold=int(holds.min()),
                total_gross=float((1 + returns).prod() - 1),
                mean_mfe=float(np.mean([e["mfe"] for e in closed])),
                mean_mae=float(np.mean([e["mae"] for e in closed])),
                time_exits=int(sum(e["exit_reason"] == "time" for e in closed)),
                stop_exits=int(sum(e["exit_reason"] == "stop" for e in closed)))


def build_evidence(features, parameters, periods, start, cost=5.0):
    """Compute a rich evidence record for one parameter vector over named periods."""
    prepared = rl.prepare(features, parameters)
    sim = rl.simulate(features, prepared, start=start, cost_bp=cost, trace=True)
    bh = rl.buy_hold(features, start, cost_bp=cost)
    days = features.days
    results = {}
    for name, (s, e) in periods.items():
        rule = rl.stats(sim["nav"], sim["weight"], s, e)
        buy = rl.stats(bh["nav"], bh["weight"], s, e)
        blocks = []
        for b0, b1 in rl.block_bounds(s, e, 3):
            rs = rl.stats(sim["nav"], sim["weight"], b0, b1)
            bs = rl.stats(bh["nav"], bh["weight"], b0, b1)
            blocks.append(dict(start=str(days[b0]), end=str(days[b1 - 1]), rule=rs, buyhold=bs,
                               utility=rl.utility(rs, bs)))
        results[name] = dict(rule=rule, buyhold=buy, blocks=blocks,
                             utility=rl.utility(rule, buy),
                             start=str(days[s]), end=str(days[e - 1]))
    years = {}
    for year in range(int(str(days[start])[:4]), int(str(days[-1])[:4]) + 1):
        mask = (days >= np.datetime64(f"{year}-01-01")) & (days <= np.datetime64(f"{year}-12-31"))
        idx = np.flatnonzero(mask)
        if len(idx) < 20 or int(idx[0]) <= start:
            continue
        s, e = int(idx[0]), int(idx[-1]) + 1
        years[year] = dict(rule=rl.stats(sim["nav"], sim["weight"], s, e),
                           buyhold=rl.stats(bh["nav"], bh["weight"], s, e))
    episodes = []
    for episode in sim["episodes"]:
        row = _episode_row(episode, days)
        fill = int(episode["entry_index"])
        last = int(episode["exit_index"]) if episode["exit_index"] is not None else len(days) - 1
        window = slice(fill, last + 1)
        row["mfe"] = float(features.high[window].max() / episode["entry"] - 1.0)
        row["mae"] = float(features.low[window].min() / episode["entry"] - 1.0)
        episodes.append(row)
    ledger = pd.DataFrame({
        "date": days.astype("datetime64[D]").astype(str),
        "open": features.open, "high": features.high, "low": features.low,
        "close": features.close, "volume": features.volume,
        "volume_median_ref": prepared["volmed"],
        "volume_ratio": features.volume / np.where(
            np.isfinite(prepared["volmed"]) & (prepared["volmed"] > 0),
            prepared["volmed"], np.nan),
        "range_lookback": prepared["L"], "range_upper": prepared["upper"],
        "range_lower": prepared["lower"], "range_width_log": prepared["width"],
        "range_drift": prepared["drift"], "short_long_vol_ratio": prepared["vol_ratio"],
        "trigger": prepared["boundary"], "atr": prepared["atr"],
        "cross": prepared["cross"].astype(int), "state": sim["state"],
        "trigger_level": sim["level"], "entry_price": sim["entry"], "stop": sim["stop"],
        "initial_stop": sim["stop_initial"], "band_stop": sim["stop_band"],
        "trail_stop": sim["stop_trail"], "peak": sim["peak"],
        "drawdown_from_peak": sim["drawdown"], "heated": sim["heat"],
        "hold_sessions": sim["hold"], "exit_reason": sim["reason"],
        "nav": sim["nav"], "weight": sim["weight"], "buyhold_nav": bh["nav"],
    })
    trace = dict(nav=sim["nav"], weight=sim["weight"], state=sim["state"], reason=sim["reason"],
                 stop=sim["stop"], stop_initial=sim["stop_initial"], stop_band=sim["stop_band"],
                 stop_trail=sim["stop_trail"], level=sim["level"], entry=sim["entry"],
                 peak=sim["peak"], drawdown=sim["drawdown"], heat=sim["heat"], hold=sim["hold"],
                 L=prepared["L"], upper=prepared["upper"], lower=prepared["lower"],
                 width=prepared["width"], drift=prepared["drift"],
                 vol_ratio=prepared["vol_ratio"], boundary=prepared["boundary"],
                 atr=prepared["atr"], volmed=prepared["volmed"], cross=prepared["cross"],
                 valid=prepared["valid"], buyhold_nav=bh["nav"])
    return dict(sim=sim, prepared=prepared, results=results, years=years, episodes=episodes,
                ledger=ledger, trace=trace)


def evaluate_main():
    verify_manifest(VAR / "inputs", "manifest.json")
    verify_manifest(VAR / "fit", "manifest.json")
    selection = read_json(VAR / "selection.json")
    verify_manifest(VAR, "selection_manifest.json")
    chosen = selection["chosen"]
    p = mapped_parameters(chosen["parameter_vector"])
    features = load_features(VAR / "inputs" / FULL_FEATURE_FILE)
    is_idx = int(np.flatnonzero(features.days <= np.datetime64(IS_END))[-1])
    oos_idx = int(np.flatnonzero(features.days >= np.datetime64(OOS_START))[0])
    periods = {"IS": (WARMUP, is_idx + 1), "OOS": (oos_idx, len(features.days)),
               "FULL": (WARMUP, len(features.days))}
    evidence = build_evidence(features, p, periods, WARMUP)
    # friction and delay stress
    friction_rows = []
    for cost, delay in ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1)):
        prepared = rl.prepare(features, p)
        sim = rl.simulate(features, prepared, start=WARMUP, cost_bp=cost, delay=delay)
        bh = rl.buy_hold(features, WARMUP, cost_bp=cost)
        row = dict(cost_bp=cost, delay=delay)
        for name, (s, e) in (("IS", periods["IS"]), ("OOS", periods["OOS"])):
            row[name] = dict(rule=rl.stats(sim["nav"], sim["weight"], s, e),
                             buyhold=rl.stats(bh["nav"], bh["weight"], s, e))
        friction_rows.append(row)
    # sealed fit equality check on the IS slice
    sealed = chosen["scenarios"][0]["rule"]
    for key in ("cagr", "sharpe", "maxdd", "exposure"):
        actual = evidence["results"]["IS"]["rule"][key]
        if abs(actual - sealed[key]) > 1e-8:
            raise AssertionError(f"IS {key} mismatch between full run ({actual}) and sealed fit "
                                 f"({sealed[key]})")
    trade_stats = _trade_stats(evidence["episodes"])
    work = VAR / "evaluation"
    work.mkdir(parents=True, exist_ok=True)
    evidence["ledger"].to_csv(work / "daily-ledger.csv", index=False, float_format="%.6f")
    evidence["ledger"].loc[evidence["ledger"]["date"] >= "2022-01-01"].to_csv(
        work / "daily-ledger-2022.csv", index=False, float_format="%.6f")
    pd.DataFrame(evidence["episodes"]).to_csv(work / "episodes.csv", index=False)
    save_trace(evidence, work / "trace.npz", features)
    payload = dict(
        identity=IDENTITY,
        selection_sha256=sha256(VAR / "selection.json"),
        selected=chosen["decoded"], parameter_vector=p.tolist(),
        periods=evidence["results"], years=evidence["years"], frictions=friction_rows,
        episodes=evidence["episodes"], trade_stats=trade_stats,
        n_episodes=len(evidence["episodes"]),
        first_session=str(features.days[0]), last_session=str(features.days[-1]),
        warmup_sessions=WARMUP, fit_window=chosen["fit_window"],
        is_equality_check="full-history IS statistics equal the sealed fit within 1e-8",
        limitations=[
            "The 2023+ interval was inspected in prior GLD work and in the operator's review; "
            "this is a chronological development retest, not an untouched holdout.",
            "Close-based stop decisions can gap; cash yield is zero; costs are per traded side.",
            "One US-listed gold ETF on a provider-vintage audited history; no historical universe "
            "or publication-vintage certification.",
        ],
    )
    write_json(work / "evaluation.json", payload)
    manifest(work, "manifest.json", [work / "evaluation.json", work / "daily-ledger.csv",
                                     work / "daily-ledger-2022.csv", work / "episodes.csv",
                                     work / "trace.npz"])
    print(json.dumps(dict(IS=payload["periods"]["IS"]["rule"],
                          OOS=payload["periods"]["OOS"]["rule"],
                          trade_stats=trade_stats), indent=1), flush=True)
    return payload


def save_trace(evidence, path, features):
    trace = dict(evidence["trace"])
    trace.update(days=features.days, close=features.close, open=features.open,
                 high=features.high, low=features.low, volume=features.volume)
    np.savez_compressed(path, **trace)


def evaluate_validation():
    verify_manifest(VAR / "inputs", "manifest.json")
    root = VAR / "validation"
    verify_manifest(root / "fit", "manifest.json")
    verify_manifest(root, "selection_manifest.json")
    selection = read_json(root / "selection.json")
    chosen = selection["chosen"]
    p = mapped_parameters(chosen["parameter_vector"])
    features = load_features(VAR / "inputs" / FULL_FEATURE_FILE)
    fit_end_idx = int(np.flatnonzero(features.days <= np.datetime64(VALIDATION_FIT_END))[-1])
    oos_start = int(np.flatnonzero(features.days >= np.datetime64(VALIDATION_OOS_START))[0])
    oos_end = int(np.flatnonzero(features.days <= np.datetime64(VALIDATION_OOS_END))[-1]) + 1
    periods = {"FIT": (WARMUP, fit_end_idx + 1), "PSEUDO_OOS": (oos_start, oos_end)}
    evidence = build_evidence(features, p, periods, WARMUP)
    sealed = chosen["scenarios"][0]["rule"]
    for key in ("cagr", "sharpe", "maxdd", "exposure"):
        actual = evidence["results"]["FIT"]["rule"][key]
        if abs(actual - sealed[key]) > 1e-8:
            raise AssertionError(f"validation FIT {key} mismatch: {actual} vs {sealed[key]}")
    payload = dict(identity=f"{IDENTITY}-validation",
                   selection_sha256=sha256(root / "selection.json"),
                   selected=chosen["decoded"], parameter_vector=p.tolist(),
                   periods=evidence["results"], years=evidence["years"],
                   episodes=evidence["episodes"],
                   trade_stats=_trade_stats(evidence["episodes"]),
                   fit_window=chosen["fit_window"], limits=[VALIDATION_OOS_START, VALIDATION_OOS_END])
    work = root / "evaluation"
    work.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(evidence["episodes"]).to_csv(work / "episodes.csv", index=False)
    write_json(work / "evaluation.json", payload)
    manifest(work, "manifest.json", [work / "evaluation.json", work / "episodes.csv"])
    print(json.dumps(dict(FIT=payload["periods"]["FIT"]["rule"],
                          PSEUDO_OOS=payload["periods"]["PSEUDO_OOS"]["rule"],
                          trade_stats=payload["trade_stats"]), indent=1), flush=True)
    return payload


# --------------------------------------------------------------------------------------
# Stages
# --------------------------------------------------------------------------------------
def prepare():
    VAR.mkdir(parents=True, exist_ok=True)
    (VAR / "inputs").mkdir(exist_ok=True)
    data, provenance = load_pinned_gld()
    np.savez_compressed(VAR / "inputs" / "gld-audited.npz", **data)
    features = rl.Features.build(data, SPEC)
    export_features(features, VAR / "inputs" / FULL_FEATURE_FILE)
    is_features = features_until(features, IS_END)
    export_features(is_features, VAR / "inputs" / FIT_FEATURE_FILE)
    is_idx = len(is_features.days) - 1
    oos_idx = is_idx + 1
    protocol = {
        "identity": IDENTITY,
        "authority": "Research only; no monitoring, promotion, funding or broker action.",
        "question": QUESTION_TEXT,
        "operator_direction": DIRECTION_TEXT,
        "data": {
            "source": "Pinned published audited GLD continuous history reused from the frozen "
                      "range-breakout v2 study input and hash-verified against its manifest.",
            "asset_sha256": provenance["asset_sha256"],
            "governance_batch": provenance["batch"],
            "governance_root": provenance["root"],
            "through": provenance["through"],
            "basis": ("Adjusted OHLC for signal/returns; audited raw volume for traded activity. "
                      "Adjusted and raw GLD closes are identical. No filling, splicing or online prices."),
            "sessions": int(len(features.days)),
            "first_session": str(features.days[0]),
            "last_session": str(features.days[-1]),
        },
        "chronology": {
            "warmup_sessions": WARMUP,
            "fit_start": str(is_features.days[WARMUP]),
            "fit_end": IS_END,
            "fit_is_sessions": int(len(is_features.days) - WARMUP),
            "oos_start": OOS_START,
            "oos_first_session": str(features.days[oos_idx]),
            "oos_end": str(features.days[-1]),
            "rule": "Fit and selection read only sessions through fit_end. OOS metrics start at the "
                    "first session on/after oos_start and continue the same account and state.",
        },
        "parameterization": {
            "structural_domain": SPEC.name,
            "structural_domain_note": LONG_DOMAIN_NOTE,
            "vector_length": len(SPEC.parameters),
            "parameters": [dict(name=name, low=float(low), high=float(high), integral=bool(integ))
                           for name, low, high, integ in SPEC.parameters],
            "structural_choices": {
                "candidate_windows": list(SPEC.windows),
                "tail_candidates": list(SPEC.tails),
                "atr_candidates": list(SPEC.atr_periods),
                "volume_reference_candidates": list(SPEC.vol_periods),
                "time_limit_candidates": list(SPEC.time_limits),
                "reentry_wait_candidates": list(SPEC.reentry_waits),
                "range_selection": "longest qualifying lookback wins",
                "decision_clock": "completed close",
                "execution": "next session open; one whole-session delay in stress cases",
                "accounting": "fractional units, 100% target, zero cash yield, cost per side",
                "continuation_reentry": ("Optional fitted re-engagement of a closed breakout "
                                          "trend: a close above the previous episode peak plus "
                                          "reentry_buffer_atr*ATR within reentry_wait_sessions "
                                          "re-enters at the next open. It is disabled when the "
                                          "fitted switch is zero."),
            },
        },
        "objective": {
            "utility": ("45% clipped scaled excess CAGR, 40% clipped excess Sharpe, 15% clipped "
                        "excess regularized Calmar versus a matched-cost buy-and-hold of the same "
                        "window; CAGR scaled by 10pp and clipped to +/-3; Sharpe/Calmar clipped to +/-3."),
            "robust": "0.5*full utility + 0.5*median of three contiguous IS block utilities - 0.25*std(blocks)",
            "fit_fitness": ("robust - 0.10*scarcity - 0.30*low-exposure; scarcity=max(0,10-closed)/10; "
                            "low-exposure=max(0,0.20-average exposure)/0.20"),
            "note": "The objective contains no post-2022 observation.",
        },
        "search": {
            "algorithm": "rand/1/bin differential evolution, F=0.7, CR=0.9",
            "seeds": DE_SEEDS, "population_multiplier": DE_POPSIZE,
            "generations": DE_GENERATIONS,
            "evaluations_per_seed": DE_POPSIZE * len(SPEC.parameters) * (DE_GENERATIONS + 1),
            "screening": "5bp per side, next-open fills, IS window only",
        },
        "selection": {
            "finalists": TOP_K,
            "frictions": [dict(cost_bp=c, delay=d) for c, d in FRICTIONS],
            "final_score": "minimum fitness over the friction set",
            "evidence": (">=10 closed IS episodes, average IS exposure >=20% at 5bp and at least one "
                         "closed episode in each of the three contiguous IS blocks"),
            "guards": ("at every friction: IS CAGR >= matched buy-hold CAGR - 2pp and IS maximum "
                       "drawdown no worse than matched buy-hold drawdown - 5pp"),
            "stability": ("Among evidence/guard-passing finalists within 0.05 of the best final_score, "
                          "compute the fraction of +/-1-selection-step parameter neighbours whose IS "
                          "fitness is within 0.15 of the candidate; choose the highest, then lower "
                          "annual turnover, then higher exposure, then lexicographic parameters."),
            "fallback": "If no candidate passes the guards the best evidence candidate is retained and "
                        "marked descriptive.",
            "seal": "selection.json is written and hashed before any 2023+ evaluation.",
        },
        "validation": {
            "purpose": ("Second pre-2023 chronology: fit 2005-2015, select, then evaluate 2016-2022. "
                        "Untouched pseudo-OOS for the procedure; never reads 2023+."),
            "fit_end": VALIDATION_FIT_END,
            "pseudo_oos": [VALIDATION_OOS_START, VALIDATION_OOS_END],
            "search": dict(seeds=VALIDATION_SEEDS, population_multiplier=VALIDATION_POPSIZE,
                           generations=VALIDATION_GENERATIONS),
        },
        "limitations": [
            "The 2023+ interval has already been inspected in earlier GLD work and in the operator's "
            "review; it is a chronological development retest, not an untouched holdout.",
            "The lifecycle structure was motivated by the operator's critique of the earlier attempt "
            "(confirmation lag, tight stop, five-session exit). Structure choices were not selected "
            "using post-2022 performance, but 2023 is not unbiased evidence for them.",
            "A fitted rule can overfit 2005-2022 gold; block stability, friction stress, parameter-"
            "neighbour stability and a 2016-2022 pseudo-OOS validation are reported.",
            "One US-listed gold ETF on a current-vintage provider history; no historical universe or "
            "publication-vintage certification. Cash earns zero; close-based stops can gap.",
        ],
    }
    write_json(VAR / "protocol.json", protocol)
    write_json(VAR / "provenance.json", provenance)
    write_json(VAR / "bounds.json", [
        dict(name=name, low=low, high=high, integral=bool(integ))
        for name, low, high, integ in SPEC.parameters])
    anchors = warm_start_anchors()
    write_json(VAR / "inputs" / "anchors.json", anchors)
    if anchors:
        protocol = read_json(VAR / "protocol.json")
        protocol["search"]["warm_start"] = (
            f"{len(anchors)} anchor vector(s) from the earlier 24-parameter IS-only calibration are "
            "inserted into the initial population with the new re-entry switches disabled. They "
            "contain no post-2022 information.")
        write_json(VAR / "protocol.json", protocol)
    source_dir = VAR / "source"
    source_dir.mkdir(exist_ok=True)
    shutil.copyfile(SOURCE_MODULE, source_dir / SOURCE_MODULE.name)
    shutil.copyfile(SOURCE_RUNNER, source_dir / SOURCE_RUNNER.name)
    write_json(VAR / "source_hashes.json",
               {str(SOURCE_MODULE): sha256(SOURCE_MODULE),
                str(SOURCE_RUNNER): sha256(SOURCE_RUNNER)})
    manifest(VAR / "inputs", "manifest.json",
             [VAR / "inputs" / "gld-audited.npz", VAR / "inputs" / FIT_FEATURE_FILE,
              VAR / "inputs" / FULL_FEATURE_FILE, VAR / "inputs" / "anchors.json"])
    manifest(VAR, "input_manifest.json",
             [VAR / "inputs" / "gld-audited.npz", VAR / "inputs" / FIT_FEATURE_FILE,
              VAR / "inputs" / FULL_FEATURE_FILE, VAR / "inputs" / "anchors.json",
              VAR / "protocol.json", VAR / "bounds.json", VAR / "provenance.json",
              VAR / "source_hashes.json"])
    print(json.dumps(dict(asset=provenance["asset_sha256"], sessions=len(features.days),
                          fit_start=str(is_features.days[WARMUP]), fit_end=IS_END,
                          oos_first_session=str(features.days[oos_idx]),
                          last_session=str(features.days[-1])), indent=1))
    return protocol


def fit():
    return run_fit(VAR, VAR / "inputs" / FIT_FEATURE_FILE, WARMUP,
                   len(load_features(VAR / "inputs" / FIT_FEATURE_FILE).days),
                   DE_SEEDS, DE_POPSIZE, DE_GENERATIONS)


def select():
    return run_select(VAR, VAR / "inputs" / FIT_FEATURE_FILE, WARMUP,
                      len(load_features(VAR / "inputs" / FIT_FEATURE_FILE).days))


def evaluate():
    return evaluate_main()


def validate():
    root = VAR / "validation"
    root.mkdir(parents=True, exist_ok=True)
    full = load_features(VAR / "inputs" / FULL_FEATURE_FILE)
    fit_features = features_until(full, VALIDATION_FIT_END)
    export_features(fit_features, root / "fit-features.npz")
    start, end = WARMUP, len(fit_features.days)
    print(f"validation fit window {fit_features.days[start]} .. {fit_features.days[end - 1]}",
          flush=True)
    run_fit(root, root / "fit-features.npz", start, end, VALIDATION_SEEDS,
            VALIDATION_POPSIZE, VALIDATION_GENERATIONS, use_anchors=False)
    run_select(root, root / "fit-features.npz", start, end)
    evaluate_validation()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "fit", "select", "evaluate", "validate"])
    args = parser.parse_args()
    globals()[args.stage]()
