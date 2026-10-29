"""Fit corrected lifecycle per ETF; seal before evaluating held-out chronology."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from retest_fr25_lifecycle_review import digest, write  # noqa: E402
from systematic_trading.research import breakout_revisit as br  # noqa: E402
from systematic_trading.research import fitted_breakout_diagnostics as stats  # noqa: E402
from systematic_trading.research import fr25_lifecycle_conditional as frozen  # noqa: E402
from systematic_trading.research import range_lifecycle as old  # noqa: E402

OUTPUT = ROOT / "research/fitted-breakout-audit-20261021-v1"
WORK = ROOT / "var/research/fitted-breakout-audit-20261021-v1"
FRICTIONS = [(c, d) for c in (5, 10, 20) for d in (0, 1)]


def anchors():
    result = {}
    for kind, name in (("short", "gld-lifecycle-20261019-v1"), ("long", "gld-longrange-lifecycle-20261019-v1")):
        for phase, suffix in (("original", "selection.json"), ("procedure", "validation/selection.json")):
            path = ROOT / "var/research" / name / suffix
            vector = json.loads(path.read_text())["chosen"]["parameter_vector"]
            if len(vector) == 24:
                vector += [0, 0., 0]
            result[kind + "_" + phase] = dict(parameters=vector, source=str(path.relative_to(ROOT)), sha256=digest(path))
    return result


def protocol():
    return dict(identity=OUTPUT.name, question="Do individually fitted breakout/lifecycle rules earn net returns, ETF-beta-adjusted alpha and forward IC; does this generalize beyond GLD and add to FR25?",
        data=frozen.verified_input_provenance(), gld_anchors=anchors(),
        code_hashes={p: digest(ROOT / p) for p in ("scripts/fit_breakout_signal_audit.py",
            "src/systematic_trading/research/breakout_revisit.py", "src/systematic_trading/research/fitted_breakout_diagnostics.py",
            "src/systematic_trading/research/range_lifecycle.py", "src/systematic_trading/research/fr25_lifecycle_conditional.py")},
        universe="All 52 audited price-supported ETFs individually. BIL is cash benchmark, excluded from the 51-asset alpha/IC family. No new provider data.",
        original_audit="Replay original GLD short/long vectors and original per-ETF vectors under both frozen legacy and corrected execution. Preserve original 2026-10-16 single-ETF cutoff; portfolios share FR25's 2026-10-12 cutoff.",
        fit="Each of 52 ETFs independently, short and long existing structural domains. Truncate at 2022-12-30, and separately at 2019-12-31 for procedure validation. Warmup252; >=500 training sessions required, otherwise unavailable (no future-trained fallback). 200 uniform canonical draws + anchor +40 8%-domain Gaussian mutations, deterministic symbol/domain seed. Pre-2023 anchor is original own-ETF fitted vector. Pre-2020 anchor is domain midpoint; never use later fitted anchors. Identical search budget per ETF, no OOS selection.",
        objective="Original 45/40/15 excess CAGR/Sharpe/regularized-Calmar utility versus buy-hold; repaired initial-capital anchor. 0.5 full +0.5 median of 3 chronological blocks -0.25 block SD -0.1 trade scarcity -0.3 exposure scarcity. Top15 rescored at six cost/delay cases; choose largest worst-case score among >=5 closed trades and >=5% training exposure; otherwise mark evidence insufficient.",
        evaluation="Pre2023 fits evaluated 2023-01-03..2026-10-16; pre2020 fits evaluated 2020-01-02..2022-12-30. Full-history virtual state carried from training; each evaluation includes preceding NAV/close anchor. Cash earns zero; buy-hold uses same prior-close anchor. Report 5/10/20bp and 0/1 added sessions. No reinvestment/entry at OOS boundary is invented. Returns from training are not evidence of extrapolation.",
        alpha="OLS(strategy daily net return minus BIL return) ~ intercept + (same ETF return minus BIL return). Annualized intercept, beta, Newey-West lag21 normal-approximate p. Positive CAGR alone is not alpha; alpha can arise from timing/exposure, not proof of fundamental alpha. Check all frictions and both chronologies.",
        ic="Primary: per-ETF Spearman(close-time desired long state, next-open to close t+21 ETF return minus BIL). Secondary: confirmation-entry indicator and active extension/ATR, horizons5/63. Labels remain wholly within evaluation. Rank-OLS Newey-West horizon lag handles overlap approximately. Also daily cross-sectional rank IC for state and extension across the 51 risky ETFs. Holm adjustment across 102 ETF/domain tests separately for primary alpha and IC. All inference descriptive after prior model/data inspection.",
        gld_transfer="Replay original pre-2023 GLD vector unchanged on each ETF at 2023+; compare to own-ETF original and corrected refits, never call transfer individually fitted.",
        portfolio="Corrected refits only, 2023..2026-10-12, full52 price-supported cohort with frozen causal raw-dollar-volume admission mask for trading selection; BIL parking. Six 98%/6 slots, positive momentum score; short/long union eligibility, rank-buffer8, dynamic membership or monthly control. Overlay: FR25 weight multiplied by (0.5+0.25*short_state+0.25*long_state); diverted weight to BIL, core cash preserved. Monthly or month-end +cash-inclusive L1>=10% events. All six frictions; no absolute cost gate.",
        controls="FR25; same full-pool admitted momentum selector without lifecycle gate at both clocks; original frozen-fit overlay at both clocks; constant per-asset overlay multiplier estimated from pre2023 state frequency; three 21-session common-block shuffled-state placebo overlays, seeds7/11/23, preserving cross-asset dependence. Placebos are non-deployable diagnostics. No post-result winner selection.",
        decision="Use as alpha tool only if primary alpha/IC generalizes across ETFs and chronologies and realized selection/overlay improves matched FR25 net Sharpe with CAGR loss<=1pp and no worse DD across friction cases; report component and placebo failures. Positive GLD P&L alone is insufficient. Promotion remains a separate gate.",
        limitations=["Both eras and GLD paths have previously been inspected; these are chronological development tests, not untouched confirmation.",
            "Original GLD search exceeded 500k evaluations; bounded new pool refits use 241 candidates each, not equivalent optimization effort.",
            "No same-day/intraday stop fills; asset states are virtual lifecycle regimes, distinct from broker stop orders.",
            "Retrospective cohort, price audit does not certify historical availability/identity membership or FX. USD only.",
            "No promotion, running-service, registry, allocation, funding or broker changes."])


def prepare():
    p = protocol()
    path = OUTPUT / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != p:
        raise ValueError("Protocol changed")
    write(path, p)
    print("Frozen", digest(path), flush=True)


def load_asset(symbol):
    with np.load(ROOT / "var/research/range-breakout-20261018-v2/assets" / f"{symbol}.npz", allow_pickle=False) as a:
        return {k: a[k].copy() for k in ("days", "open", "high", "low", "close", "volume")}


def evaluate_fit(f, vector, cost=5, delay=0):
    start, end = 252, len(f.close)
    sim = br.simulate(f, old.prepare(f, vector), start=start, cost_bp=cost, delay=delay)
    bh = np.full(end, np.nan)
    bh[start:] = f.close[start:] / f.open[start] / (1 + cost / 10000)
    def window(a, lo, hi):
        return stats.nav_stats(np.r_[1. if lo == start else a[lo - 1], a[lo:hi]])
    full, base = window(sim["nav"], start, end), window(bh, start, end)
    exposure = float(sim["held"][start:end].mean())
    closed = sum(e.get("exit_index") is not None for e in sim["episodes"])
    utilities = [old.utility(window(sim["nav"], lo, hi), window(bh, lo, hi)) for lo, hi in old.block_bounds(start, end)]
    score = (.5 * old.utility(full, base) + .5 * np.median(utilities) - .25 * np.std(utilities)
             - .1 * max(0, 10 - closed) / 10 - .3 * max(0, .20 - exposure) / .20)
    return dict(score=float(score), metrics=full, buyhold=base, closed=closed, exposure=exposure)


def fit_one(f, spec, anchor, seed):
    if len(f.days) - 252 < 500:
        return dict(available=False, training_sessions=len(f.days) - 252, reason="fewer than 500 training sessions")
    rng = np.random.default_rng(seed)
    low, high = spec.bounds[:, 0], spec.bounds[:, 1]
    vectors = [spec.canonical(v) for v in rng.uniform(low, high, (200, len(low)))]
    vectors += [spec.canonical(anchor)] + [spec.canonical(anchor + rng.normal(0, .08, len(low)) * (high - low)) for _ in range(40)]
    scored = [(evaluate_fit(f, v)["score"], i) for i, v in enumerate(vectors)]
    top = sorted(scored, key=lambda row: (-row[0], row[1]))[:15]
    finalists = []
    for _, i in top:
        evaluations = [evaluate_fit(f, vectors[i], cost, delay) for cost, delay in FRICTIONS]
        base = evaluations[0]
        finalists.append(dict(parameters=vectors[i].tolist(), score=min(e["score"] for e in evaluations),
            evidence=base["closed"] >= 5 and base["exposure"] >= .05, base=base, candidate_index=i))
    eligible = [f for f in finalists if f["evidence"]]
    best = max(eligible or finalists, key=lambda x: x["score"])
    return dict(available=True, training_sessions=len(f.days) - 252, candidates=241, shortlist=15, **best)


def fit_asset(symbol):
    data = load_asset(symbol)
    original = frozen.frozen_parameters()["sleeve"]
    rows = {}
    for kind, spec in (("short", old.SHORT_SPEC), ("long", old.LONG_SPEC)):
        full = old.Features.build(data, spec)
        for era, boundary in (("late", "2022-12-30"), ("early", "2019-12-31")):
            f = full.truncated(boundary)
            anchor = np.asarray(original[kind + "_parameters"][symbol], float) if era == "late" else spec.bounds.mean(axis=1)
            seed = 20261021 + sum((i + 1) * ord(c) for i, c in enumerate(symbol)) + (1000 if kind == "long" else 0)
            rows[kind + "_" + era] = fit_one(f, spec, anchor, seed)
    return symbol, rows


def fit():
    declared = json.loads((OUTPUT / "protocol.json").read_text())
    if declared != protocol():
        raise ValueError("Study inputs changed")
    symbols = list(frozen._load_panel()["symbols"])
    folder = WORK / "fits"
    folder.mkdir(parents=True, exist_ok=True)
    missing = [str(s) for s in symbols if not (folder / f"{s}.json").exists()]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for symbol, rows in pool.map(fit_asset, missing):
            write(folder / f"{symbol}.json", dict(symbol=symbol, protocol_sha256=digest(OUTPUT / "protocol.json"), fits=rows))
            print("Sealed", symbol, flush=True)
    if protocol() != declared:
        raise ValueError("Inputs changed during fitting")
    files = {p.name: digest(p) for p in sorted(folder.glob("*.json"))}
    for name in files:
        if json.loads((folder / name).read_text())["protocol_sha256"] != digest(OUTPUT / "protocol.json"):
            raise ValueError("Mixed fit identity")
    write(OUTPUT / "fit-manifest.json", dict(protocol_sha256=digest(OUTPUT / "protocol.json"), files=files))
    print("All fits sealed", len(files), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "fit"))
    {"prepare": prepare, "fit": fit}[parser.parse_args().stage]()
