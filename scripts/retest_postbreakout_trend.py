"""Separate declared test of post-entry rising-trend failure exits."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import analyze_fitted_breakout_signals as source  # noqa: E402
from systematic_trading.research import post_breakout_trend as model  # noqa: E402

study, old, stats = source.study, source.old, source.stats
OUT = ROOT / "research/post-breakout-trend-20261023-v1"
WORK = ROOT / "var/research/post-breakout-trend-20261023-v1"
FAMILIES = ("trend_fit",)
VARIANTS = ("baseline", *FAMILIES, "shared_trend")
ERAS = (("late", "2022-12-30", "2023-01-03", "2026-10-16"),
        ("early", "2019-12-31", "2020-01-02", "2022-12-30"))


def clean(value):
    """Machine evidence keeps full precision; formatting belongs in the report."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write(path, value):
    study.write(path, clean(value))


def grid(domain):
    return [dict(range="legacy", trend="none", exit="legacy", rule=None)] + [
        dict(range="legacy", trend="none", exit="post_trend", rule=dict(lookback=n, buffer_atr=b))
        for n, b in product((10, 21, 42, 63), (.5, 1., 2.))]


def subset(row, family):
    return family == "trend_fit"


def protocol():
    declared, fits = source.verified_fits()
    return dict(identity=OUT.name, model=model.VERSION,
        source_protocol_sha256=study.digest(source.OUTPUT / "protocol.json"),
        source_sealed_fits_sha256=study.digest(source.OUTPUT / "sealed-fits.json"),
        published_batch=declared["data"]["batch"], universe=sorted(fits), grid=grid("short"),
        question="Does exiting on failure of the new post-entry rising trend accommodate both sustained GLD trends and steep IAT reversals without selecting winners from evaluation?",
        entry="Keep all own-ETF independently fitted range/breakout/confirmation/volume/continuation/cooldown rules fixed. This isolates exits; a separate downward-channel entry redesign is not included.",
        exit="Replace old trailing/heat profit rule with rising log-price OLS support fitted only to post-entry closes through yesterday. Require at least5 prior closes; growing window capped at10/21/42/63. Project today; add10th-percentile in-window residual; subtract0.5/1/2 prior-session ATR (own fitted ATR period). Positive slope creates support; ratchet it upward, never loosen it if slope turns negative. Retain original initial risk floor. Original failed-breakout time exit remains until first valid rising support, then trend support governs. Close below effective floor triggers next-open sale, symmetric optional delay. No fixed profit activation threshold or intraday fill.",
        fit="13 candidates including unchanged baseline, separately each ETF/domain/era. Same original utility, three chronological blocks and scarcity penalties. Top5 plus baseline rescored across6 frictions. Replacement requires>=5 training closed trades and5% exposure, CAGR within1pp/DD within2pp of baseline in every friction, and worst utility improvement>.01. Otherwise retain baseline. No retuning from evaluation outcomes. Original27-coordinate anchor stays fixed; lookback/noise allowance refitted per ETF.",
        controls="Baseline, training-selected trend exit, fixed21-session/1ATR trend-exit control applied to full pool. GLD/IAT examples chosen by operator before this test, not used for parameter selection. Both original heavily optimized GLD anchors also get the fixed21/1 rule as a separately labelled sensitivity, not substituted into pool fits.",
        evaluation="Train through2022 evaluate2023-01-03..2026-10-16; separately train through2019 evaluate2020-01-02..2022-12-30. Seal all fits before evaluation. Carry virtual state; idle cash0; all52 supported ETFs, BIL excluded from risky family; no future fallback. These are inspected development periods, not untouched holdouts.",
        frictions=study.FRICTIONS,
        data="Pinned published adjusted OHLC and audited raw volume only. No online sources/splicing/fills; same batch and hashes as verified baseline. Historical membership and publication-vintage limitations remain.",
        metrics="Net cumulative/CAGR/Sharpe/standardCalmar/DD, alpha over same ETF/BIL, stateIC21, exposure, actual turnover/fees, prior-close regime attribution. Exact baseline regression, ledger reconciliation and training-prefix checks.",
        portfolio="Training-selected states in same full52 admitted six-slot98% momentum selector (rank buffer8,BIL vacancies) and FR25*(.5+.25short+.25long) overlay. Dynamic membership vs monthly; overlay dynamic last-adopted cash-inclusiveL1>=.10+monthly vs monthly. All6 frictions; both eras selector; later FR25/overlay throughOct12. Compare paired baseline, ungated momentum and FR25. Independent native checks for selected/delayed representative portfolios.",
        acceptance="ExcludeBIL and inadequate original training evidence from family gate, retain all in tables. Improved median Sharpe and lower-quartileCAGR;>=90% within1pp CAGR loss and2pp DD deterioration. Require all frictions and both eras. Portfolio higher Sharpe,CAGR within1pp,no worseDD versus matched baseline and FR25(late)/momentum(early). No post-result winner substitution.",
        code_hashes={str(p.relative_to(ROOT)).replace(chr(92), '/'): study.digest(p) for p in (
            Path(__file__), ROOT / "src/systematic_trading/research/post_breakout_trend.py",
            ROOT / "src/systematic_trading/research/breakout_adaptive.py",
            ROOT / "scripts/run_fitted_breakout_portfolios.py", ROOT / "scripts/revisit_breakout_research.py")},
        authority="Research only; no promotion, monitoring, execution, funding, broker or service changes.")


def prepare_protocol():
    p = protocol()
    path = OUT / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != clean(p):
        raise ValueError("Changed protocol")
    write(path, p)
    print("Frozen", study.digest(path), flush=True)


def prepared(f, vector, row, cache):
    return model.prepare(f, vector, row["rule"])


def score(f, p, cost=5, delay=0):
    sim = model.simulate(f, p, cost_bp=cost, delay=delay)
    start, end = 252, len(f.days)
    bh = np.full(end, np.nan)
    bh[start:] = f.close[start:] / f.open[start] / (1 + cost / 10000)
    def window(a, lo, hi):
        return stats.nav_stats(np.r_[1. if lo == start else a[lo - 1], a[lo:hi]])
    full, base = window(sim["nav"], start, end), window(bh, start, end)
    exposure = float(sim["held"][start:].mean())
    closed = sum(e["exit_index"] is not None for e in sim["episodes"])
    blocks = [old.utility(window(sim["nav"], lo, hi), window(bh, lo, hi)) for lo, hi in old.block_bounds(start, end)]
    value = (.5 * old.utility(full, base) + .5 * np.median(blocks) - .25 * np.std(blocks)
             - .1 * max(0, 10 - closed) / 10 - .3 * max(0, .20 - exposure) / .20)
    return dict(score=float(value), cagr=full["cagr"], sharpe=full["sharpe"], maxdd=full["maxdd"],
                exposure=exposure, closed=closed)


def fit_job(job):
    symbol, oldfits, protocol_hash = job
    records = {}
    data = study.load_asset(symbol)
    for domain, spec in (("short", old.SHORT_SPEC), ("long", old.LONG_SPEC)):
        full = old.Features.build(data, spec)
        for era, cutoff, _, _ in ERAS:
            key = domain + "_" + era
            anchor = oldfits[key]
            if not anchor["available"]:
                records[key] = dict(available=False, reason="Insufficient training history")
                continue
            f = full.truncated(cutoff)
            cache = {}
            choices = grid(domain)
            preps = [prepared(f, anchor["parameters"], r, cache) for r in choices]
            base_scores = [score(f, p) for p in preps]
            shortlist = {0}
            for family in FAMILIES:
                ix = [i for i, r in enumerate(choices) if subset(r, family)]
                shortlist.update(sorted(ix, key=lambda i: (-base_scores[i]["score"], i))[:5])
            robust = {i: [base_scores[i]] + [score(f, preps[i], c, d) for c, d in study.FRICTIONS[1:]]
                      for i in sorted(shortlist)}
            worst = lambda i: min(r["score"] for r in robust[i])
            eligible = {i: all(r["closed"] >= 5 and r["exposure"] >= .05
                and r["cagr"] >= b["cagr"] - .01 and r["maxdd"] >= b["maxdd"] - .02
                for r, b in zip(rows, robust[0], strict=True)) for i, rows in robust.items()}
            chosen = {}
            for family in FAMILIES:
                ix = [i for i in shortlist if subset(choices[i], family) and eligible[i] and worst(i) > worst(0) + .01]
                best = min(ix, key=lambda i: (-worst(i), i)) if ix else 0
                chosen[family] = dict(index=best, components=choices[best], worst_score=worst(best),
                                      training=robust[best], retained_baseline=best == 0)
            records[key] = dict(available=True, training_end=str(f.days[-1]), training_sessions=len(f.days) - 252,
                anchor_evidence=anchor["evidence"], parameters=anchor["parameters"], choices=chosen,
                base_scores=base_scores, finalists={str(i): dict(components=choices[i], training=v, eligible=eligible[i])
                                                  for i, v in robust.items()})
    write(WORK / "fits" / (symbol + ".json"), dict(symbol=symbol, protocol_sha256=protocol_hash, fits=records))
    return symbol


def fit():
    if clean(protocol()) != json.loads((OUT / "protocol.json").read_text()):
        raise ValueError("Study inputs changed")
    _, fits = source.verified_fits()
    h = study.digest(OUT / "protocol.json")
    jobs = [(s, fits[s], h) for s in sorted(fits) if not (WORK / "fits" / (s + ".json")).exists()]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for s in pool.map(fit_job, jobs):
            print("Fitted and sealed", s, flush=True)
    files = {p.name: study.digest(p) for p in sorted((WORK / "fits").glob("*.json"))}
    if len(files) != 52 or any(json.loads((WORK / "fits" / p).read_text())["protocol_sha256"] != h for p in files):
        raise ValueError("Incomplete or mixed fits")
    write(OUT / "fit-manifest.json", dict(protocol_sha256=h, files=files))


def verified():
    if clean(protocol()) != json.loads((OUT / "protocol.json").read_text()):
        raise ValueError("Study identity changed")
    manifest = json.loads((OUT / "fit-manifest.json").read_text())
    if manifest["protocol_sha256"] != study.digest(OUT / "protocol.json"):
        raise ValueError("Fit protocol changed")
    result = {}
    for name, h in manifest["files"].items():
        p = WORK / "fits" / name
        if study.digest(p) != h:
            raise ValueError("Fit changed")
        r = json.loads(p.read_text())
        result[r["symbol"]] = r["fits"]
    return result


def ledger(f, sim, cost):
    events = {e["fill"]: e["side"] for e in sim["events"]}
    cash, units, turnover, fees, error = 1., 0., [], [], 0.
    for t in range(252, len(f.days)):
        value = cash + units * f.open[t]
        amount = 0.
        if events.get(t) == "buy":
            amount = cash / (1 + cost / 10000)
            units, cash = amount / f.open[t], 0.
        elif events.get(t) == "sell":
            amount = units * f.open[t]
            cash, units = amount * (1 - cost / 10000), 0.
        turnover.append(amount / value)
        fees.append(amount / value * cost / 10000)
        error = max(error, abs((cash + units * f.close[t]) / sim["nav"][t] - 1))
    if error > 1e-10:
        raise ValueError("Event ledger mismatch")
    return np.r_[np.zeros(252), turnover], np.r_[np.zeros(252), fees], error


def evaluate():
    if (OUT / "asset-results.json").exists():
        raise ValueError("Preserve completed evaluation")
    fits = verified()
    panel = study.frozen._load_panel()
    symbols = list(panel["symbols"])
    bill_data = study.load_asset("BIL")
    bill_lookup = {str(d): i for i, d in enumerate(bill_data["days"])}
    signals = {f"{domain}_{era}_{variant}": np.zeros(panel["close"].shape, bool)
               for domain in ("short", "long") for era, *_ in ERAS for variant in ("baseline", "trend_fit")}
    rows, choices, regime_rows = [], [], []
    max_error = 0.
    for symbol in sorted(fits):
        data = study.load_asset(symbol)
        lookup = {str(d): i for i, d in enumerate(data["days"])}
        panel_ix = [lookup[str(d)] for d in panel["days"]]
        bill = {k: np.array([bill_data[k][bill_lookup[str(d)]] if str(d) in bill_lookup else np.nan for d in data["days"]])
                for k in ("open", "close")}
        for domain, spec in (("short", old.SHORT_SPEC), ("long", old.LONG_SPEC)):
            f = old.Features.build(data, spec)
            cache = {}
            regimes = model.regimes(f.close)
            for era, cutoff, first, last in ERAS:
                fit_ = fits[symbol][domain + "_" + era]
                if not fit_["available"]:
                    continue
                lo = int(np.flatnonzero(f.days >= np.datetime64(first))[0])
                hi = int(np.flatnonzero(f.days <= np.datetime64(last))[-1]) + 1
                for variant in VARIANTS:
                    config = (grid(domain)[0] if variant == "baseline" else
                              dict(range="legacy", trend="none", exit="post_trend", rule=dict(lookback=21, buffer_atr=1.))
                              if variant == "shared_trend" else fit_["choices"][variant]["components"])
                    p = prepared(f, fit_["parameters"], config, cache)
                    choices.append(dict(symbol=symbol, domain=domain, era=era, variant=variant, **config,
                                        training_evidence=fit_["anchor_evidence"]))
                    for cost, delay in study.FRICTIONS:
                        sim = model.simulate(f, p, cost_bp=cost, delay=delay)
                        turn, fees, error = ledger(f, sim, cost)
                        max_error = max(max_error, error)
                        row = dict(symbol=symbol, domain=domain, era=era, variant=variant, cost_bp=cost, delay=delay,
                            training_evidence=fit_["anchor_evidence"], **source.measure(f, sim, sim["desired"], sim["held"], bill, lo, hi))
                        row.update(cumulative=sim["nav"][hi - 1] / sim["nav"][lo - 1] - 1,
                            calmar=row["cagr"] / abs(row["maxdd"]) if abs(row["maxdd"]) > 1e-12 else None,
                            turnover_annual=float(turn[lo:hi].sum() * 252 / (hi - lo)),
                            cost_bp_annual=float(fees[lo:hi].sum() * 252 / (hi - lo) * 10000))
                        if cost == 5 and delay == 0:
                            forward = stats.forward_returns(f.open[:hi], f.close[:hi], bill["open"][:hi], bill["close"][:hi], 21)
                            row["ic21"] = stats.rank_ic(sim["desired"][lo:hi], forward[lo:hi], 21)
                            daily = np.diff(np.log(sim["nav"][lo - 1:hi]))
                            bh = np.diff(np.log(f.close[lo - 1:hi]))
                            for state in ("up", "down", "mixed", "unknown"):
                                mask = regimes[lo - 1:hi - 1] == state
                                regime_rows.append(dict(symbol=symbol, domain=domain, era=era, variant=variant, regime=state,
                                    sessions=int(mask.sum()), strategy_log_return=float(daily[mask].sum()),
                                    benchmark_log_return=float(bh[mask].sum()), held_sessions=int(sim["held"][lo:hi][mask].sum())))
                            if variant in {"baseline", "trend_fit"}:
                                signals[f"{domain}_{era}_{variant}"][:, symbols.index(symbol)] = sim["desired"][panel_ix]
                                # The evaluated full-data path must reproduce its sealed training score.
                                train_f = f.truncated(cutoff)
                                train_p = prepared(train_f, fit_["parameters"], config,
                                    {k: {q: v[:len(train_f.days)] for q, v in b.items()} for k, b in cache.items()})
                                training = score(train_f, train_p)
                                prefix = model.simulate(train_f, train_p)
                                for field in ("nav", "desired", "held", "stop"):
                                    np.testing.assert_allclose(prefix[field], sim[field][:len(train_f.days)],
                                                               atol=1e-10, rtol=0, equal_nan=True)
                                sealed = (fit_["finalists"]["0"]["training"][0] if variant == "baseline"
                                          else fit_["choices"][variant]["training"][0])
                                for k in ("score", "cagr", "sharpe", "maxdd", "exposure"):
                                    if abs(training[k] - sealed[k]) > 1e-10:
                                        raise ValueError("Training recipe changed")
                        rows.append(row)
        print("Evaluated", symbol, flush=True)
    write(OUT / "asset-results.json", rows)
    write(OUT / "selected-components.json", choices)
    write(OUT / "regime-attribution.json", regime_rows)
    WORK.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(WORK / "signals.npz", **signals)
    write(OUT / "validation.json", dict(asset_cases=len(rows), event_ledger_max_relative_error=max_error,
        training_selection_reproduced=True, all_fits_sealed_before_evaluation=True,
        signal_sha256=study.digest(WORK / "signals.npz")))
    verified()


def portfolios():
    import run_fitted_breakout_portfolios as parent
    import revisit_breakout_research as control
    from retest_fr25_lifecycle_review import metrics
    verified()
    if (OUT / "portfolio-results.json").exists():
        raise ValueError("Preserve completed portfolio evidence")
    receipt = json.loads((OUT / "validation.json").read_text())
    if study.digest(WORK / "signals.npz") != receipt["signal_sha256"]:
        raise ValueError("Signals changed")
    with np.load(WORK / "signals.npz", allow_pickle=False) as a:
        signals = {k: a[k] for k in a.files}
    panel = study.frozen._load_panel()
    recipe = json.loads(study.frozen.RECIPE_PATH.read_text())
    scores = study.br.momentum_score(panel["close"])
    rows, native, paths = [], {}, {}
    for era, _, first, last in ERAS:
        replay = study.frozen._Replay(panel, recipe, first)
        dates = [str(panel["days"][replay.indices[0] - 1]), *map(str, replay.days)]
        end = next((i for i, d in enumerate(dates) if d > last), len(dates))
        monthly = control.monthly_indices(panel, first)
        n = len(panel["days"])
        scenarios = {"FR25": (np.column_stack([panel["fr25"], np.zeros(n)]), study.frozen._monthly_indices(panel), None)} if era == "late" else {}
        for clock in ("dynamic", "monthly"):
            scenarios["momentum_" + clock] = study.br.select_targets(panel, panel["admitted"], scores, monthly, clock=clock)
            for variant in ("baseline", "trend_fit"):
                s, l = signals[f"short_{era}_{variant}"], signals[f"long_{era}_{variant}"]
                scenarios[f"{variant}_selection_{clock}"] = study.br.select_targets(panel, panel["admitted"] & (s | l), scores, monthly, clock=clock)
                if era == "late":
                    scenarios[f"{variant}_overlay_{clock}"] = parent.overlay_targets(panel, .5 + .25 * s + .25 * l, clock)
        for name, (weights, indices, _) in scenarios.items():
            for cost, delay in study.FRICTIONS:
                result, fills = replay.run_result(weights, indices, cost, delay)
                payload = study.frozen.report_payload(replay, result, fills)
                nav = np.array([float(r["nav_cnh"]) for r in payload["nav_series"]])[:end]
                period_fills = [fill for fill in fills if fill["date"] <= last] if era == "early" else fills
                row = dict(era=era, scenario=name, cost_bp=cost, delay=delay,
                           **metrics(nav, dates[:end], period_fills))
                rows.append(row)
                if era == "late" and name in {"trend_fit_overlay_dynamic", "trend_fit_selection_dynamic"} and cost == 5:
                    key = f"{name}_c{cost}d{delay}"
                    native[key + "_weights"], native[key + "_indices"] = weights, indices
                    paths[key] = nav
                print("Portfolio", era, name, cost, delay, round(row["cagr"] * 100, 2), flush=True)
    write(OUT / "portfolio-results.json", rows)
    np.savez_compressed(WORK / "native-mappings.npz", **native)
    np.savez_compressed(WORK / "native-nav.npz", **paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "fit", "evaluate", "portfolios"))
    {"prepare": prepare_protocol, "fit": fit, "evaluate": evaluate, "portfolios": portfolios}[parser.parse_args().stage]()
