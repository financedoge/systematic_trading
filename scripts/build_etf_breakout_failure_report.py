"""Full-pool tables and accounting diagnosis of sealed, individual ETF refits.

This does not transfer GLD parameters, refit on evaluation data, change the
optimizer objective or silently replace completed research evidence.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import analyze_fitted_breakout_signals as source  # noqa: E402
from build_gld_breakout_inspection import clean  # noqa: E402

OUT = ROOT / "research/etf-breakout-failure-review-20261023-v1"
TEMPLATE = ROOT / "scripts/assets/etf-breakout-failure-review.html"
CHECK_KEYS = ("cagr", "sharpe", "maxdd", "sessions")


def standard_calmar(cagr, drawdown):
    """Unregularized reporting; the old 3% optimizer floor stays frozen."""
    return cagr / abs(drawdown) if abs(drawdown) > 1e-12 else None


def interval_accounting(f, sim, lo, hi, fee=.0005):
    """Exact binary-position overnight / intraday log-return decomposition."""
    gross = np.zeros(hi - lo)
    fees = np.zeros(hi - lo)
    missing = np.zeros(hi - lo)
    by_fill = {e["fill"]: e["side"] for e in sim["events"]}
    for j, t in enumerate(range(lo, hi)):
        overnight = np.log(f.open[t] / f.close[t - 1])
        daytime = np.log(f.close[t] / f.open[t])
        before, after = bool(sim["held"][t - 1]), bool(sim["held"][t])
        gross[j] = before * overnight + after * daytime
        missing[j] = (not before) * overnight + (not after) * daytime
        if by_fill.get(t) == "buy":
            fees[j] = np.log1p(fee)
        elif by_fill.get(t) == "sell":
            fees[j] = -np.log1p(-fee)
    actual = np.diff(np.log(sim["nav"][lo - 1:hi]))
    np.testing.assert_allclose(actual, gross - fees, atol=2e-12, rtol=0)
    benchmark = np.diff(np.log(f.close[lo - 1:hi]))
    np.testing.assert_allclose(benchmark, gross + missing, atol=2e-12, rtol=0)
    return dict(net_log_return=float(actual.sum()), captured_market_log_return=float(gross.sum()),
        uninvested_market_log_return=float(missing.sum()), fee_log_drag=float(fees.sum()),
        gross_cumulative=float(np.expm1(gross.sum())), net_cumulative=float(np.expm1(actual.sum())),
        fee_cumulative_drag=float(np.expm1(gross.sum()) - np.expm1(actual.sum())),
        max_daily_accounting_error=float(np.max(np.abs(actual - gross + fees))))


def episode_details(f, prepared, sim, lo, hi):
    """Only history through hi; include carried and terminal open positions."""
    p = prepared["parameters"]
    result = []
    for e in sim["episodes"]:
        entry, exit_ = e["entry_index"], e["exit_index"]
        if entry >= hi or (exit_ is not None and exit_ < lo):
            continue
        last = min(hi - 1, e.get("exit_signal", hi - 1))
        initial = e["entry"] - p[10] * e["atr"]
        band = e["u"] - p[11] * e["atr"] if p[11] >= 0 else np.nan
        floor = max(initial, band) if np.isfinite(band) else initial
        activation = e["entry"] + p[15] * e["atr"]
        peak, stop, heat, armed = float(f.close[entry]), floor, False, False
        first_arm, first_heat = None, None
        armed_floor_days, armed_loss_floor_days = 0, 0
        for t in range(entry, last + 1):
            peak = max(peak, float(f.close[t]))
            atr = prepared["atr"][t]
            if (p[16] and f.close[t] >= e["u"] + p[17] * e["atr"]
                    and f.volume[t] >= p[18] * prepared["volmed"][t] and f.close[t] >= peak - p[19] * atr):
                heat = True
                first_heat = t if first_heat is None else first_heat
            if peak >= activation:
                armed = True
                first_arm = t if first_arm is None else first_arm
                mult = p[20] if heat else 1.
                candidate = peak - p[13] * mult * atr if p[12] == 0 else peak * (1 - p[14] * mult)
                stop = max(stop, candidate)
            if armed:
                armed_floor_days += int(stop <= floor + 1e-9)
                armed_loss_floor_days += int(stop < e["entry"])
            np.testing.assert_allclose(stop, sim["stop"][t], rtol=0, atol=1e-10)
        closed = exit_ is not None and exit_ < hi
        exit_price = e["exit_price"] if closed else float(f.close[hi - 1])
        full_return = exit_price / e["entry"] * ((1 - .0005) if closed else 1) / (1 + .0005) - 1
        start_eval, end_eval = max(lo, entry), min(hi, exit_ + 1 if closed else hi)
        window_log = np.log(sim["nav"][end_eval - 1] / sim["nav"][start_eval - 1])
        date = lambda t: str(f.days[t]) if t is not None else None
        exit_kind = ("Initial risk stop" if stop <= floor + 1e-9 else "Ratcheted trailing stop") if e.get("exit_reason") == "stop" else e.get("exit_reason", "Open at cutoff")
        result.append(dict(crossing=date(e["crossing"]), confirmation=date(e["confirmation"]), entry=date(entry), exit=date(exit_) if closed else None,
            exit_decision=date(e.get("exit_signal")), entry_price=e["entry"], exit_or_mark=exit_price,
            net_trade_return=float(full_return), evaluation_log_contribution=float(window_log), carried_in=entry < lo,
            closed=closed, sessions=(exit_ if closed else hi - 1) - entry,
            range_sessions=None if e["reentry"] else int(prepared["L"][e["crossing"]]), reentry=e["reentry"],
            initial_floor=float(floor), initial_risk_fraction=float(1 - floor / e["entry"]),
            activation=float(activation), activation_gain_fraction=float(activation / e["entry"] - 1),
            first_arm=date(first_arm), first_heat=date(first_heat), exit_kind=exit_kind, effective_last_stop=float(stop),
            peak_gain=float(peak / e["entry"] - 1), worst_close_return=float(f.close[entry:last + 1].min() / e["entry"] - 1),
            armed=armed, heat=heat, armed_days_at_initial_floor=armed_floor_days,
            armed_days_with_stop_below_entry=armed_loss_floor_days,
            base_pct_trail_break_even_peak_gain=float(p[14] / (1 - p[14])) if p[12] == 1 else None,
            close_to_open_entry_gap=float(e["entry"] / f.close[entry - 1] - 1)))
    return result


def closing_states(f, prepared, sim, lo, hi):
    """Descriptive closing states, not a counterfactual causal attribution."""
    p = prepared["parameters"]
    cool = np.zeros(hi, bool)
    queued = np.zeros(hi, bool)
    for e in sim["episodes"]:
        if e["exit_index"] is not None:
            x = e["exit_index"]
            cool[x:min(hi, x + int(p[23]))] = True
    for e in sim["events"]:
        if e["side"] == "buy":
            queued[e["day"]:min(hi, e["fill"])] = True
    counts = Counter()
    for t in range(lo, hi):
        if sim["held"][t]:
            state = "Holding"
        elif queued[t]:
            state = "Buy queued"
        elif cool[t]:
            state = "Cooldown"
        elif np.isfinite(sim["level"][t]):
            state = "Awaiting confirmation"
        elif not prepared["valid"][t]:
            state = "Flat; no fresh qualifying range"
        else:
            state = "Flat; waiting for crossing"
        counts[state] += 1
    crossings = [t for t in prepared["cross_idx"] if lo <= t < hi]
    return dict(counts=dict(counts), raw_crossings=len(crossings),
        raw_crossings_while_held=sum(bool(sim["held"][t]) for t in crossings),
        raw_crossings_in_cooldown=sum(bool(cool[t] and not sim["held"][t]) for t in crossings),
        accepted_entries=sum(lo <= e["day"] < hi and e["side"] == "buy" for e in sim["events"]),
        note="Closing-state counts; 'no fresh range' does not rule out continuation eligibility. These are observed states, not a proof that changing a filter improves returns.")


def verification():
    declared, fits = source.verified_fits()
    manifest = json.loads((source.OUTPUT / "manifest.json").read_text())
    for name in ("asset-results.json", "information-coefficients.json", "gld-claim-audit.json", "sealed-fits.json", "protocol.json"):
        if source.study.digest(source.OUTPUT / name) != manifest[name]:
            raise ValueError("Retained evidence changed: " + name)
    return declared, fits, manifest


def protocol(declared, manifest):
    return dict(identity=OUT.name, created_utc=datetime.now(UTC).isoformat(),
        question="Show individually fitted short/long ETF results and diagnose weak cases without sacrificing stronger cases.",
        fit_identity="Reuse verified sealed independent per-ETF refits from October 21; no transfer of GLD parameters, no new test-period fitting. 241 candidates / ETF / domain / cutoff, six-friction training-finalist selection.",
        source_protocol_sha256=manifest["protocol.json"], published_batch=declared["data"]["batch"],
        source_results_sha256=manifest["asset-results.json"], sealed_fits_sha256=manifest["sealed-fits.json"],
        source_code_hashes={str(p.relative_to(ROOT)):source.study.digest(p) for p in (Path(__file__), TEMPLATE)},
        evaluation="Primary 2023-01-03..2026-10-16 after fitting through2022; earlier independent 2020-01-02..2022-12-30 after fitting through2019. 5bp/side and next-open execution. Retain all cost/delay sensitivities. Both periods previously inspected.",
        metrics="Cumulative from anchored NAV, CAGR252, Sharpe riskfree0. Standard Calmar=CAGR/abs(maxDD), unavailable for zero drawdown; retain legacy 3% denominator floor only as optimizer/archived metric. State IC21 vs next-open-to-close ETF return above BIL; approximate overlapping-label HAC p and Holm family adjustment.",
        diagnosis="Fixed sealed parameters. Replay every later ETF/domain; exact overnight/intraday captured and uninvested log-return decomposition with entry/exit fees. Trade stops reconstructed independently. Report closing states, trades, training comparison, yearly metrics and all friction cases. Distinguish absolute loss from opportunity cost and sparse evidence.",
        selection="Descriptive weak cases: six lowest later CAGRs plus four worst CAGR differences vs own buy-hold. Stronger cases: positive-return positive Sharpe differences. These post-result labels must not become asset gates or optimization targets.",
        improvements="Propose testable changes only; no new hyperparameter selection or variant winner based on the inspected evaluation sample. Future test must retain full pool, train-only selection, fixed-monthly/dynamic controls, net outcomes and good-case return/drawdown guardrails.")


def build_rows(fits, archived, information):
    ic = {(r["symbol"], r["domain"], r["era"]): r for r in information if r["method"] == "corrected_refit"}
    result = []
    for r in archived:
        if r["method"] != "corrected_refit" or r["cost_bp"] != 5 or r["delay"] != 0:
            continue
        fit = fits[r["symbol"]][r["domain"] + "_" + r["era"]]
        info = ic[r["symbol"], r["domain"], r["era"]]
        spec = source.old.SHORT_SPEC if r["domain"] == "short" else source.old.LONG_SPEC
        row = {k: v for k, v in r.items() if k not in ("method", "cost_bp", "delay", "buyhold")}
        row.update(cumulative=(1 + r["cagr"]) ** (r["sessions"] / 252) - 1,
            calmar_archived=r["calmar"], calmar=standard_calmar(r["cagr"], r["maxdd"]),
            bh_cumulative=(1 + r["buyhold"]["cagr"]) ** (r["sessions"] / 252) - 1,
            bh_cagr=r["buyhold"]["cagr"], bh_sharpe=r["buyhold"]["sharpe"], bh_maxdd=r["buyhold"]["maxdd"],
            cagr_difference=r["cagr"] - r["buyhold"]["cagr"], sharpe_difference=r["sharpe"] - r["buyhold"]["sharpe"],
            ic21=info["metrics"]["21"]["state"]["ic"], ic21_p=info["metrics"]["21"]["state"]["p"],
            ic21_holm_p=info.get("state21_holm_p"), ic5=info["metrics"]["5"]["state"]["ic"], ic63=info["metrics"]["63"]["state"]["ic"],
            ic_on=info["metrics"]["21"]["conditional_mean_excess_return"],
            training=fit["base"], parameters=fit["parameters"], decoded=spec.describe(fit["parameters"]),
            fit_candidates=fit["candidates"], fit_training_sessions=fit["training_sessions"])
        result.append(row)
    return result


def replay_rows(rows, archived):
    paths, diagnostics = {}, {}
    for symbol in sorted({r["symbol"] for r in rows}):
        data = source.study.load_asset(symbol)
        for kind, spec in (("short", source.old.SHORT_SPEC), ("long", source.old.LONG_SPEC)):
            r = next(r for r in rows if r["symbol"] == symbol and r["domain"] == kind and r["era"] == "late")
            f = source.old.Features.build(data, spec)
            prepared = source.old.prepare(f, r["parameters"])
            lo = int(np.flatnonzero(f.days >= np.datetime64("2023-01-03"))[0])
            hi = int(np.flatnonzero(f.days <= np.datetime64("2026-10-16"))[-1]) + 1
            sim = source.br.simulate(f, prepared, end=hi, cost_bp=5.)
            measured = source.stats.nav_stats(sim["nav"][lo - 1:hi])
            for k in CHECK_KEYS:
                np.testing.assert_allclose(measured[k], r[k], atol=1e-10, rtol=0)
            attribution = interval_accounting(f, sim, lo, hi)
            np.testing.assert_allclose(attribution["net_cumulative"], r["cumulative"], atol=1e-10, rtol=0)
            episodes = episode_details(f, prepared, sim, lo, hi)
            np.testing.assert_allclose(sum(e["evaluation_log_contribution"] for e in episodes), attribution["net_log_return"], atol=1e-10, rtol=0)
            years = []
            for year in range(2023, 2027):
                ix = np.flatnonzero((f.days >= np.datetime64(f"{year}-01-01")) & (f.days <= np.datetime64(f"{year}-12-31")) & (np.arange(len(f.days)) < hi))
                a, b = max(lo, int(ix[0])), min(hi, int(ix[-1]) + 1)
                years.append(dict(year=year, return_=float(sim["nav"][b - 1] / sim["nav"][a - 1] - 1),
                    bh_return=float(f.close[b - 1] / f.close[a - 1] - 1), exposure=float(sim["held"][a:b].mean())))
            frictions = [{k: s[k] for k in ("cost_bp", "delay", "cagr", "sharpe", "maxdd")} for s in archived
                if s["symbol"] == symbol and s["domain"] == kind and s["era"] == "late" and s["method"] == "corrected_refit"]
            diag = dict(accounting=attribution, states=closing_states(f, prepared, sim, lo, hi),
                episodes=episodes, years=years, frictions=frictions,
                losing_closed_trades=sum(e["closed"] and e["net_trade_return"] < 0 and not e["carried_in"] for e in episodes),
                initial_stop_exits=sum(e["closed"] and e["exit_kind"] == "Initial risk stop" for e in episodes),
                trail_exits=sum(e["closed"] and e["exit_kind"] == "Ratcheted trailing stop" for e in episodes),
                unarmed_episodes=sum(not e["armed"] for e in episodes),
                armed_but_initial_floor_exits=sum(e["closed"] and e["armed"] and e["exit_kind"] == "Initial risk stop" for e in episodes))
            diagnostics[symbol + "_" + kind] = diag
            paths[symbol + "_" + kind] = dict(days=f.days[lo - 1:hi].astype(str), nav=sim["nav"][lo - 1:hi] / sim["nav"][lo - 1],
                bh=f.close[lo - 1:hi] / f.close[lo - 1])
        print("Verified / diagnosed", symbol, flush=True)
    return diagnostics, paths


def families(rows):
    out = []
    for era in ("early", "late"):
        for domain in ("short", "long"):
            group = [r for r in rows if r["era"] == era and r["domain"] == domain and r["symbol"] != "BIL"]
            ic = [r["ic21"] for r in group if r["ic21"] is not None]
            out.append(dict(era=era, domain=domain, assets=len(group), positive_return=sum(r["cagr"] > 1e-8 for r in group),
                negative_return=sum(r["cagr"] < -1e-8 for r in group), beat_bh_cagr=sum(r["cagr_difference"] > 1e-8 for r in group),
                beat_bh_sharpe=sum(r["sharpe_difference"] > 1e-8 for r in group), median_cagr_gap=float(np.median([r["cagr_difference"] for r in group])),
                median_ic=float(np.median(ic)), insufficient_fit=sum(not r["fit_evidence"] for r in group),
                fewer_than_five_closed=sum(r["completed_trades"] < 5 for r in group)))
    return out


def selected_cases(rows):
    later = [r for r in rows if r["era"] == "late" and r["symbol"] != "BIL"]
    weak = sorted(later, key=lambda r:r["cagr"])[:6]
    weak += sorted(later, key=lambda r:r["cagr_difference"])[:4]
    weak_ids = list(dict.fromkeys(r["symbol"] + "_" + r["domain"] for r in weak))
    strong = sorted([r for r in later if r["cagr"] > 0 and r["sharpe_difference"] > 1e-8], key=lambda r:r["sharpe_difference"], reverse=True)[:5]
    return weak_ids, [r["symbol"] + "_" + r["domain"] for r in strong]


def charts(rows, paths, weak, strong):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    later = [r for r in rows if r["era"] == "late" and r["symbol"] != "BIL"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for kind, color in (("short", "#2879a7"), ("long", "#c57c23")):
        group = [r for r in later if r["domain"] == kind]
        axes[0].scatter([r["exposure"] * 100 for r in group], [r["cagr_difference"] * 100 for r in group], color=color, s=28, alpha=.8, label=kind)
        axes[1].scatter([r["bh_cagr"] * 100 for r in group], [r["cagr"] * 100 for r in group], color=color, s=28, alpha=.8, label=kind)
        for r in group:
            if r["symbol"] + "_" + kind in weak[:4] + strong[:3] + ["EWY_long", "SLV_short"]:
                axes[0].annotate(r["symbol"] + " " + kind[0].upper(), (r["exposure"] * 100, r["cagr_difference"] * 100), xytext=(4, 4), textcoords="offset points", fontsize=7)
    axes[0].axhline(0, color="#a0aab5", lw=1)
    axes[0].set(title="Return shortfall is not just trading cost", xlabel="Sessions invested (%)", ylabel="Strategy CAGR minus own ETF CAGR (pp)")
    axes[1].plot([-15, 50], [-15, 50], color="#8c9ba8", ls="--", lw=1)
    axes[1].set(title="Positive returns can still miss most of the ETF rally", xlabel="Buy-and-hold CAGR (%)", ylabel="Individually fitted strategy CAGR (%)")
    for ax in axes:
        ax.legend(); ax.grid(alpha=.16)
    fig.savefig(OUT / "pool-comparison.png", dpi=160)
    plt.close(fig)
    examples = list(dict.fromkeys(weak[:5] + ["EWY_long", "SLV_short", "GLD_long"]))
    fig, axes = plt.subplots(4, 2, figsize=(14, 12), layout="constrained")
    for ax, key in zip(axes.flat, examples, strict=True):
        p = paths[key]
        dates = np.array(p["days"], dtype="datetime64[D]")
        ax.plot(dates, 100 * p["nav"], color="#2879a7", label="Own-ETF fitted strategy")
        ax.plot(dates, 100 * p["bh"], color="#939aa3", label="Own ETF buy/hold")
        ax.axhline(100, color="#c9d0d6", lw=.6)
        ax.set_title(key.replace("_", " · "), loc="left")
        ax.grid(alpha=.15)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_ylabel("Value from 100")
    axes.flat[0].legend(fontsize=8)
    fig.savefig(OUT / "weak-and-strong-paths.png", dpi=145)
    plt.close(fig)


def exports(payload):
    flat_fields = ["symbol", "domain", "era", "cumulative", "cagr", "sharpe", "calmar", "maxdd", "ic21", "ic21_p", "ic21_holm_p", "alpha", "p", "alpha_holm_p", "bh_cumulative", "bh_cagr", "bh_sharpe", "bh_maxdd", "cagr_difference", "sharpe_difference", "exposure", "completed_trades", "fit_evidence", "fit_candidates", "fit_training_sessions"]
    with (OUT / "individual-etf-results.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=flat_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(payload["rows"])
    page = TEMPLATE.read_text(encoding="utf-8").replace("__REPORT_DATA__", json.dumps(payload, separators=(",", ":"), allow_nan=False))
    (OUT / "index.html").write_text(page, encoding="utf-8")


def main():
    declared, fits, manifest = verification()
    OUT.mkdir(parents=True, exist_ok=True)
    source.study.write(OUT / "protocol.json", protocol(declared, manifest))
    archived = json.loads((source.OUTPUT / "asset-results.json").read_text())["rows"]
    information = json.loads((source.OUTPUT / "information-coefficients.json").read_text())
    rows = build_rows(fits, archived, information)
    diagnostics, paths = replay_rows(rows, archived)
    weak, strong = selected_cases(rows)
    original_gld = [r for r in json.loads((source.OUTPUT / "gld-claim-audit.json").read_text())
                    if r["phase"] == "original" and r["method"] == "corrected_original" and r["cost_bp"] == 5 and r["delay"] == 0]
    payload = clean(dict(rows=rows, diagnostics=diagnostics, families=families(rows), weak=weak, strong=strong, original_gld=original_gld,
        unavailable=[dict(symbol=s, fit=k, reason=v["reason"]) for s,f in fits.items() for k,v in f.items() if not v["available"]]))
    source.study.write(OUT / "results.json", payload)
    charts(rows, paths, weak, strong)
    exports(payload)
    source.study.write(OUT / "validation.json", dict(source_inputs_and_sealed_fits_verified=True,
        available_independent_fits=len(rows), later_replays=len(diagnostics), all_saved_return_metrics_reproduced=True,
        interval_accounting_max_error=max(v["accounting"]["max_daily_accounting_error"] for v in diagnostics.values()),
        all_trade_stop_components_reconciled=True, trade_contributions_sum_to_nav=True,
        standard_calmar="Actual maximum drawdown; optimizer's 3% floor retained only in archived fit scores",
        no_new_fitting="Verified retained individual refits; no GLD transfer and no evaluation-based parameter changes"))
    source.study.write(OUT / "manifest.json", {p.name:source.study.digest(p) for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"})
    print(json.dumps(dict(report=str(OUT / "index.html"), families=payload["families"], weak=weak, strong=strong), indent=2), flush=True)


if __name__ == "__main__":
    main()
