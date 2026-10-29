"""Replay the full pool and diagnose actual trend exits; no parameter selection."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

import retest_postbreakout_trend as study
from build_etf_breakout_failure_report import closing_states, interval_accounting

OUT = study.ROOT / "research/trend-exit-failure-review-20261023-v1"
TEMPLATE = study.ROOT / "scripts/assets/trend-exit-failure-review.html"
RULE = dict(lookback=21, buffer_atr=1.)


def independent_support(close, entry, t, rule, atr):
    """Separate least-squares/quantile implementation, excluding today's close."""
    if t - entry < 5 or not np.isfinite(atr):
        return None
    y = np.log(close[max(entry, t - rule["lookback"]):t])
    x = np.arange(len(y), dtype=float)
    intercept, slope = np.linalg.lstsq(np.column_stack((np.ones(len(y)), x)), y, rcond=None)[0]
    # Symmetric or constant data can produce a least-squares rounding residue.
    # 1e-14 log-price/session is below economically meaningful slope precision.
    if slope <= 1e-14:
        return None
    residual = np.quantile(y - intercept - slope * x, .1)
    return float(np.exp(intercept + slope * len(y) + residual) - rule["buffer_atr"] * atr)


def inspect_episodes(f, prepared, sim, lo, hi, fee=.0005):
    """Rebuild stops; distinguish active trend protection from mere formation.

    Stop prices are closing decision boundaries, never assumed execution prices.
    Trade contributions include carried positions and an open terminal position.
    """
    p, rule = prepared["parameters"], prepared["trend_rule"]
    records, checked, max_error = [], 0, 0.
    for e in sim["episodes"]:
        a, x = e["entry_index"], e["exit_index"]
        if a >= hi or (x is not None and x < lo):
            continue
        closed = x is not None and x < hi
        decision = e.get("exit_signal")
        if decision is not None and decision >= hi:
            decision = None
        last = hi - 1 if decision is None else decision
        initial = e["entry"] - p[10] * e["atr"]
        if p[11] >= 0:
            initial = max(initial, e["u"] - p[11] * e["atr"])
        trend, stop, first = None, initial, None
        last_held = x - 1 if closed else hi - 1
        for t in range(a, last_held + 1):
            if t <= last:
                candidate = independent_support(f.close, a, t, rule, prepared["atr"][t - 1])
                if candidate is not None:
                    first = t if first is None else first
                    trend = max(trend, candidate) if trend is not None else candidate
                    stop = max(stop, trend)
            actual = sim["stop"][t]
            max_error = max(max_error, abs(stop - actual))
            np.testing.assert_allclose(actual, stop, atol=1e-8, rtol=0)
            np.testing.assert_allclose(sim["trend_level"][t], np.nan if trend is None else trend,
                                       atol=1e-8, rtol=0, equal_nan=True)
            checked += 1
        mark = e["exit_price"] if closed else float(f.close[hi - 1])
        net = mark / e["entry"] * (1 - fee if closed else 1) / (1 + fee) - 1
        start, end = max(lo, a), min(hi, x + 1 if closed else hi)
        contribution = float(np.log(sim["nav"][end - 1] / sim["nav"][start - 1]))
        reason = e.get("exit_reason", "Open at cutoff") if e.get("exit_signal", hi) < hi else "Open at cutoff"
        if reason == "stop":
            reason = "Trend support" if stop > initial + 1e-8 else "Initial risk"
        date = lambda i: str(f.days[i]) if i is not None else None
        records.append(dict(entry=date(a), exit=date(x) if closed else None, entry_index=a,
            exit_index=x if closed else None, decision=date(decision),
            decision_index=decision, crossing=date(e["crossing"]), confirmation=date(e["confirmation"]),
            entry_price=e["entry"], exit_or_mark=mark, net_return=net, evaluation_log_contribution=contribution,
            carried=a < lo, closed=closed, holding_sessions=(x if closed else hi) - a,
            initial_floor=initial, initial_risk=1 - initial / e["entry"], first_support=date(first),
            support_delay_sessions=first - a if first is not None else None,
            trend_formed=first is not None, exit_kind=reason, last_stop=stop,
            last_trend=trend, peak_close_gain=float(f.close[a:last + 1].max() / e["entry"] - 1),
            decision_close=float(f.close[last]),
            decision_to_fill_gap=mark / f.close[last] - 1 if closed else None,
            fill_vs_stop=mark / stop - 1 if closed and reason in ("Trend support", "Initial risk") else None,
            entry_from_crossing=float(e["entry"] / f.close[e["crossing"]] - 1)))
    target = float(np.log(sim["nav"][hi - 1] / sim["nav"][lo - 1]))
    np.testing.assert_allclose(sum(e["evaluation_log_contribution"] for e in records), target, atol=2e-12, rtol=0)
    return records, checked, max_error


def yearly(f, sim, base, lo, hi):
    result = []
    for year in sorted(set(str(d)[:4] for d in f.days[lo:hi])):
        ix = np.flatnonzero((f.days >= np.datetime64(year + "-01-01")) & (f.days < np.datetime64(str(int(year) + 1) + "-01-01")))
        a, b = max(lo, int(ix[0])), min(hi, int(ix[-1]) + 1)
        result.append(dict(year=year, trend=sim["nav"][b - 1] / sim["nav"][a - 1] - 1,
            baseline=base["nav"][b - 1] / base["nav"][a - 1] - 1, buyhold=f.close[b - 1] / f.close[a - 1] - 1,
            exposure=float(sim["held"][a:b].mean())))
    return result


def selection_diagnosis(fit):
    """Describe why the sealed finalists did not replace the existing exit."""
    base = fit["finalists"]["0"]["training"]
    result = []
    for key, item in fit["finalists"].items():
        if key == "0":
            continue
        failures = []
        if any(r["closed"] < 5 or r["exposure"] < .05 for r in item["training"]):
            failures.append("Too few trades/exposure")
        if any(r["cagr"] < b["cagr"] - .01 for r, b in zip(item["training"], base, strict=True)):
            failures.append("Training return loss >1 pp/year")
        if any(r["maxdd"] < b["maxdd"] - .02 for r, b in zip(item["training"], base, strict=True)):
            failures.append("Training drawdown deterioration >2 pp")
        if min(r["score"] for r in item["training"]) <= min(r["score"] for r in base) + .01:
            failures.append("Insufficient worst-friction utility gain")
        result.append(dict(rule=item["components"]["rule"], failures=failures))
    return result


def build():
    fits = study.verified()
    upstream = json.loads((study.OUT / "manifest.json").read_text())
    for name, expected in upstream["files"].items():
        if study.study.digest(study.OUT / name) != expected:
            raise ValueError("Upstream artifact changed: " + name)
    all_rows = json.loads((study.OUT / "asset-results.json").read_text())
    primary = [r for r in all_rows if r["cost_bp"] == 5 and r["delay"] == 0]
    lookup = {(r["symbol"], r["domain"], r["era"], r["variant"]): r for r in primary}
    rows = []
    for r in primary:
        if r["variant"] != "shared_trend":
            continue
        b = lookup[r["symbol"], r["domain"], r["era"], "baseline"]
        rows.append(dict(r, baseline=b,
            bh_cumulative=(1 + r["buyhold"]["cagr"]) ** (r["sessions"] / 252) - 1,
            difference=r["cumulative"] - b["cumulative"]))
    late = [r for r in rows if r["era"] == "late" and r["symbol"] != "BIL"]
    worst = sorted(late, key=lambda r: r["cumulative"])
    damaged = sorted(late, key=lambda r: r["difference"])
    focus = list(dict.fromkeys(r["symbol"] + "_" + r["domain"] for r in [*worst[:2], damaged[0]]))
    results, charts = {}, {}
    metric_error, boundary_error, ledger_error, boundary_sessions = 0., 0., 0., 0
    bill = study.study.load_asset("BIL")
    bill_lookup = {str(d): i for i, d in enumerate(bill["days"])}
    for symbol in sorted(fits):
        data = study.study.load_asset(symbol)
        mapped = {k: np.array([bill[k][bill_lookup[str(d)]] if str(d) in bill_lookup else np.nan for d in data["days"]])
                  for k in ("open", "close")}
        for domain, spec in (("short", study.old.SHORT_SPEC), ("long", study.old.LONG_SPEC)):
            fit = fits[symbol][domain + "_late"]
            f = study.old.Features.build(data, spec)
            lo, hi = int(np.flatnonzero(f.days >= np.datetime64("2023-01-03"))[0]), len(f.days)
            prepared = study.model.prepare(f, fit["parameters"], RULE)
            sim = study.model.simulate(f, prepared, end=hi)
            base = study.model.simulate(f, study.model.prepare(f, fit["parameters"], None), end=hi)
            for name, path in (("shared_trend", sim), ("baseline", base)):
                saved = lookup[symbol, domain, "late", name]
                actual = study.source.measure(f, path, path["desired"], path["held"], mapped, lo, hi)
                for field in ("cagr", "sharpe", "maxdd", "alpha", "exposure", "completed_trades"):
                    if actual[field] is None or saved[field] is None:
                        if actual[field] != saved[field]:
                            raise ValueError("Missing metric mismatch")
                        continue
                    error = abs(actual[field] - saved[field])
                    metric_error = max(metric_error, error)
                    if error > 1e-10:
                        raise ValueError("Saved metric mismatch: " + symbol + domain + field)
                _, _, error = study.ledger(f, path, 5)
                ledger_error = max(ledger_error, error)
            episodes, count, error = inspect_episodes(f, prepared, sim, lo, hi)
            boundary_sessions += count
            boundary_error = max(boundary_error, error)
            account = interval_accounting(f, sim, lo, hi)
            key = symbol + "_" + domain
            results[key] = dict(symbol=symbol, domain=domain, trades=episodes,
                accounting=account, baseline_accounting=interval_accounting(f, base, lo, hi),
                states=closing_states(f, prepared, sim, lo, hi), yearly=yearly(f, sim, base, lo, hi),
                continuation=bool(fit["parameters"][24]), cooldown=int(fit["parameters"][23]),
                confirmation_sessions=int(fit["parameters"][6]), atr_sessions=spec.atr_periods[int(fit["parameters"][4])],
                rejected_finalists=selection_diagnosis(fit))
            if key in focus:
                start = lo - 1
                initial = np.full(hi, np.nan)
                for e in episodes:
                    initial[e["entry_index"]:e["exit_index"] or hi] = e["initial_floor"]
                charts[key] = dict(days=f.days[start:hi].astype(str), close=f.close[start:hi],
                    stop=sim["stop"][start:hi], trend=sim["trend_level"][start:hi], initial=initial[start:hi],
                    nav=100 * sim["nav"][start:hi] / sim["nav"][start],
                    baseline=100 * base["nav"][start:hi] / base["nav"][start],
                    buyhold=100 * f.close[start:hi] / f.close[start], offset=start)
        print("Replayed and inspected", symbol, flush=True)
    validation = dict(replayed_later_fits=104, replayed_paths=208, saved_metric_max_error=metric_error,
        independently_rebuilt_stop_sessions=boundary_sessions, stop_max_absolute_error=boundary_error,
        event_ledger_max_relative_error=ledger_error,
        max_daily_log_accounting_error=max(v["accounting"]["max_daily_accounting_error"] for v in results.values()),
        upstream_manifest_verified=True, frozen_protocol_and_52_fit_hashes_verified=True)
    protocol = dict(question="Full-pool actual trend exits and worst-case inspection; no new fitting or strategy changes.",
        published_batch=json.loads((study.OUT / "protocol.json").read_text())["published_batch"],
        source_protocol_sha256=study.study.digest(study.OUT / "protocol.json"),
        source_manifest_sha256=study.study.digest(study.OUT / "manifest.json"),
        source_fit_manifest_sha256=study.study.digest(study.OUT / "fit-manifest.json"), rule=RULE,
        fitting="Each ETF's sealed independently fitted entry/risk anchor. Fixed21/1 exit control, not individually selected exit. All104 later training selections retained the existing exit.",
        ranking="All51 risky ETFs x2 domains, including inadequate-training rows with flags; BIL cash reference excluded from rankings. Worst net cumulative, largest change vs existing fit and largest gap vs buy-hold are separate descriptive ranks. Focus is two worst losses and largest deterioration.",
        inspection="Replay104 later actual-control and104 baseline paths. Independent least-squares support reconstruction, ledger and exact log accounting. Earlier metrics and all six frictions are verified saved evidence. No new portfolio experiment; prior study retains dynamic/monthly controls. Post-result inspection is not a selection rule.",
        authority="Research only, previously inspected history. No promotion, deployment or allocation changes.")
    stress = [r for r in all_rows if r["variant"] == "shared_trend"]
    data = dict(rows=rows, details=results, charts=charts, focus=focus, stress=stress, validation=validation, protocol=protocol)
    OUT.mkdir(parents=True, exist_ok=True)
    study.write(OUT / "results.json", data)
    study.write(OUT / "validation.json", validation)
    study.write(OUT / "protocol.json", protocol)
    fields = ("symbol", "domain", "era", "cumulative", "cagr", "sharpe", "calmar", "maxdd", "alpha", "exposure", "completed_trades", "training_evidence", "bh_cumulative", "difference")
    with (OUT / "full-etf-table.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[*fields, "baseline_cumulative", "ic21"])
        writer.writeheader()
        writer.writerows({**{k: r[k] for k in fields}, "baseline_cumulative": r["baseline"]["cumulative"], "ic21": r["ic21"]["ic"]} for r in rows)
    page = TEMPLATE.read_text(encoding="utf-8").replace("__REPORT_DATA__", json.dumps(study.clean(data), separators=(",", ":"), allow_nan=False).replace("</", "<\\/"))
    (OUT / "index.html").write_text(page, encoding="utf-8")
    figures(study.clean(data))
    study.write(OUT / "manifest.json", dict(files={p.name: study.study.digest(p) for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"},
        code={str(p.relative_to(study.ROOT)).replace(chr(92), "/"): study.study.digest(p) for p in (Path(__file__), TEMPLATE)}))
    print(json.dumps(validation, indent=2), flush=True)


def figures(data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    for key in data["focus"]:
        chart, detail = data["charts"][key], data["details"][key]
        days = np.array(chart["days"], dtype="datetime64[D]")
        fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained", height_ratios=[1.4, 1])
        ax = axes[0]
        for field, color, label, ls in (("close", "#183b56", "Adjusted close", "-"), ("stop", "#c1583b", "Effective exit level", "-"), ("trend", "#168775", "Ratcheted trend support", "--")):
            ax.plot(days, chart[field], color=color, lw=1.2, ls=ls, label=label)
        for e in detail["trades"]:
            ax.scatter(np.datetime64(e["entry"]), e["entry_price"], marker="^", color="#168775", s=40, zorder=4)
            if e["closed"]:
                ax.scatter(np.datetime64(e["exit"]), e["exit_or_mark"], marker="v", color="#bd4252", s=40, zorder=4)
        ax.set_ylabel("Adjusted USD")
        ax.legend(fontsize=8, loc="upper right" if key == "TLT_short" else "upper left")
        ax.set_title("Actual next-open buys / sells and closing exit levels", loc="left", fontsize=11)
        ax = axes[1]
        for field, color, label in (("nav", "#168775", "Trend exit"), ("baseline", "#8a659e", "Previous own-ETF exit"), ("buyhold", "#8195a5", "Buy and hold")):
            ax.plot(days, chart[field], label=label, color=color, lw=1.4)
        ax.set_ylabel("Value from 100")
        ax.legend(fontsize=8, loc="upper right" if key == "TLT_short" else "upper left")
        for ax in axes:
            ax.grid(alpha=.15)
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        fig.suptitle(f"{key.replace('_', ' ')} | Fixed 21-session / 1 ATR exit\n2023-Jan-03 to 2026-Oct-16 | 5 bp per side; cash earns 0", fontsize=13)
        fig.savefig(OUT / (key.lower() + ".png"), dpi=145)
        plt.close(fig)
    # Zoom into SLV's largest loss, with the separate initial-risk floor visible.
    chart, detail = data["charts"][data["focus"][0]], data["details"][data["focus"][0]]
    e = min(detail["trades"], key=lambda e: e["net_return"])
    a, b = max(0, e["entry_index"] - chart["offset"] - 12), min(len(chart["days"]), e["exit_index"] - chart["offset"] + 12)
    days = np.array(chart["days"], dtype="datetime64[D]")
    fig, ax = plt.subplots(figsize=(12, 5), layout="constrained")
    for field, color, label, ls in (("close", "#183b56", "Adjusted close", "-"), ("initial", "#c69b50", "Initial risk floor", ":"), ("stop", "#c1583b", "Effective exit level", "-"), ("trend", "#168775", "Trend support", "--")):
        ax.plot(days[a:b], chart[field][a:b], color=color, lw=1.6, ls=ls, label=label)
    ax.scatter(np.datetime64(e["entry"]), e["entry_price"], marker="^", s=70, color="#168775", zorder=4)
    ax.scatter(np.datetime64(e["exit"]), e["exit_or_mark"], marker="v", s=70, color="#bd4252", zorder=4)
    ax.annotate(f"Buy {e['entry']}\n{e['entry_price']:.2f}", (np.datetime64(e["entry"]), e["entry_price"]), xytext=(8, 12), textcoords="offset points", fontsize=9)
    ax.annotate(f"Sell {e['exit']}\n{e['net_return']:+.2%} after fees", (np.datetime64(e["exit"]), e["exit_or_mark"]), xytext=(-135, -35), textcoords="offset points", fontsize=9)
    ax.set_title(f"{data['focus'][0].replace('_', ' ')}: largest losing trade | support first forms {e['first_support']}", loc="left", fontsize=12)
    ax.set_ylabel("Adjusted USD")
    ax.grid(alpha=.15)
    ax.legend(fontsize=9, loc="lower left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.savefig(OUT / "worst-trade.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    build()
