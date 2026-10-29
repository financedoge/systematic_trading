"""Report for the operator's post-entry upward-trend failure exit hypothesis."""
import csv
import json
from pathlib import Path

import numpy as np

import retest_postbreakout_trend as study

OUT = study.OUT


def summaries(rows, portfolios):
    lookup = {(r["symbol"], r["domain"], r["era"], r["cost_bp"], r["delay"], r["variant"]): r for r in rows}
    families = []
    for era in ("late", "early"):
        for variant in (*study.FAMILIES, "shared_trend"):
            for cost, delay in study.study.FRICTIONS:
                candidates = [r for r in rows if r["era"] == era and r["variant"] == variant
                    and r["cost_bp"] == cost and r["delay"] == delay and r["symbol"] != "BIL" and r["training_evidence"]]
                bases = [lookup[(r["symbol"], r["domain"], era, cost, delay, "baseline")] for r in candidates]
                dc = np.array([r["cagr"] - b["cagr"] for r, b in zip(candidates, bases, strict=True)])
                ds = np.array([r["sharpe"] - b["sharpe"] for r, b in zip(candidates, bases, strict=True)])
                dd = np.array([r["maxdd"] - b["maxdd"] for r, b in zip(candidates, bases, strict=True)])
                med = lambda rr, k: float(np.median([r[k] for r in rr]))
                q = lambda rr: float(np.quantile([r["cagr"] for r in rr], .25))
                guard = float(np.mean((dc >= -.01 - 1e-12) & (dd >= -.02 - 1e-12)))
                sharpe_gain, qgain = med(candidates, "sharpe") - med(bases, "sharpe"), q(candidates) - q(bases)
                families.append(dict(era=era, variant=variant, cost_bp=cost, delay=delay, cases=len(candidates),
                    median_cagr_difference=float(np.median(dc)), median_paired_sharpe_difference=float(np.median(ds)),
                    median_sharpe_gain=sharpe_gain, lower_quartile_cagr_gain=qgain, guard_fraction=guard,
                    improved_cagr=int((dc > 1e-10).sum()), impaired_cagr=int((dc < -1e-10).sum()),
                    unchanged=int((np.abs(dc) <= 1e-10).sum()), passed=sharpe_gain > 1e-10 and qgain > 1e-10 and guard >= .90))
    gates = []
    index = {(r["era"], r["scenario"], r["cost_bp"], r["delay"]): r for r in portfolios}
    for r in portfolios:
        if not r["scenario"].startswith("trend_fit_"):
            continue
        baseline = r["scenario"].replace("trend_fit_", "baseline_")
        reference = "FR25" if r["era"] == "late" else "momentum_" + r["scenario"].rsplit("_", 1)[1]
        comparisons = []
        for name in (baseline, reference):
            b = index[(r["era"], name, r["cost_bp"], r["delay"])]
            checks = dict(sharpe=r["sharpe"] > b["sharpe"] + 1e-10, cagr=r["cagr"] >= b["cagr"] - .01,
                          drawdown=r["max_drawdown"] >= b["max_drawdown"] - 1e-12)
            comparisons.append(dict(reference=name, **checks, passed=all(checks.values())))
        gates.append(dict(era=r["era"], scenario=r["scenario"], cost_bp=r["cost_bp"], delay=r["delay"],
                          comparisons=comparisons, passed=all(c["passed"] for c in comparisons)))
    return families, gates


def gld_original():
    declared, _ = study.source.verified_fits()
    fdata = study.study.load_asset("GLD")
    billdata = study.study.load_asset("BIL")
    lookup = {str(d): i for i, d in enumerate(billdata["days"])}
    bill = {k: np.array([billdata[k][lookup[str(d)]] if str(d) in lookup else np.nan for d in fdata["days"]]) for k in ("open", "close")}
    rows = []
    for domain, spec in (("short", study.old.SHORT_SPEC), ("long", study.old.LONG_SPEC)):
        f = study.old.Features.build(fdata, spec)
        vector = declared["gld_anchors"][domain + "_original"]["parameters"]
        lo = int(np.flatnonzero(f.days >= np.datetime64("2023-01-03"))[0])
        hi = len(f.days)
        for variant, rule in (("original", None), ("shared_trend", dict(lookback=21, buffer_atr=1.))):
            p = study.model.prepare(f, vector, rule)
            for cost, delay in study.study.FRICTIONS:
                sim = study.model.simulate(f, p, cost_bp=cost, delay=delay)
                r = study.source.measure(f, sim, sim["desired"], sim["held"], bill, lo, hi)
                forward = study.stats.forward_returns(f.open, f.close, bill["open"], bill["close"], 21)
                rows.append(dict(domain=domain, variant=variant, cost_bp=cost, delay=delay, **r,
                    cumulative=sim["nav"][hi - 1] / sim["nav"][lo - 1] - 1,
                    ic21=study.stats.rank_ic(sim["desired"][lo:hi], forward[lo:hi], 21)))
    study.write(OUT / "original-gld-sensitivity.json", rows)
    return rows


def plots():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    evidence = []
    for symbol, domain, spec in (("GLD", "long", study.old.LONG_SPEC), ("IAT", "short", study.old.SHORT_SPEC)):
        fit = json.loads((study.WORK / "fits" / (symbol + ".json")).read_text())["fits"][domain + "_late"]
        f = study.old.Features.build(study.study.load_asset(symbol), spec)
        lo = int(np.flatnonzero(f.days >= np.datetime64("2023-01-03"))[0])
        rules = dict(baseline=None, trend_fit=fit["choices"]["trend_fit"]["components"]["rule"], shared_trend=dict(lookback=21, buffer_atr=1.))
        sims = {k: study.model.simulate(f, study.model.prepare(f, fit["parameters"], rule)) for k, rule in rules.items()}
        sim = sims["shared_trend"]
        episodes = [e for e in sim["episodes"] if e["entry_index"] >= lo]
        first = episodes[0]["entry_index"] if episodes else lo
        start, end = max(lo - 1, first - 10), min(len(f.days), first + 190)
        fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained", gridspec_kw={"height_ratios": [1.4, 1]})
        ax = axes[0]
        ax.plot(f.days[start:end], f.close[start:end], color="#173a57", lw=1.4, label="Adjusted close")
        ax.plot(f.days[start:end], sim["stop"][start:end], color="#b45443", lw=1.5, label="Effective exit level (initial risk or trend support)")
        ax.plot(f.days[start:end], sim["trend_level"][start:end], color="#138c75", ls="--", lw=1.4, label="Ratcheted rising-trend support")
        for e in episodes:
            entry, exit_ = e["entry_index"], e["exit_index"]
            if start <= entry < end:
                ax.scatter(f.days[entry], e["entry"], color="#16855d", marker="^", s=55, zorder=5)
            if exit_ is not None and start <= exit_ < end:
                ax.scatter(f.days[exit_], e["exit_price"], color="#be364d", marker="v", s=55, zorder=5)
        ax.set_title(f"{symbol} {domain}: fixed 21-session / 1 ATR rule · first later entry and following 190 sessions", loc="left", fontsize=11)
        ax.set_ylabel("Adjusted USD")
        ax.legend(fontsize=8, loc="best")
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.grid(alpha=.15)
        ax.text(.01, .02, "Triangles: actual next-open buys ▲ / sells ▼. The support is fitted through the previous close.", transform=ax.transAxes, fontsize=8)
        ax = axes[1]
        for key, color, label in (("baseline", "#6c7f90", "Existing own-ETF fit"), ("shared_trend", "#138c75", "Fixed 21 / 1 trend rule"), ("trend_fit", "#b87025", "Training-selected rule (may retain baseline)")):
            nav = sims[key]["nav"][lo - 1:] / sims[key]["nav"][lo - 1] * 100
            ax.plot(f.days[lo - 1:], nav, label=label, color=color, lw=1.5, ls="--" if key == "trend_fit" else "-")
        ax.set_ylabel("Value from 100, after costs")
        ax.set_title("Full evaluation: 2023–October 16, 2026 · 5 bp per side · next open", loc="left", fontsize=11)
        ax.legend(fontsize=8)
        ax.grid(alpha=.15)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        fig.suptitle("Exit on failure of the new rising trend—not the first lower close", fontsize=14)
        fig.savefig(OUT / f"{symbol.lower()}-trend-exit.png", dpi=160)
        plt.close(fig)
        records = [{k: e[k] for k in ("entry_index", "entry", "exit_index", "exit_price", "exit_signal", "exit_reason") if k in e} for e in episodes]
        evidence.append(dict(symbol=symbol, domain=domain, displayed_rule=rules["shared_trend"], selected_rule=rules["trend_fit"],
            days=f.days[start:end].astype(str), close=f.close[start:end], stop=sim["stop"][start:end],
            trend_level=sim["trend_level"][start:end], episodes=records))
    study.write(OUT / "plot-evidence.json", evidence)


def main():
    study.verified()
    rows = json.loads((OUT / "asset-results.json").read_text())
    ports = json.loads((OUT / "portfolio-results.json").read_text())
    choices = json.loads((OUT / "selected-components.json").read_text())
    families, gates = summaries(rows, ports)
    summary = dict(families=families, portfolio_gates=gates)
    study.write(OUT / "summary.json", summary)
    primary = [r for r in rows if r["cost_bp"] == 5 and r["delay"] == 0]
    fields = ("symbol", "domain", "era", "variant", "cumulative", "cagr", "sharpe", "calmar", "maxdd", "alpha", "exposure", "completed_trades", "turnover_annual", "cost_bp_annual")
    with (OUT / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[*fields, "ic21"])
        writer.writeheader()
        writer.writerows({**{k: r[k] for k in fields}, "ic21": r["ic21"]["ic"]} for r in primary)
    data = dict(rows=primary, stress=rows, choices=choices, portfolios=ports, summary=summary,
        original_gld=gld_original(), validation=json.loads((OUT / "validation.json").read_text()),
        native=json.loads((OUT / "native-checks.json").read_text()) if (OUT / "native-checks.json").exists() else [])
    template = study.ROOT / "scripts/assets/postbreakout-trend-review.html"
    page = template.read_text(encoding="utf-8").replace("__REPORT_DATA__", json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/"))
    (OUT / "index.html").write_text(page, encoding="utf-8")
    plots()
    names = [p.name for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"]
    study.write(OUT / "manifest.json", dict(files={name: study.study.digest(OUT / name) for name in names},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92), '/'): study.study.digest(p) for p in
            (Path(__file__), template, study.ROOT / "scripts/validate_postbreakout_trend.py")}))
    print(json.dumps(dict(families=[r for r in families if r["cost_bp"] == 5 and r["delay"] == 0],
        portfolio_passes=sum(g["passed"] for g in gates), portfolio_cases=len(gates)), indent=2))


if __name__ == "__main__":
    main()

