"""Two-horizon GLD lifecycle across the 52-ETF pool, and asset-selection tests.

Stages
------
prepare   : verify the pinned 52-asset panel and per-asset audited histories, write
            the predeclared protocol (domains, fit window, selection rules, frictions).
fit       : per-ETF fit/selection of the short-range and long-range lifecycle signals
            on pre-2023 sessions only, then causal signals for the portfolio window.
portfolio : replay the asset-selection rules and benchmarks through the same shared
            application accounting engine used by the frozen FR25 SOTA paths.
report    : (separate script) HTML report.

Research only; no monitoring, promotion, funding or broker action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
from collections import Counter
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
VAR = ROOT / "var" / "research" / "gld-lifecycle-pool-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-pool-20261019-v1"
V2 = ROOT / "var" / "research" / "range-breakout-20261018-v2"
PANEL = V2 / "pool" / "inputs.npz"
RECIPE = V2 / "pool" / "recipe.json"
ASSETS = V2 / "assets"
SHORT_STUDY = ROOT / "var" / "research" / "gld-lifecycle-20261019-v1"
LONG_STUDY = ROOT / "var" / "research" / "gld-longrange-lifecycle-20261019-v1"
IS_END = "2022-12-30"
OOS_START = "2023-01-03"
WARMUP = 252
FRICTIONS = ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1))
N_RANDOM = 200
N_ANCHOR_MUTATIONS = 40
TOP_PER_DOMAIN = 15
MIN_IS_SESSIONS = 500
EVIDENCE_MIN_TRADES = 5
EVIDENCE_MIN_EXPOSURE = 0.05
TREND_GATE = 126
REBALANCE_THRESHOLD = 0.10
WORKERS = min(14, max(2, (mp.cpu_count() or 4) - 1))
# BIL is a Treasury-bill money-market fund, not a trend asset; it is kept in the
# panel and benchmarks but excluded from lifecycle selection so the sleeve cannot
# become a cash proxy (the same BIL-dominance issue flagged in the earlier study).
EXCLUDE_FROM_SELECTION = {"BIL"}

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(V2))
from systematic_trading.research import range_lifecycle as rl  # noqa: E402

ASSET_CLASS = {
    # US equities and sector/thematic equity ETFs
    **{s: "US equities" for s in ("SPY", "IWM", "MDY", "XLB", "XLC", "XLE", "XLI",
                                  "XLK", "XLP", "XLU", "XLV", "XLY", "SOXX", "IBB",
                                  "ITA")},
    # international equities
    **{s: "International equities" for s in ("EEM", "EFA", "EWA", "EWC", "EWG", "EWH",
                                            "EWJ", "EWT", "EWU", "EWY", "INDA", "MCHI",
                                            "VGK")},
    # fixed income / credit
    **{s: "Fixed income" for s in ("AGG", "BIL", "EMB", "HYG", "IBND", "IEF", "IGOV",
                                  "LQD", "MBB", "SHY", "TIP", "LEMB", "TLT")},
    # commodities and precious metals
    **{s: "Commodities" for s in ("CORN", "CPER", "DBA", "DBB", "DBC", "GLD", "PPLT",
                                 "SLV", "USO", "WEAT")},
    "IAT": "Real assets",
}


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


def load_panel():
    panel = dict(np.load(PANEL, allow_pickle=True))
    return panel


def load_recipe():
    return read_json(RECIPE)


def list_assets(panel):
    return [str(s) for s in panel["symbols"]]


def load_asset(symbol):
    path = ASSETS / f"{symbol}.npz"
    d = np.load(path, allow_pickle=True)
    return {k: np.asarray(d[k]) for k in ("open", "high", "low", "close", "volume", "days")}


def panel_days(panel):
    return pd.to_datetime(panel["days"]).to_numpy()


def is_window(features):
    days = features.days
    end = int(np.flatnonzero(days <= np.datetime64(IS_END))[-1]) + 1
    start = min(WARMUP, max(1, end - 300))
    oos = int(np.flatnonzero(days >= np.datetime64(OOS_START))[0]) if (days >= np.datetime64(OOS_START)).any() else None
    return start, end, oos


def gld_anchor_vectors():
    short = list(read_json(SHORT_STUDY / "selection.json")["chosen"]["parameter_vector"])
    if len(short) == len(rl.SHORT_SPEC.parameters) - 3:
        short = short + [0, 0.0, 0]
    long = list(read_json(LONG_STUDY / "selection.json")["chosen"]["parameter_vector"])
    return {"short": rl.SHORT_SPEC.canonical(short), "long": rl.LONG_SPEC.canonical(long)}


def candidate_vectors(spec, anchor, rng):
    bounds = spec.bounds
    low, high = bounds[:, 0], bounds[:, 1]
    random = rng.uniform(low, high, (N_RANDOM, len(spec.parameters)))
    mutated = [anchor]
    for _ in range(N_ANCHOR_MUTATIONS):
        step = rng.normal(0.0, 0.08, len(spec.parameters)) * (high - low)
        mutated.append(np.clip(anchor + step, low, high))
    vectors = np.vstack([random, np.asarray(mutated)])
    return np.array([spec.canonical(row) for row in vectors])


def fit_one_domain(features, spec, anchor, rng):
    start, end, _ = is_window(features)
    n_is = end - start
    if n_is < MIN_IS_SESSIONS:
        return dict(parameters=anchor, fallback_transfer=True, evidence=False,
                    fitness=float(rl.evaluate(features, anchor, start, end, cost_bp=5.0)["fitness"]),
                    is_metrics=rl.evaluate(features, anchor, start, end, cost_bp=5.0)["full"])
    vectors = candidate_vectors(spec, anchor, rng)
    scored = []
    for vector in vectors:
        ev = rl.evaluate(features, vector, start, end, cost_bp=5.0)
        scored.append((ev["fitness"], vector, ev["n_closed"], ev["full"]["exposure"]))
    scored.sort(key=lambda row: -row[0])
    shortlist = scored[:TOP_PER_DOMAIN]
    finals = []
    for _, vector, _, _ in shortlist:
        scores = []
        n_closed = 0
        exposure = 0.0
        for cost, delay in FRICTIONS:
            ev = rl.evaluate(features, vector, start, end, cost_bp=cost, delay=delay)
            scores.append(ev["fitness"])
            if (cost, delay) == (5.0, 0):
                n_closed = ev["n_closed"]
                exposure = ev["full"]["exposure"]
        finals.append(dict(parameter_vector=vector.tolist(),
                           final_score=float(min(scores)),
                           evidence=bool(n_closed >= EVIDENCE_MIN_TRADES and exposure >= EVIDENCE_MIN_EXPOSURE),
                           n_closed=int(n_closed), exposure=float(exposure)))
    evidence = [row for row in finals if row["evidence"]]
    pool = evidence if evidence else finals
    chosen = max(pool, key=lambda row: row["final_score"])
    vector = spec.canonical(chosen["parameter_vector"])
    ev = rl.evaluate(features, vector, start, end, cost_bp=5.0)
    return dict(parameters=vector, fallback_transfer=False, evidence=bool(evidence),
                fitness=float(chosen["final_score"]), n_closed=int(chosen["n_closed"]),
                exposure=float(chosen["exposure"]), is_metrics=ev["full"],
                is_buyhold=ev["buyhold"])


def _score_signals(features, spec, params, panel_days):
    """Causal sleeve state and extension score, mapped onto the portfolio panel dates."""
    prepared = rl.prepare(features, params)
    sim = rl.simulate(features, prepared, start=WARMUP, cost_bp=5.0, trace=True)
    n = len(features.days)
    active = np.zeros(n, bool)
    score = np.zeros(n)
    level = sim["level"]
    atr = prepared["atr"]
    for t in range(n):
        state = int(sim["state"][t])
        active[t] = state == rl.STATE_LONG
        if active[t] and np.isfinite(level[t]) and np.isfinite(atr[t]) and atr[t] > 0:
            extension = (features.close[t] - level[t]) / atr[t]
            score[t] = max(0.0, float(extension))
    lookup = {str(np.datetime64(d, "D")): i for i, d in enumerate(features.days)}
    panel_active = np.zeros(len(panel_days), bool)
    panel_score = np.zeros(len(panel_days))
    for i, day in enumerate(panel_days):
        j = lookup.get(str(np.datetime64(day, "D")))
        if j is not None:
            panel_active[i] = active[j]
            panel_score[i] = score[j]
    days = features.days
    start, end, oos = is_window(features)
    oos_idx = int(np.flatnonzero(days >= np.datetime64(OOS_START))[0]) if oos is not None else None
    is_stats = rl.stats(sim["nav"], sim["weight"], start, end)
    oos_stats = (rl.stats(sim["nav"], sim["weight"], oos_idx, len(days))
                 if oos_idx is not None else None)
    return dict(active=panel_active, score=panel_score, nav=sim["nav"], weight=sim["weight"],
                is_stats=is_stats, oos_stats=oos_stats)


def fit_asset(symbol):
    data = load_asset(symbol)
    rng = np.random.default_rng(10_000 + sum(ord(c) for c in symbol))
    anchors = gld_anchor_vectors()
    panel = load_panel()
    pdays = panel_days(panel)
    result = dict(symbol=symbol, class_=ASSET_CLASS.get(symbol, "Other"),
                  first_session=str(np.datetime64(data["days"][0], "D")),
                  last_session=str(np.datetime64(data["days"][-1], "D")))
    arrays = {}
    for kind, spec, anchor in (("short", rl.SHORT_SPEC, anchors["short"]),
                               ("long", rl.LONG_SPEC, anchors["long"])):
        features = rl.Features.build(data, spec)
        fit = fit_one_domain(features, spec, anchor, rng)
        signals = _score_signals(features, spec, fit["parameters"], pdays)
        result[kind] = dict(
            parameters=fit["parameters"].tolist(), decoded=spec.describe(fit["parameters"]),
            fallback_transfer=fit["fallback_transfer"], evidence=fit["evidence"],
            fitness=fit["fitness"], n_closed=fit.get("n_closed"),
            is_metrics=fit["is_metrics"], is_buyhold=fit["is_buyhold"],
            oos_stats=signals["oos_stats"],
        )
        arrays[f"{kind}_active"] = signals["active"].astype(np.int8)
        arrays[f"{kind}_score"] = signals["score"].astype(np.float32)
    return result, arrays


def _signals_for_asset(symbol):
    per_asset = read_json(VAR / "fit" / "per-asset.json")
    entry = per_asset[symbol]
    data = load_asset(symbol)
    panel = load_panel()
    pdays = panel_days(panel)
    arrays = {}
    for kind, spec in (("short", rl.SHORT_SPEC), ("long", rl.LONG_SPEC)):
        params = spec.canonical(entry[kind]["parameters"])
        features = rl.Features.build(data, spec)
        signals = _score_signals(features, spec, params, pdays)
        arrays[f"{kind}_active"] = signals["active"].astype(np.int8)
        arrays[f"{kind}_score"] = signals["score"].astype(np.float32)
    return symbol, arrays


def signals():
    per_asset = read_json(VAR / "fit" / "per-asset.json")
    symbols = sorted(per_asset)
    arrays = {}
    with mp.Pool(WORKERS) as pool:
        for i, (symbol, asset_arrays) in enumerate(pool.imap_unordered(_signals_for_asset, symbols)):
            for key, value in asset_arrays.items():
                arrays.setdefault(key, {})[symbol] = value
            print(f"[{i + 1}/{len(symbols)}] {symbol} signals", flush=True)
    out = {}
    for key, by_symbol in arrays.items():
        out[key] = np.vstack([by_symbol[s] for s in symbols])
    out["symbols"] = np.array(symbols)
    np.savez_compressed(VAR / "fit" / "panel-signals.npz", **out)
    write_json(VAR / "fit" / "signal_manifest.json",
               {"panel-signals.npz": sha256(VAR / "fit" / "panel-signals.npz")})
    print(json.dumps({"assets": len(symbols),
                      "mean_short_active": float(out["short_active"].mean()),
                      "mean_long_active": float(out["long_active"].mean()),
                      "assets_any_short": int((out["short_active"].sum(axis=0) > 0).sum()),
                      "assets_any_long": int((out["long_active"].sum(axis=0) > 0).sum())}, indent=1))


def prepare():
    VAR.mkdir(parents=True, exist_ok=True)
    (VAR / "inputs").mkdir(exist_ok=True)
    panel = load_panel()
    assets = list_assets(panel)
    # Identity checks: panel closes must equal each per-asset audited close on common dates.
    pdays = [str(np.datetime64(d, "D")) for d in panel["days"]]
    panel_index = {d: i for i, d in enumerate(pdays)}
    max_diff = 0.0
    for symbol in assets:
        data = load_asset(symbol)
        days = [str(np.datetime64(d, "D")) for d in data["days"]]
        for i, day in enumerate(days):
            j = panel_index.get(day)
            if j is not None:
                max_diff = max(max_diff, abs(float(data["close"][i]) - float(panel["close"][j, assets.index(symbol)])))
    protocol = dict(
        identity="gld-lifecycle-pool-20261019-v1",
        authority="Research only; no monitoring, promotion, funding or broker action.",
        question=("Do the sealed short-range and long-range GLD lifecycle signals generalise "
                  "across the 52-ETF audited pool, and does a two-horizon lifecycle "
                  "asset-selection rule beat the current FR25 SOTA after costs?"),
        data=dict(
            panel=str(PANEL), panel_sha256=sha256(PANEL), recipe_sha256=sha256(RECIPE),
            assets_dir=str(ASSETS), assets=[a for a in assets],
            asset_class=ASSET_CLASS,
            panel_first=pdays[0], panel_last=pdays[-1], panel_sessions=len(pdays),
            per_asset_close_max_abs_diff=max_diff,
            basis=("Pinned published audited adjusted OHLC and raw volume; the 52-asset panel "
                   "and the FR25 target weights are the frozen v2 pool inputs repriced on the "
                   "same batch. No online prices, filling or splicing."),
        ),
        chronology=dict(warmup=WARMUP, fit_end=IS_END, oos_start=OOS_START,
                        oos_end=pdays[-1], oos_sessions=int(panel["days"].size - np.flatnonzero(panel["days"] >= OOS_START)[0])),
        methodology=dict(
            per_asset_fit=("Each ETF gets an independent pre-2023 fit in each structural domain: "
                           f"{N_RANDOM} random bounded vectors + the sealed GLD vector + "
                           f"{N_ANCHOR_MUTATIONS} anchor mutations, screened at 5bp; the top "
                           f"{TOP_PER_DOMAIN} replayed across 5/10/20bp and +1 session delay; "
                           "evidence requires >=5 closed IS episodes and >=5% exposure; the best "
                           "final score is sealed per ETF/domain."),
            transfer_fallback=("ETFs with fewer than 500 evaluable IS sessions use the sealed GLD "
                               "vector for that domain (no per-asset fit)."),
            signals=("Sleeve state and extension score ((close - frozen trigger)/ATR) are causal "
                     "daily outputs; the portfolio window uses only these pre-2023-fitted signals."),
            selection_rules=[
                "R1 lifecycle top-six: among ETFs with a short/long sleeve active at the month-end "
                "close, keep positive 126-session momentum, rank by combined extension score, take "
                "up to six, inverse-vol (63-session) weights, 45% cap, 98% budget, cash remainder.",
                "R2 lifecycle top-six without the 126-session momentum gate.",
                "R3 lifecycle allocation: all active ETFs, weight = combined sleeve exposure x "
                "inverse-vol, 45% cap, 98% budget.",
                "R4 lifecycle-gated momentum: among active ETFs, rank by 126-session momentum.",
                "Event controls: mandatory adoption on any held-name lifecycle exit or when the "
                "L1 target change including cash exceeds 0.10, plus monthly anchors.",
                "Tilt: 80% frozen FR25 targets + 20% lifecycle rule target, monthly rebalanced.",
            ],
            benchmarks=["frozen FR25 SOTA path", "frozen M1 momentum control path",
                        "frozen equal-weight pool", "URTH buy-and-hold", "BIL"],
            frictions=[dict(cost_bp=c, delay=d) for c, d in FRICTIONS],
            no_oos_tuning=("Rules, caps, weights and frictions are predeclared; 2023+ outcomes are "
                           "not used to choose a weight, threshold or rule."),
        ),
        limitations=[
            "Per-ETF fits use a deliberately smaller search budget than the GLD deep dives; the "
            "purpose is breadth across the pool, not an optimum per ETF.",
            "The 2023-2026 interval has been inspected in prior research; all OOS results are "
            "development retests, not untouched holdouts.",
            "FR25 and M1 benchmark paths are frozen replays of their own decisions on the same "
            "batch; the FR25 target-weight matrix was reproduced exactly by the shared engine.",
            "One current-vintage provider cohort; no historical universe or publication-vintage "
            "certification. Cash earns zero; close decisions fill at the next open.",
        ],
    )
    write_json(VAR / "protocol.json", protocol)
    np.savez_compressed(VAR / "inputs" / "panel-metadata.npz",
                        symbols=panel["symbols"], days=panel["days"])
    write_json(VAR / "assets.json", assets)
    manifest(VAR / "inputs", "manifest.json", [VAR / "inputs" / "panel-metadata.npz"])
    print(json.dumps(dict(assets=len(assets), panel_sessions=len(pdays),
                          close_max_abs_diff=max_diff, oos_sessions=protocol["chronology"]["oos_sessions"]),
                     indent=1))


def manifest(root, name, files):
    root = Path(root)
    write_json(root / name, {str(Path(f).relative_to(root)).replace("\\", "/"): sha256(f)
                             for f in files})


def fit():
    panel = load_panel()
    assets = list_assets(panel)
    work = VAR / "fit"
    work.mkdir(parents=True, exist_ok=True)
    results, arrays = {}, {}
    with mp.Pool(WORKERS) as pool:
        for i, (result, asset_arrays) in enumerate(pool.imap_unordered(fit_asset, assets)):
            results[result["symbol"]] = result
            for key, value in asset_arrays.items():
                arrays.setdefault(key, {})[result["symbol"]] = value
            print(f"[{i + 1}/{len(assets)}] {result['symbol']} fitted", flush=True)
    symbols = sorted(results)
    out = {}
    for key, by_symbol in arrays.items():
        out[key] = np.vstack([by_symbol[s] for s in symbols])
    out["symbols"] = np.array(symbols)
    np.savez_compressed(work / "panel-signals.npz", **out)
    write_json(work / "per-asset.json", results)
    for s in symbols:
        write_json(work / "assets" / f"{s}.json", results[s])
    write_json(work / "manifest.json", {"panel-signals.npz": sha256(work / "panel-signals.npz"),
                                        "per-asset.json": sha256(work / "per-asset.json")})
    print(json.dumps({"fitted": len(results),
                      "transfer_fallbacks": sum(1 for s in symbols
                                                for kind in ("short", "long")
                                                if results[s][kind]["fallback_transfer"]),
                      "short_evidence": sum(1 for s in symbols if results[s]["short"]["evidence"]),
                      "long_evidence": sum(1 for s in symbols if results[s]["long"]["evidence"])},
                     indent=1))


# --------------------------------------------------------------------------------------
# Portfolio rules and benchmarks
# --------------------------------------------------------------------------------------
def load_signals():
    d = np.load(VAR / "fit" / "panel-signals.npz", allow_pickle=True)
    symbols = [str(s) for s in d["symbols"]]
    return symbols, {k: d[k] for k in d.files if k != "symbols"}


def inverse_vol_weights(close, t, indices, guard=63):
    if len(indices) == 0:
        return np.array([])
    window = np.asarray(close[t - guard + 1:t + 1, indices], float)
    window = np.where(window > 0, window, np.nan)
    returns = np.diff(np.log(window), axis=0)
    vol = np.nanstd(returns, axis=0) * np.sqrt(252)
    fallback = np.nanmedian(vol[np.isfinite(vol) & (vol > 1e-6)]) if (vol > 1e-6).any() else 0.20
    vol = np.where(np.isfinite(vol) & (vol > 1e-6), vol, fallback)
    return 1.0 / vol


def cap_weights(raw, budget=0.98, cap=0.45):
    """Normalise to the budget, then enforce the per-name cap by redistributing."""
    raw = np.asarray(raw, float)
    if len(raw) == 0 or raw.sum() <= 1e-12:
        return np.zeros(len(raw))
    weights = raw / raw.sum() * budget
    for _ in range(50):
        over = weights > cap + 1e-12
        if not over.any():
            break
        weights[over] = cap
        free = ~over
        leftover = budget - weights[over].sum()
        if not free.any() or raw[free].sum() <= 1e-12 or leftover <= 1e-12:
            break
        weights[free] = raw[free] / raw[free].sum() * leftover
    return weights


def build_target_matrix(panel, signals, symbols, rule, gate=True):
    order = symbols
    close = panel["close"]
    n = close.shape[0]
    admitted = panel["admitted"]
    combined_weight = 0.5 * signals["short_active"] + 0.5 * signals["long_active"]
    combined_score = 0.5 * signals["short_score"] + 0.5 * signals["long_score"]
    mom = np.full((n, len(symbols)), np.nan)
    mom[TREND_GATE:] = close[TREND_GATE:] / close[:-TREND_GATE] - 1.0
    targets = np.zeros((n, len(symbols) + 1))
    for t in range(TREND_GATE, n):
        valid = admitted[t] & np.isfinite(close[t]) & (close[t] > 0) & (combined_weight[t] > 0)
        idx = np.flatnonzero(valid)
        idx = np.array([j for j in idx if order[j] not in EXCLUDE_FROM_SELECTION], dtype=int)
        if len(idx) == 0:
            continue
        if rule in ("top6", "top6_nogate", "gated_momentum"):
            if rule in ("top6", "gated_momentum") and gate:
                idx = idx[mom[t, idx] > 0]
            if len(idx) == 0:
                continue
            if rule == "gated_momentum":
                ranking = np.lexsort((-combined_score[t, idx], -mom[t, idx]))
            else:
                ranking = np.lexsort((-mom[t, idx], -combined_score[t, idx]))
            chosen = idx[ranking[:6]]
            raw = inverse_vol_weights(close, t, chosen)
            weights = cap_weights(raw)
            targets[t, chosen] = weights
        elif rule == "allocation":
            raw = inverse_vol_weights(close, t, idx) * combined_weight[t, idx]
            weights = cap_weights(raw)
            targets[t, idx] = weights
        else:
            raise ValueError(rule)
    return targets


def monthly_indices(panel):
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    initial = int(np.flatnonzero(np.array(days) <= "2022-12-30")[-1])
    indices = [initial]
    previous_month = days[initial][:7]
    for t in range(initial + 1, len(days)):
        month = days[t][:7]
        if month != previous_month and t - 1 > initial:
            indices.append(t - 1)
            previous_month = month
    return np.array(indices, dtype=int)


def event_indices(panel, targets, base_indices, sleeve_weight=None):
    base = set(int(t) for t in base_indices)
    indices = list(base_indices)
    adopted = np.zeros(targets.shape[1])
    last_adopt = -1
    for t in range(int(base_indices[0]), targets.shape[0] - 1):
        target = targets[t, :-1]
        if t in base:
            adopted = target.copy()
            last_adopt = t
            continue
        if last_adopt < 0:
            continue
        risk_exit = False
        if sleeve_weight is not None:
            held = np.flatnonzero(adopted > 0)
            risk_exit = bool(len(held) and np.any(sleeve_weight[t, held] <= 0))
        diff = float(np.abs(target - adopted).sum())
        if risk_exit or diff >= REBALANCE_THRESHOLD:
            indices.append(t)
            adopted = target.copy()
            last_adopt = t
    return np.array(sorted(set(int(t) for t in indices)), dtype=int)


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


def period_returns(nav, days, start, end):
    mask = (days >= np.datetime64(start)) & (days <= np.datetime64(end))
    idx = np.flatnonzero(mask)
    s, e = int(idx[0]), int(idx[-1]) + 1
    return nav[e - 1] / nav[s] - 1.0


def portfolio():
    sys.path.insert(0, str(V2))
    from run_range_breakout import Replay  # noqa: E402
    panel = load_panel()
    recipe = load_recipe()
    symbols, signals = load_signals()
    order = [str(s) for s in panel["symbols"]]
    signals = {k: np.column_stack([signals[k][symbols.index(s)] for s in order])
               for k in signals}
    days = panel_days(panel)
    base_indices = monthly_indices(panel)
    start = OOS_START
    replay = Replay(panel, recipe, start)
    fr25 = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    # Benchmark frozen NAV paths.
    benchmark_paths = {
        "FR25 SOTA": "FR25_c5d0", "M1 momentum control": "M1_monthly_c5d0",
        "Equal weight": "equal_weight_c5d0", "URTH": "URTH_c5d0", "BIL": "BIL_c5d0",
        "FR25 (10bp)": "FR25_c10d0", "FR25 (20bp)": "FR25_c20d0", "FR25 (+1 delay)": "FR25_c5d1",
    }
    benchmarks = {}
    for label, stem in benchmark_paths.items():
        d = np.load(V2 / "pool" / "paths" / f"{stem}.npz")
        benchmarks[label] = dict(nav=d["nav"], exposure=d["exposure"],
                                 metrics=metrics(d["nav"], d["exposure"]))
    sleeve_weight = 0.5 * signals["short_active"] + 0.5 * signals["long_active"]
    # Build rule targets and replay across frictions.
    rule_targets = {
        "R1 lifecycle top-six": ("top6", True),
        "R2 lifecycle top-six, no momentum gate": ("top6", False),
        "R3 lifecycle allocation": ("allocation", False),
        "R4 lifecycle-gated momentum": ("gated_momentum", True),
    }
    results, daily = {}, {}
    for label, (rule, gate) in rule_targets.items():
        targets = build_target_matrix(panel, signals, order, rule, gate)
        indices = event_indices(panel, targets, base_indices, sleeve_weight=sleeve_weight)
        for cost, delay in FRICTIONS:
            compact, _, fills = replay.run(targets, indices, cost, delay)
            key = f"{label} | {cost:g}bp d{delay}"
            results[key] = dict(rule=label, cost_bp=cost, delay=delay, fills=int(fills),
                                indices=int(len(indices)),
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            if cost == 5.0 and delay == 0:
                daily[label] = compact["nav"]
    # Monthly-only controls for the same rules.
    for label, (rule, gate) in rule_targets.items():
        targets = build_target_matrix(panel, signals, order, rule, gate)
        for cost, delay in ((5.0, 0), (10.0, 0)):
            compact, _, fills = replay.run(targets, base_indices, cost, delay)
            key = f"{label} monthly | {cost:g}bp d{delay}"
            results[key] = dict(rule=label + " monthly", cost_bp=cost, delay=delay,
                                fills=int(fills), indices=int(len(base_indices)),
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            if cost == 5.0 and delay == 0:
                daily[label + " monthly"] = compact["nav"]
    # Tilt: 80% FR25 + 20% lifecycle rule (event and monthly).
    for label, (rule, gate) in (("R1 lifecycle top-six", ("top6", True)),
                                ("R3 lifecycle allocation", ("allocation", False))):
        sleeve = build_target_matrix(panel, signals, order, rule, gate)
        blended = 0.8 * fr25 + 0.2 * sleeve
        for indices, tag in ((event_indices(panel, sleeve, base_indices,
                                            sleeve_weight=sleeve_weight), "event"),
                             (base_indices, "monthly")):
            compact, _, fills = replay.run(blended, indices, 5.0, 0)
            key = f"80% FR25 + 20% {label} ({tag})"
            results[key] = dict(rule=label, cost_bp=5.0, delay=0, fills=int(fills),
                                indices=int(len(indices)),
                                metrics=metrics(compact["nav"], compact["exposure"],
                                                compact["turnover"], compact["fees"]))
            daily[key] = compact["nav"]
    # FR25 and M1 replays through the same engine (integrity check on the frozen paths).
    integrity = {}
    for label, weights, indices in (
            ("FR25", fr25, base_indices),
            ("M1 monthly", np.load(V2 / "pool" / "mappings.npz")["M1_monthly__weights"],
             np.load(V2 / "pool" / "mappings.npz")["M1_monthly__indices"])):
        compact, _, _ = replay.run(weights, indices, 5.0, 0)
        integrity[label] = dict(nav_first=float(compact["nav"][0]),
                                nav_last=float(compact["nav"][-1]))
    fr25_check = np.load(V2 / "pool" / "paths" / "FR25_c5d0.npz")["nav"]
    replay_fr25, _, _ = replay.run(fr25, base_indices, 5.0, 0)
    integrity["FR25 max relative deviation vs frozen path"] = float(
        np.abs(replay_fr25["nav"] / fr25_check - 1.0).max())
    # Annual returns for the primary rule and FR25.
    year_rows = {}
    for label in ("R1 lifecycle top-six", "R3 lifecycle allocation"):
        nav = daily[label]
        year_rows[label] = {year: period_returns(nav, days[-len(nav):], f"{year}-01-01",
                                                 f"{year}-12-31")
                            for year in (2023, 2024, 2025, 2026)}
    year_rows["FR25 SOTA"] = {
        year: period_returns(benchmarks["FR25 SOTA"]["nav"], days[-len(benchmarks["FR25 SOTA"]["nav"]):],
                             f"{year}-01-01", f"{year}-12-31")
        for year in (2023, 2024, 2025, 2026)}
    # Correlation of the primary selection rule with FR25.
    ret_rule = np.diff(daily["R1 lifecycle top-six"]) / daily["R1 lifecycle top-six"][:-1]
    ret_fr25 = np.diff(benchmarks["FR25 SOTA"]["nav"]) / benchmarks["FR25 SOTA"]["nav"][:-1]
    correlation = float(np.corrcoef(ret_rule, ret_fr25)[0, 1])
    # Selection frequency and class composition for the primary monthly rule.
    r1_targets = build_target_matrix(panel, signals, order, "top6", True)
    freq = Counter()
    holdings_per_rebalance = []
    slots_by_class = Counter()
    for t in base_indices:
        held = np.flatnonzero(r1_targets[t, :-1] > 0)
        holdings_per_rebalance.append(len(held))
        for j in held:
            symbol = order[j]
            freq[symbol] += 1
            slots_by_class[ASSET_CLASS.get(symbol, "Other")] += 1
    total_slots = max(1, sum(slots_by_class.values()))
    selection_summary = dict(selection_frequency=dict(sorted(freq.items(), key=lambda kv: -kv[1])),
                             average_holdings=float(np.mean(holdings_per_rebalance)),
                             rebalances=int(len(base_indices)),
                             slots_by_class={k: v for k, v in slots_by_class.most_common()},
                             slot_share_by_class={k: v / total_slots
                                                  for k, v in slots_by_class.most_common()})
    # Per-asset evidence table.
    per_asset = read_json(VAR / "fit" / "per-asset.json")
    asset_rows = []
    for symbol in order:
        entry = per_asset[symbol]
        asset_rows.append(dict(
            symbol=symbol, asset_class=entry["class_"], first=entry["first_session"],
            last=entry["last_session"],
            short_is=entry["short"]["is_metrics"], short_oos=entry["short"]["oos_stats"],
            long_is=entry["long"]["is_metrics"], long_oos=entry["long"]["oos_stats"],
            short_evidence=entry["short"]["evidence"], long_evidence=entry["long"]["evidence"],
            short_fallback=entry["short"]["fallback_transfer"],
            long_fallback=entry["long"]["fallback_transfer"],
            short_decoded=entry["short"]["decoded"], long_decoded=entry["long"]["decoded"],
        ))
    # Daily NAV series CSV.
    daily_frame = {"date": [str(d)[:10] for d in days[-len(daily["R1 lifecycle top-six"]):]]}
    for label, nav in daily.items():
        daily_frame[label] = nav
    for label in ("FR25 SOTA", "M1 momentum control", "Equal weight", "URTH", "BIL"):
        daily_frame[label] = benchmarks[label]["nav"]
    evidence = dict(
        identity="gld-lifecycle-pool-20261019-v1",
        protocol=read_json(VAR / "protocol.json"),
        symbols=order, asset_class=ASSET_CLASS, signals_summary=signals_summary(signals, order),
        results=results, benchmarks={k: v["metrics"] for k, v in benchmarks.items()},
        integrity=integrity, annual_returns=year_rows,
        correlation_rule_vs_fr25=correlation,
        selection_summary=selection_summary,
        per_asset=asset_rows,
        event_indices=int(len(event_indices(
            panel, build_target_matrix(panel, signals, order, "top6", True), base_indices,
            sleeve_weight=sleeve_weight))),
        monthly_indices=int(len(base_indices)),
    )
    (VAR / "portfolio").mkdir(parents=True, exist_ok=True)
    evidence["annual_returns"] = {k: {
        year: period_returns(nav, days[-len(nav):], f"{year}-01-01", f"{year}-12-31")
        for year in (2023, 2024, 2025, 2026)} for k, nav in daily.items()}
    write_json(VAR / "portfolio" / "evidence.json", evidence)
    pd.DataFrame(daily_frame).to_csv(VAR / "portfolio" / "daily-nav.csv", index=False,
                                     float_format="%.4f")
    pd.DataFrame(asset_rows).to_csv(VAR / "portfolio" / "per-asset.csv", index=False)
    write_json(VAR / "portfolio" / "manifest.json",
               {"evidence.json": sha256(VAR / "portfolio" / "evidence.json"),
                "daily-nav.csv": sha256(VAR / "portfolio" / "daily-nav.csv"),
                "per-asset.csv": sha256(VAR / "portfolio" / "per-asset.csv")})
    print(json.dumps(dict(
        primary={k: {m: round(v, 4) for m, v in r["metrics"].items()}
                 for k, r in results.items() if r["cost_bp"] == 5 and r["delay"] == 0},
        fr25=benchmarks["FR25 SOTA"]["metrics"], correlation=correlation,
        integrity=integrity), indent=1))


def signals_summary(signals, symbols):
    out = {}
    for kind in ("short", "long"):
        active = signals[f"{kind}_active"]
        out[kind] = dict(
            mean_active_per_asset=float(active.mean()),
            assets_with_any_active=int((active.sum(axis=0) > 0).sum()),
            mean_extension_when_active=float(
                signals[f"{kind}_score"][active.astype(bool)].mean()
                if (active.astype(bool)).any() else 0.0))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "fit", "signals", "portfolio"])
    args = parser.parse_args()
    globals()[args.stage]()
