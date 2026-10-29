"""Compact full-pool evidence and standalone component-comparison report."""
from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np

import retest_adaptive_breakout as study

OUT = study.OUT


def summaries(rows, portfolios):
    lookup = {(r["symbol"], r["domain"], r["era"], r["cost_bp"], r["delay"], r["variant"]): r for r in rows}
    families = []
    for era in ("late", "early"):
        for variant in (*study.FAMILIES, "first_lower_control"):
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
        if not r["scenario"].startswith("joint_fit_"):
            continue
        baseline = r["scenario"].replace("joint_fit_", "baseline_")
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


def plots(rows, regimes):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    later = [r for r in rows if r["era"] == "late" and r["cost_bp"] == 5 and r["delay"] == 0 and r["symbol"] != "BIL"]
    base = {(r["symbol"], r["domain"]): r for r in later if r["variant"] == "baseline"}
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout="constrained")
    for ax, variant, title in zip(axes, ("first_lower_control", "joint_fit"),
        ("First lower close after 1 ATR gain: imposed on every ETF", "Components selected separately on each ETF's training data"), strict=True):
        for domain, color in (("short", "#2563eb"), ("long", "#059669")):
            group = [r for r in later if r["variant"] == variant and r["domain"] == domain]
            x = [100 * (r["cagr"] - base[(r["symbol"], domain)]["cagr"]) for r in group]
            y = [r["sharpe"] - base[(r["symbol"], domain)]["sharpe"] for r in group]
            ax.scatter(x, y, s=28, alpha=.65, label=domain, color=color)
            for r, xx, yy in zip(group, x, y, strict=True):
                labels = ({("GLD", "long"), ("IAT", "short"), ("XLY", "short"), ("EWY", "long"), ("SLV", "long")}
                          if variant == "first_lower_control" else {("EMB", "short"), ("IWM", "short"), ("TIP", "short")})
                if (r["symbol"], domain) in labels:
                    ax.annotate(r["symbol"] + " " + domain, (xx, yy), fontsize=8, xytext=(4, 4), textcoords="offset points")
        ax.axhline(0, color="#64748b", lw=.8)
        ax.axvline(0, color="#64748b", lw=.8)
        ax.set(title=title, xlabel="CAGR change versus existing own-ETF fit (percentage points)", ylabel="Net Sharpe change")
        ax.grid(alpha=.15)
        ax.legend()
        ax.margins(x=.12)
        if variant == "joint_fit":
            ax.text(.03, .04, "GLD, IAT, XLY, EWY and SLV examples retain baseline", transform=ax.transAxes, fontsize=8)
    fig.suptitle("Tighter exits and redesigned entries: benefit versus damage, 2023–Oct 16, 2026\n5 bp per side, next open; 102 risky ETF/domain cases; zero idle-cash interest", fontsize=12)
    fig.savefig(OUT / "component-tradeoffs.png", dpi=160)
    plt.close(fig)


def range_illustrations():
    """First later raw crossing for two training-selected new range examples."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout="constrained")
    records = []
    for ax, symbol in zip(axes, ("EMB", "TIP"), strict=True):
        fit = json.loads((study.WORK / "fits" / (symbol + ".json")).read_text())["fits"]["short_late"]
        choice = fit["choices"]["joint_fit"]["components"]
        f = study.old.Features.build(study.study.load_asset(symbol))
        p = study.model.prepare(f, fit["parameters"], choice["range"], choice["trend"], choice["exit"])
        old = study.old.prepare(f, fit["parameters"])
        crosses = np.flatnonzero(p["cross"] & (f.days >= np.datetime64("2023-01-03")))
        if not len(crosses):
            ax.text(.1, .5, symbol + ": no later crossing", transform=ax.transAxes)
            continue
        t = int(crosses[0])
        kind, raw = choice["range"].split("_")
        length = int(raw)
        lo, hi = max(0, t - length - 15), min(len(f.days), t + 30)
        ax.plot(f.days[lo:hi], f.close[lo:hi], color="#173a57", lw=1.5, label="Adjusted close")
        x = np.arange(length, dtype=float)
        y = np.log(f.close[t - length:t])
        if kind == "rising":
            centered = x - x.mean()
            slope = centered @ y / (centered @ centered)
            line = y.mean() + slope * centered
            qlo, qhi = np.quantile(y - line, [.1, .9])
            lower, upper = np.exp(line + qlo), np.exp(line + qhi)
        else:
            lower, upper = np.full(length, p["lower"][t]), np.full(length, p["upper"][t])
        ax.fill_between(f.days[t - length:t], lower, upper, color="#15a28b", alpha=.2, label="New prior-window range")
        ax.plot(f.days[t - length:t], upper, color="#158573", lw=1)
        ax.plot(f.days[t - length:t], lower, color="#158573", lw=1)
        ax.scatter(f.days[t], f.close[t], marker="^", color="#dc7c18", s=70, zorder=4, label="First later raw crossing")
        ax.scatter(f.days[t], p["boundary"][t], marker="_", color="#dc7c18", s=150, label="Buffered crossing threshold")
        if old["valid"][t]:
            ax.axhline(old["upper"][t], color="#8857a8", ls="--", lw=1, label="Legacy upper at same date")
            legacy_text = f"legacy lookback {old['L'][t]} sessions"
        else:
            legacy_text = "legacy has no qualifying box at this date"
        ax.set_title(f"{symbol} · {choice['range']} · crossing {f.days[t]} · {legacy_text}", loc="left", fontsize=11)
        ax.set_ylabel("Adjusted USD")
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.grid(alpha=.15)
        ax.legend(loc="best", fontsize=8, ncol=2)
        records.append(dict(symbol=symbol, components=choice, crossing=str(f.days[t]),
            prior_window_start=str(f.days[t - length]), prior_window_end=str(f.days[t - 1]),
            upper=float(p["upper"][t]), lower=float(p["lower"][t]), boundary=float(p["boundary"][t]),
            legacy_valid=bool(old["valid"][t])))
    fig.suptitle("What the redesigned ranges look like on actual published histories\nExamples selected from training fits; first later crossing, not selected for profitable outcome", fontsize=13)
    fig.savefig(OUT / "range-examples.png", dpi=160)
    plt.close(fig)
    study.write(OUT / "range-example-evidence.json", records)


def main():
    study.verified()
    rows = json.loads((OUT / "asset-results.json").read_text())
    choices = json.loads((OUT / "selected-components.json").read_text())
    regime = json.loads((OUT / "regime-attribution.json").read_text())
    portfolios = json.loads((OUT / "portfolio-results.json").read_text())
    families, gates = summaries(rows, portfolios)
    distributions = []
    for era in ("late", "early"):
        for domain in ("short", "long"):
            group = [r for r in choices if r["era"] == era and r["domain"] == domain and r["variant"] == "joint_fit" and r["symbol"] != "BIL"]
            distributions.append(dict(era=era, domain=domain, **{k: dict(Counter(r[k] for r in group)) for k in ("range", "trend", "exit")}))
    summary = dict(families=families, portfolio_gates=gates, component_distributions=distributions,
                   total_cases=len(rows), portfolio_cases=len(portfolios))
    study.write(OUT / "summary.json", summary)
    primary = [r for r in rows if r["cost_bp"] == 5 and r["delay"] == 0]
    keys = ("symbol", "domain", "era", "variant", "cumulative", "cagr", "sharpe", "calmar", "maxdd", "exposure", "alpha", "completed_trades", "turnover_annual", "cost_bp_annual", "training_evidence")
    with (OUT / "per-etf-component-results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[*keys, "ic21"])
        writer.writeheader()
        for r in primary:
            writer.writerow({**{k: r[k] for k in keys}, "ic21": r["ic21"]["ic"]})
    native = json.loads((OUT / "native-checks.json").read_text()) if (OUT / "native-checks.json").exists() else []
    data = dict(rows=primary, stress=rows, choices=choices, regimes=regime, portfolios=portfolios,
                summary=summary, validation=json.loads((OUT / "validation.json").read_text()), native=native)
    template = (study.ROOT / "scripts/assets/adaptive-breakout-review.html").read_text(encoding="utf-8")
    (OUT / "index.html").write_text(template.replace("__REPORT_DATA__", json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")), encoding="utf-8")
    plots(rows, regime)
    range_illustrations()
    names = ["index.html", "asset-results.json", "selected-components.json", "regime-attribution.json", "portfolio-results.json", "summary.json", "validation.json", "protocol.json", "fit-manifest.json", "per-etf-component-results.csv", "component-tradeoffs.png"]
    names += ["range-examples.png", "range-example-evidence.json"]
    names += [p for p in ("native-checks.json", "baseline-validation.json") if (OUT / p).exists()]
    study.write(OUT / "manifest.json", dict(files={n: study.study.digest(OUT / n) for n in names},
        report_code={str(p.relative_to(study.ROOT)).replace('\\', '/'): study.study.digest(p) for p in
            (Path(__file__), study.ROOT / "scripts/assets/adaptive-breakout-review.html", study.ROOT / "scripts/validate_adaptive_breakout.py")}))
    print(json.dumps(dict(families=[r for r in families if r["cost_bp"] == 5 and r["delay"] == 0],
        portfolio_gates_passed=sum(r["passed"] for r in gates), portfolio_gates=len(gates)), indent=2))


if __name__ == "__main__":
    main()
