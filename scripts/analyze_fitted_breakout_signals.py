"""Evaluate sealed per-ETF fits; no parameter selection occurs in this stage."""
from __future__ import annotations

import json

import numpy as np

import fit_breakout_signal_audit as study

ROOT, OUTPUT, WORK = study.ROOT, study.OUTPUT, study.WORK
old, br, stats = study.old, study.br, study.stats


def verified_fits():
    declared = json.loads((OUTPUT / "protocol.json").read_text())
    if declared != study.protocol():
        raise ValueError("Study input/code identity changed")
    manifest = json.loads((OUTPUT / "fit-manifest.json").read_text())
    if manifest["protocol_sha256"] != study.digest(OUTPUT / "protocol.json"):
        raise ValueError("Fit identity changed")
    result = {}
    for name, expected in manifest["files"].items():
        path = WORK / "fits" / name
        if study.digest(path) != expected:
            raise ValueError("Fit changed: " + name)
        row = json.loads(path.read_text())
        result[row["symbol"]] = row["fits"]
    return declared, result


def expose(f, prepared, vector, method, cost, delay):
    if method == "legacy_original":
        sim = old.simulate(f, prepared, start=252, cost_bp=cost, delay=delay, trace=True)
        desired = sim["state"] == old.STATE_LONG
        entry = np.zeros(len(f.days))
        for e in sim["episodes"]:
            entry[e["confirmation"]] = 1
        level = sim["level"]
        held = desired
    else:
        sim = br.simulate(f, prepared, start=252, cost_bp=cost, delay=delay)
        desired, held, level = sim["desired"], sim["held"], sim["level"]
        entry = np.zeros(len(f.days))
        for e in sim["events"]:
            if e["side"] == "buy":
                entry[e["day"]] = 1
        # Independent event-ledger calculation, with no lifecycle state logic.
        by_fill = {e["fill"]: e["side"] for e in sim["events"]}
        cash, units = 1., 0.
        checked = []
        for t in range(252, len(f.days)):
            if by_fill.get(t) == "buy":
                units = cash / (f.open[t] * (1 + cost / 10000))
                cash = 0.
            elif by_fill.get(t) == "sell":
                cash = units * f.open[t] * (1 - cost / 10000)
                units = 0.
            checked.append(cash + units * f.close[t])
        if not np.allclose(checked, sim["nav"][252:], atol=1e-10, rtol=1e-10):
            raise ValueError("Corrected asset NAV differs from independent event ledger")
    extension = np.where(desired & np.isfinite(level) & (prepared["atr"] > 0),
                         (f.close - level) / np.maximum(prepared["atr"], 1e-12), 0.)
    return sim, desired, held, entry, extension


def measure(f, sim, desired, held, bill, lo, hi):
    nav = sim["nav"][lo - 1:hi]
    close = f.close[lo - 1:hi]
    row = dict(**stats.nav_stats(nav), buyhold=stats.nav_stats(close),
        exposure=float(held[lo:hi].mean()), active=float(desired[lo:hi].mean()),
        **stats.alpha(nav, close, bill["close"][lo - 1:hi]))
    trades = [e for e in sim["episodes"] if e["entry_index"] >= lo and e.get("exit_index") is not None and e["exit_index"] < hi]
    row["completed_trades"] = len(trades)
    row["win_fraction"] = sum(e["exit_price"] > e["entry"] for e in trades) / len(trades) if trades else None
    return row


def information(f, desired, entry, extension, bill, lo, hi):
    rows = {}
    for h in (5, 21, 63):
        forward = stats.forward_returns(f.open[:hi], f.close[:hi], bill["open"][:hi], bill["close"][:hi], h)
        rows[str(h)] = {key: stats.rank_ic(value[lo:hi], forward[lo:hi], h)
                       for key, value in (("state", desired), ("entry", entry), ("extension", extension))}
        finite = np.isfinite(forward[lo:hi])
        s, y = desired[lo:hi][finite], forward[lo:hi][finite]
        rows[str(h)]["conditional_mean_excess_return"] = dict(
            on=float(y[s].mean()) if s.any() else None, off=float(y[~s].mean()) if (~s).any() else None,
            on_observations=int(s.sum()), off_observations=int((~s).sum()))
    return rows


def gld_claims(declared, bill_data):
    data = study.load_asset("GLD")
    lookup = {str(day): t for t, day in enumerate(bill_data["days"])}
    mapped = {k: np.array([bill_data[k][lookup[str(d)]] if str(d) in lookup else np.nan for d in data["days"]]) for k in ("open", "close")}
    rows, paths = [], {}
    for kind, spec in (("short", old.SHORT_SPEC), ("long", old.LONG_SPEC)):
        f = old.Features.build(data, spec)
        for phase, first, last in (("original", "2023-01-03", "2026-10-16"), ("procedure", "2016-01-04", "2022-12-30")):
            p = spec.canonical(declared["gld_anchors"][kind + "_" + phase]["parameters"])
            prepared = old.prepare(f, p)
            lo = int(np.flatnonzero(f.days >= np.datetime64(first))[0])
            hi = int(np.flatnonzero(f.days <= np.datetime64(last))[-1]) + 1
            for method in ("legacy_original", "corrected_original"):
                for cost, delay in study.FRICTIONS:
                    sim, desired, held, entry, extension = expose(f, prepared, p, method, cost, delay)
                    result = dict(domain=kind, phase=phase, method=method, cost_bp=cost, delay=delay,
                                  **measure(f, sim, desired, held, mapped, lo, hi))
                    if cost == 5 and delay == 0:
                        result["ic"] = information(f, desired, entry, extension, mapped, lo, hi)
                        key = f"{kind}_{phase}_{method}"
                        paths[key] = sim["nav"][lo - 1:hi] / sim["nav"][lo - 1]
                        paths[phase + "_dates"] = f.days[lo - 1:hi].astype(str)
                    rows.append(result)
    study.write(OUTPUT / "gld-claim-audit.json", rows)
    np.savez_compressed(WORK / "gld-nav.npz", **paths)
    return rows


def main():
    if (OUTPUT / "asset-results.json").exists():
        raise ValueError("Preserve completed evidence")
    declared, fits = verified_fits()
    bill_data = study.load_asset("BIL")
    gld_claims(declared, bill_data)
    panel = study.frozen._load_panel()
    symbols = list(panel["symbols"])
    n, m = panel["close"].shape
    signals = {k: np.zeros((n, m)) for k in ("short_refit", "long_refit", "short_original", "long_original",
        "short_extension", "long_extension", "short_early", "long_early")}
    prior_frequency = np.zeros((2, m))
    rows, ic_rows = [], []
    original = study.frozen.frozen_parameters()["sleeve"]
    for j, symbol in enumerate(symbols):
        data = study.load_asset(symbol)
        bill_lookup = {str(day): t for t, day in enumerate(bill_data["days"])}
        bill = {k: np.array([bill_data[k][bill_lookup[str(d)]] if str(d) in bill_lookup else np.nan for d in data["days"]]) for k in ("open", "close")}
        lookup = {str(day): t for t, day in enumerate(data["days"])}
        panel_ix = [lookup[str(day)] for day in panel["days"]]
        for domain, spec in (("short", old.SHORT_SPEC), ("long", old.LONG_SPEC)):
            f = old.Features.build(data, spec)
            for era, first, last in (("late", "2023-01-03", "2026-10-16"), ("early", "2020-01-02", "2022-12-30")):
                fit = fits[symbol][domain + "_" + era]
                variants = {}
                if era == "late":
                    variants.update(legacy_original=original[domain + "_parameters"][symbol],
                        corrected_original=original[domain + "_parameters"][symbol],
                        gld_transfer=declared["gld_anchors"][domain + "_original"]["parameters"])
                if fit["available"]:
                    variants["corrected_refit"] = fit["parameters"]
                lo = int(np.flatnonzero(f.days >= np.datetime64(first))[0])
                hi = int(np.flatnonzero(f.days <= np.datetime64(last))[-1]) + 1
                for method, vector in variants.items():
                    p = spec.canonical(vector)
                    prepared = old.prepare(f, p)
                    for cost, delay in study.FRICTIONS:
                        sim, desired, held, entry, extension = expose(f, prepared, p, method, cost, delay)
                        record = dict(symbol=str(symbol), domain=domain, era=era, method=method, cost_bp=cost, delay=delay,
                            fit_evidence=fit.get("evidence") if method == "corrected_refit" else None,
                            **measure(f, sim, desired, held, bill, lo, hi))
                        rows.append(record)
                        if cost == 5 and delay == 0:
                            ic_rows.append(dict(symbol=str(symbol), domain=domain, era=era, method=method,
                                metrics=information(f, desired, entry, extension, bill, lo, hi)))
                            if method == "corrected_refit":
                                key = domain + ("_refit" if era == "late" else "_early")
                                signals[key][:, j] = desired[panel_ix] if fit.get("evidence") else 0.
                                if era == "late":
                                    signals[domain + "_extension"][:, j] = extension[panel_ix] if fit.get("evidence") else 0.
                                    prior_frequency[0 if domain == "short" else 1, j] = float(desired[252:lo].mean()) if fit.get("evidence") else 0.
                                # Full-history causal features must reproduce the frozen fit through its boundary.
                                fit_end = int(np.flatnonzero(f.days <= np.datetime64("2022-12-30" if era == "late" else "2019-12-31"))[-1]) + 1
                                truncated = f.truncated("2022-12-30" if era == "late" else "2019-12-31")
                                fit_sim = br.simulate(truncated, old.prepare(truncated, p), start=252)
                                if not np.allclose(fit_sim["nav"][252:], sim["nav"][252:fit_end], atol=1e-12, rtol=0):
                                    raise ValueError("Fit prefix differs from evaluation")
                            elif method == "corrected_original" and era == "late":
                                signals[domain + "_original"][:, j] = desired[panel_ix]
        print("Evaluated", symbol, flush=True)
    # Primary families are all 51 risky ETFs x two domains; no unreported winner filter.
    for era in ("early", "late"):
        primary = [r for r in rows if r["era"] == era and r["method"] == "corrected_refit" and r["symbol"] != "BIL" and r["cost_bp"] == 5 and r["delay"] == 0]
        adjusted = stats.holm([r["p"] for r in primary] + [None] * (102 - len(primary)))
        for r, q in zip(primary, adjusted):
            r["alpha_holm_p"] = q
        primary_ic = [r for r in ic_rows if r["era"] == era and r["method"] == "corrected_refit" and r["symbol"] != "BIL"]
        adjusted = stats.holm([r["metrics"]["21"]["state"]["p"] for r in primary_ic] + [None] * (102 - len(primary_ic)))
        for r, q in zip(primary_ic, adjusted):
            r["state21_holm_p"] = q
    verified_fits()
    study.write(OUTPUT / "asset-results.json", dict(rows=rows, independent_event_ledger="all corrected paths matched",
        fit_prefix="all selected fits matched the truncated training replay", analysis_sha256=study.digest(study.Path(__file__))))
    study.write(OUTPUT / "information-coefficients.json", ic_rows)
    np.savez_compressed(WORK / "signals.npz", symbols=symbols, days=panel["days"], prior_frequency=prior_frequency, **signals)
    study.write(OUTPUT / "signal-manifest.json", {"signals.npz": study.digest(WORK / "signals.npz")})
    print("Done", len(rows), "return/alpha rows;", len(ic_rows), "IC rows", flush=True)


if __name__ == "__main__":
    main()
