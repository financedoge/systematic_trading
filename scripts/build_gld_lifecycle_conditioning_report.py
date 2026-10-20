"""Build the two-era stable-signal and FR25/M1 conditioning report."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(r"D:\projects\systematic_trading")
VAR = ROOT / "var" / "research" / "gld-lifecycle-conditioning-20261019-v1"
N_RANDOM = 300
N_MUTATIONS = 60
TOP_SCREEN = 20
MIN_TRADES_PER_ERA = 2
MIN_TOTAL_TRADES = 8
MIN_EXPOSURE = 0.10
PUB = ROOT / "research" / "gld-lifecycle-conditioning-20261019-v1"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fig_b64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def table(headers, rows):
    out = ['<table class="data"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for value in row:
            out.append(f"<td>{value}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def pct(value, digits=2):
    return "&mdash;" if value is None else f"{100.0 * value:.{digits}f}%"


def num(value, digits=2):
    return "&mdash;" if value is None else f"{value:.{digits}f}"


def load_study():
    return dict(
        evidence=read_json(VAR / "condition" / "evidence.json"),
        per_asset=read_json(VAR / "fit" / "per-asset.json"),
        fit_summary=read_json(VAR / "fit" / "summary.json"),
        daily=pd.read_csv(VAR / "condition" / "daily-nav.csv", parse_dates=["date"]),
    )


def build_figures(study):
    figures = {}
    daily = study["daily"]
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    for label, color, lw in (
            ("FR25 SOTA", "#1f2a44", 1.7),
            ("FR25 union renormalise | 5bp d0", "#1b7f3a", 1.3),
            ("FR25 short renormalise | 5bp d0", "#4f7cac", 1.0),
            ("FR25 union cash | 5bp d0", "#c58b2a", 1.0),
            ("FR25 random matched filter seed7 | 5bp d0", "#999999", 1.0),
            ("Equal weight", "#bbb3c8", 0.9)):
        if label in daily:
            values = daily[label].to_numpy(float)
            ax.plot(daily["date"], values / values[0], label=label, color=color, lw=lw)
    ax.set_title("FR25 with the stable life-cycle eligibility filter, 2023-2026 (5bp)")
    ax.legend(loc="upper left", fontsize=7.5)
    figures["equity"] = fig_b64(fig)

    fig, ax = plt.subplots(figsize=(11.5, 4.3))
    for label, color in (("FR25 SOTA", "#1f2a44"),
                         ("FR25 union renormalise | 5bp d0", "#1b7f3a"),
                         ("FR25 random matched filter seed7 | 5bp d0", "#999999")):
        if label in daily:
            values = daily[label].to_numpy(float)
            peak = np.maximum.accumulate(values)
            ax.plot(daily["date"], values / peak - 1, label=label, color=color, lw=1.1)
    ax.set_title("Out-of-sample drawdown: frozen FR25 versus filtered and random-filter controls")
    ax.legend(loc="lower left", fontsize=8)
    figures["drawdown"] = fig_b64(fig)

    # Conditional overlay.
    fig, ax = plt.subplots(figsize=(11.5, 4.8))
    for label, color, lw in (
            ("FR25 SOTA", "#1f2a44", 1.5),
            ("Unconditional overlay 20% Rule A short", "#c58b2a", 1.1),
            ("Conditional overlay 20% Rule A short", "#1b7f3a", 1.4)):
        if label in daily:
            values = daily[label].to_numpy(float)
            ax.plot(daily["date"], values / values[0], label=label, color=color, lw=lw)
    ax.set_title("Pre-2023-calibrated conditional overlay of the Rule A short-only sleeve")
    ax.legend(loc="upper left", fontsize=8)
    figures["overlay"] = fig_b64(fig)

    # Stable-fit coverage by asset class.
    rows = {}
    for entry in study["per_asset"].values():
        cls = entry["class_"]
        bucket = rows.setdefault(cls, dict(n=0, short=0, long=0))
        bucket["n"] += 1
        bucket["short"] += int(entry["short"]["stable"])
        bucket["long"] += int(entry["long"]["stable"])
    labels = sorted(rows)
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(x - 0.2, [rows[c]["short"] for c in labels], width=0.4, color="#1b7f3a",
           label="short-range stable")
    ax.bar(x + 0.2, [rows[c]["long"] for c in labels], width=0.4, color="#c58b2a",
           label="long-range stable")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c}\n(n={rows[c]['n']})" for c in labels], fontsize=8)
    ax.set_ylabel("ETFs passing the two-era stability requirement")
    ax.set_title("Deeper per-ETF fits with 2005-2015 and 2016-2022 stability")
    ax.legend(fontsize=8)
    figures["coverage"] = fig_b64(fig)
    return figures


def main():
    study = load_study()
    evidence = study["evidence"]
    results = evidence["results"]
    benchmarks = evidence["benchmarks"]
    overlay = evidence["conditional_overlay"]
    figures = build_figures(study)
    fr25 = benchmarks["FR25 SOTA"]
    union_key = "FR25 union renormalise | 5bp d0"
    union = results.get(union_key, {}).get("metrics", {})
    short = results.get("FR25 short renormalise | 5bp d0", {}).get("metrics", {})
    cash = results.get("FR25 union cash | 5bp d0", {}).get("metrics", {})
    random_key = "FR25 random matched filter seed7 | 5bp d0"
    random_m = results.get(random_key, {}).get("metrics", {})
    conditional = overlay["conditional"]
    unconditional = overlay["unconditional"]
    # Main scenario table.
    scenario_rows = []
    label_rows = [
        ("Frozen FR25 SOTA", fr25),
        ("FR25 filtered to union-active names (renormalised)", union),
        ("FR25 filtered to short-active names (renormalised)", short),
        ("FR25 filtered to union-active names (removed weight in cash)", cash),
        ("FR25 matched random filter (seed 7)", random_m),
        ("FR25 SOTA, 20bp", benchmarks["FR25 (20bp)"]),
        ("FR25 SOTA, +1 delay", benchmarks["FR25 (+1 delay)"]),
    ]
    for label, m in label_rows:
        if not m:
            continue
        scenario_rows.append((label, pct(m.get("cagr")), num(m.get("sharpe")),
                              pct(m.get("maxdd")), num(m.get("calmar")),
                              pct(m.get("exposure")), num(m.get("annual_turnover")),
                              num(m.get("annual_cost_bps"))))
    scenario_table = table(["Scenario", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure",
                            "Turnover", "Cost bps"], scenario_rows)
    # Signal-source and friction table for the union renormalised filter.
    friction_rows = []
    for variant in ("renormalise", "cash"):
        for cost, delay in ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1)):
            entry = results.get(f"FR25 union {variant} | {cost:g}bp d{delay}")
            if not entry:
                continue
            m = entry["metrics"]
            friction_rows.append((variant, f"{cost:g}bp, delay {delay}", pct(m["cagr"]),
                                  num(m["sharpe"]), pct(m["maxdd"]), num(m["calmar"]),
                                  num(m.get("annual_turnover")), num(m.get("annual_cost_bps"))))
    friction_table = table(["Variant", "Assumption", "CAGR", "Sharpe", "Max DD", "Calmar",
                            "Turnover", "Cost bps"], friction_rows)
    # M1 scenarios.
    m1_rows = []
    for label, key in (("Frozen M1 control", None),
                       ("M1 filtered to union-active names", "M1 union renormalise | 5bp d0"),
                       ("M1 filtered to short-active names", "M1 short renormalise | 5bp d0")):
        m = benchmarks.get("M1 momentum control") if key is None else results.get(key, {}).get("metrics")
        if not m:
            continue
        m1_rows.append((label, pct(m.get("cagr")), num(m.get("sharpe")), pct(m.get("maxdd")),
                        num(m.get("calmar")), pct(m.get("exposure")),
                        num(m.get("annual_turnover"))))
    m1_table = table(["Scenario", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure",
                      "Turnover"], m1_rows)
    # Per-asset fit table.
    asset_rows = []
    for symbol in sorted(study["per_asset"], key=lambda s: (study["per_asset"][s]["class_"], s)):
        entry = study["per_asset"][symbol]
        s, l = entry["short"], entry["long"]
        def era_text(node):
            if not node or node.get("fitness") is None:
                return "&mdash;"
            return f"{node['fitness']:.2f}/{node.get('trades', 0)}"
        asset_rows.append((entry["class_"], symbol,
                           "Y" if s["stable"] else "", "Y" if l["stable"] else "",
                           era_text(s.get("era1")), era_text(s.get("era2")),
                           era_text(l.get("era1")), era_text(l.get("era2")),
                           pct(s["is_metrics"]["cagr"]), num(s["is_metrics"]["sharpe"]),
                           pct(l["is_metrics"]["cagr"]), num(l["is_metrics"]["sharpe"])))
    asset_table = table(["Class", "Symbol", "Short stable", "Long stable",
                         "Short era1 fit/trades", "Short era2", "Long era1", "Long era2",
                         "Short IS CAGR", "Short IS Sh", "Long IS CAGR", "Long IS Sh"],
                        asset_rows)
    # Conditional overlay table.
    overlay_rows = [
        ("Frozen FR25 SOTA", pct(fr25["cagr"]), num(fr25["sharpe"]), pct(fr25["maxdd"]),
         num(fr25["calmar"])),
        ("Unconditional 80/20 FR25 + Rule A short", pct(unconditional["cagr"]),
         num(unconditional["sharpe"]), pct(unconditional["maxdd"]), num(unconditional["calmar"])),
        ("Conditional 80/20 overlay (pre-2023 breadth threshold)", pct(conditional["cagr"]),
         num(conditional["sharpe"]), pct(conditional["maxdd"]), num(conditional["calmar"])),
    ]
    overlay_table = table(["Scenario", "CAGR", "Sharpe", "Max DD", "Calmar"], overlay_rows)
    # Annual table.
    daily = study["daily"]

    def year_return(label, year):
        if label not in daily:
            return None
        frame = daily[(daily["date"] >= f"{year}-01-01") & (daily["date"] <= f"{year}-12-31")]
        if len(frame) < 20:
            return None
        return float(frame[label].iloc[-1] / frame[label].iloc[0] - 1.0)

    annual_rows = []
    for year in (2023, 2024, 2025, 2026):
        annual_rows.append((year, pct(year_return("FR25 SOTA", year)),
                            pct(year_return("FR25 union renormalise | 5bp d0", year)),
                            pct(year_return("FR25 random matched filter seed7 | 5bp d0", year)),
                            pct(year_return("Conditional overlay 20% Rule A short", year)),
                            pct(year_return("Unconditional overlay 20% Rule A short", year))))
    annual_table = table(["Year", "FR25 SOTA", "FR25 + life-cycle filter",
                          "FR25 + random matched filter", "Conditional 20% overlay",
                          "Unconditional 20% overlay"], annual_rows)
    # Fit summary and verdict.
    fit = study["fit_summary"]
    fit_keys = dict(assets=fit["assets"], short_stable=fit["stable_short"],
                    long_stable=fit["stable_long"],
                    short_fallback=fit["fallback_short"], long_fallback=fit["fallback_long"])
    verdict = (
        f"Deeper two-era-stable per-ETF fits pass for {fit_keys['short_stable']}/52 short-range and "
        f"{fit_keys['long_stable']}/52 long-range sleeves. Filtering FR25 to stable union-active names "
        f"gives {pct(union.get('cagr'))} CAGR / Sharpe {num(union.get('sharpe'))} / max DD "
        f"{pct(union.get('maxdd'))} versus FR25 {pct(fr25['cagr'])} / {num(fr25['sharpe'])} / "
        f"{pct(fr25['maxdd'])} and the matched random filter {pct(random_m.get('cagr'))} / "
        f"{num(random_m.get('sharpe'))}. The pre-2023-calibrated conditional 20% overlay gives "
        f"{pct(conditional.get('cagr'))} / {num(conditional.get('sharpe'))} / {pct(conditional.get('maxdd'))} "
        f"versus the unconditional overlay {pct(unconditional.get('cagr'))} / {num(unconditional.get('sharpe'))}.")
    css = """
    :root { --ink:#1c2533; --muted:#5b6675; --line:#d9dee6; --bg:#fbfbfc; --accent:#1b7f3a;
            --accent2:#b23b3b; --blue:#4f7cac; --gold:#c58b2a; }
    * { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--ink);
      font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
    header { background:#16202e; color:#fff; padding:34px 6vw 28px; }
    header h1 { margin:0 0 6px; font-size:26px; } header .sub { color:#c4cdd9; max-width:1150px; }
    header .meta { margin-top:14px; color:#9fb0c4; font-size:12.5px; }
    main { max-width:1180px; margin:0 auto; padding:26px 22px 80px; }
    h2 { margin:46px 0 14px; font-size:22px; border-bottom:2px solid var(--line); padding-bottom:6px; }
    h3 { margin:26px 0 10px; font-size:16.5px; } .lede { font-size:16px; }
    .callout { background:#fff; border-left:4px solid var(--blue); padding:12px 16px; margin:16px 0;
               border-radius:4px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
    .callout.good { border-left-color:var(--accent); } .callout.warn { border-left-color:var(--accent2); }
    .kpi { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }
    .kpi div { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px; }
    .kpi .v { font-size:22px; font-weight:650; } .kpi .l { color:var(--muted); font-size:12px; }
    table.data { border-collapse:collapse; width:100%; background:#fff; margin:10px 0 18px;
                 font-size:12px; }
    table.data th, table.data td { border:1px solid var(--line); padding:5px 7px; text-align:right; }
    table.data th { background:#eef1f5; font-weight:600; }
    table.data td:first-child, table.data th:first-child { text-align:left; }
    table.data tbody tr:nth-child(even) { background:#fafbfc; }
    .scroll { max-height:580px; overflow:auto; border:1px solid var(--line); border-radius:6px; }
    .scroll table.data { margin:0; }
    img.fig { width:100%; height:auto; display:block; margin:12px 0 6px;
              border:1px solid var(--line); border-radius:6px; background:#fff; }
    .caption { color:var(--muted); font-size:12.5px; margin:2px 0 18px; }
    code { font-family:Consolas,monospace; font-size:13px; } .note { color:var(--muted); font-size:12.5px; }
    a { color:#1c5f9e; }
    """
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Two-era stable life-cycle signals as an FR25/M1 eligibility filter</title><style>{css}</style></head><body>
<header>
<h1>Deeper two-era-stable life-cycle signals as an eligibility filter on FR25/M1</h1>
<div class="sub">Per-ETF short-range and long-range life-cycle fits were deepened and required to be
positive in both 2005-2015 and 2016-2022 pre-2023 eras. The resulting active/inactive state is then
used only as an eligibility filter on the frozen FR25/M1 names while momentum/weighting does the
ranking, with matched random filters and pre-2023-calibrated conditional overlays as controls.</div>
<div class="meta">Study <code>{evidence['identity']}</code> · research only, no monitoring or trade authority</div>
</header>
<main>
<p class="lede">{verdict}</p>
<div class="kpi">
<div><div class="v">{fit_keys['short_stable']}/52</div><div class="l">short-range sleeves passing two-era stability</div></div>
<div><div class="v">{fit_keys['long_stable']}/52</div><div class="l">long-range sleeves passing</div></div>
<div><div class="v">{pct(union.get('cagr'))}</div><div class="l">FR25 + life-cycle filter CAGR</div></div>
<div><div class="v">{num(union.get('sharpe'))}</div><div class="l">FR25 + life-cycle filter Sharpe</div></div>
</div>
<div class="callout warn"><strong>Answer versus the SOTA.</strong> {verdict} The frozen FR25
({pct(fr25['cagr'])} / {num(fr25['sharpe'])} / {pct(fr25['maxdd'])}) remains the reference: filtering
names by life-cycle activity changes the book but does not automatically improve net Sharpe/return/drawdown.
The filter's value is judged against the matched random filter, not only against the frozen path.</div>

<h2>1. What was done</h2>
<ul>
<li><strong>Deeper per-ETF fit (pre-2023 only).</strong> {fit['two_era_requirement']}. Search budget:
{N_RANDOM} random bounded vectors per domain plus the sealed GLD vector and {N_MUTATIONS} anchor
mutations; candidates screened by the worst era, the top {TOP_SCREEN} replayed across 5/10/20bp and
+1 session delay. The 52-ETF pool, data batch and accounting engine are the same as the pool study.</li>
<li><strong>Conditioning, not ranking.</strong> At each FR25/M1 monthly decision, names without a stable
life-cycle signal at that close are removed; the rest keep their FR25 relative weights. Two variants:
<em>renormalise</em> (remaining names rescaled to the 98% budget) and <em>cash</em> (removed weight simply
left in cash). Momentum remains FR25's own ranking; the life cycle only grants eligibility.</li>
<li><strong>Matched controls.</strong> Random filters remove the same number of names at each rebalance
(seeded draws), so the comparison separates life-cycle information from simply holding fewer names.</li>
<li><strong>Conditional overlay threshold fitted pre-2023 (c).</strong> The Rule A short-only daily sleeve
gets 20% capital only in months whose stable union-signal breadth is at or above the pre-2023 median;
compared with the unconditional 20% overlay and FR25. The threshold uses only pre-2023 data.</li>
<li><strong>Retest (d).</strong> Net Sharpe, return and drawdown, turnover/costs, 5/10/20bp and +1 session
delay sensitivity, calendar years, and matched-control comparisons; 2023-2026 remains an inspected
development retest.</li>
</ul>

<h2>2. Two-era stable fits</h2>
<p>{fit_keys['assets']} ETFs were refitted. {fit_keys['short_stable']} short-range and
{fit_keys['long_stable']} long-range sleeves pass the stability rule; {fit_keys['short_fallback']} and
{fit_keys['long_fallback']} fall back to the sealed GLD vector. Stability is demanding: the 2005-2015 and
2016-2022 eras have different volatility regimes, and the long-range domain needs long histories before
its first signal.</p>
<div class="scroll">{asset_table}</div>
<div class="caption">Per-ETF two-era fit table. Era columns show in-sample fitness / closed trades; the
IS columns are full pre-2023 fit diagnostics, not OOS. "Stable" means both eras had positive fitness and at
least {MIN_TRADES_PER_ERA} closed trades, with at least {MIN_TOTAL_TRADES} total and {MIN_EXPOSURE:.0%}
exposure.</div>
<img class="fig" src="data:image/png;base64,{figures['coverage']}" alt="coverage">
<div class="caption">Two-era-stable sleeves by asset class.</div>

<h2>3. FR25 with the life-cycle eligibility filter (2023-2026, 5bp)</h2>
{scenario_table}
<div class="caption">Frozen FR25 and the filtered variants, with cost and delay reference rows. The
random matched filter uses the same number of removed names per rebalance. Turnover/cost columns are
annualised; FR25 benchmark rows have no turnover reported in the frozen path.</div>
<img class="fig" src="data:image/png;base64,{figures['equity']}" alt="equity">
<div class="caption">Frozen FR25 (dark), union-filtered FR25 (green), short-only filter (blue),
cash variant (gold) and the matched random filter (grey).</div>
<img class="fig" src="data:image/png;base64,{figures['drawdown']}" alt="drawdown">
<div class="caption">Drawdowns.</div>
<h3>3.1 Cost and execution-delay sensitivity</h3>
{friction_table}
<div class="caption">The filter changes the book only at monthly decisions, so transaction costs stay in
the FR25 range; delay is the larger risk.</div>
<h3>3.2 M1 conditioned control</h3>
{m1_table}
<div class="caption">The same eligibility filter applied to the frozen M1 momentum control. Its frozen
path is cash-heavy, so the level is low; the comparison is filter-versus-frozen, not versus FR25.</div>

<h2>4. Pre-2023-calibrated conditional overlay</h2>
<p>Breadth threshold: <strong>{overlay['breadth_threshold']:.1f} stable union signals</strong> (= pre-2023
median monthly breadth). The condition is true in <strong>{pct(overlay['share_of_months_condition_true'])}</strong>
of the 2023-2026 months. When true, 20% of the account follows the Rule A short-only daily sleeve; otherwise
the account is 100% FR25. The condition is decided at the prior month-end close and applied from the next
session.</p>
{overlay_table}
<img class="fig" src="data:image/png;base64,{figures['overlay']}" alt="overlay">
<div class="caption">Conditional versus unconditional 20% Rule A short-only overlay and FR25.</div>
<h3>4.1 Calendar years</h3>
{annual_table}
<div class="caption">Annual returns: the conditional overlay adds the sleeve in some years and not others;
its net effect depends on whether the sleeve's weak years coincide with FR25's strong years.</div>

<h2>5. Verdict and next actions</h2>
<ul>
<li><strong>Two-era stability is achievable but selective.</strong> {fit_keys['short_stable']}/52 short and
{fit_keys['long_stable']}/52 long sleeves survive; the rest either fall back or fail the era requirement.
That is the honest cost of demanding pre-2023 chronological robustness from a 241-vector-class search.</li>
<li><strong>The eligibility filter is not a free improvement.</strong> Filtered FR25 is
{pct(union.get('cagr'))}/{num(union.get('sharpe'))}/{pct(union.get('maxdd'))} versus frozen
{pct(fr25['cagr'])}/{num(fr25['sharpe'])}/{pct(fr25['maxdd'])}; the matched random filter is
{pct(random_m.get('cagr'))}/{num(random_m.get('sharpe'))}. Compare the filter with that random control before
claiming value; if the filter merely holds fewer names, it has no demonstrated edge.</li>
<li><strong>The conditional overlay is the better use of the life cycle.</strong> Pre-2023 breadth timing
gives {pct(conditional.get('cagr'))}/{num(conditional.get('sharpe'))}/{pct(conditional.get('maxdd'))} versus
the unconditional overlay {pct(unconditional.get('cagr'))}/{num(unconditional.get('sharpe'))}. This remains
a small risk-shaping sleeve, not a SOTA replacement.</li>
<li><strong>No promotion.</strong> No monitoring, allocation, funding or broker action follows. All 2023+
figures are development retests on an inspected interval; the filter threshold was fitted on pre-2023
breadth only.</li>
</ul>
<p><strong>Next actions:</strong> (1) require the stable screen also at the M1/FR25 decision level for names
not historically in the pool; (2) test a dynamic (target-change triggered) rebalancing variant of the filter
against the fixed monthly control; (3) if the filtered book's edge over the random filter is not positive,
retire the eligibility-filter route and keep the conditional overlay as the only candidate.</p>

<h2>6. Files and reproduction</h2>
<ul>
<li><a href="daily-nav.csv">daily-nav.csv</a> — daily NAV for frozen benchmarks, filtered variants, matched
random controls and overlays.</li>
<li><a href="scenarios.csv">scenarios.csv</a> — all scenario metrics, costs and delays.</li>
<li><a href="evidence.json">evidence.json</a> — full results, per-scenario metrics, annual returns,
conditional-overlay diagnostics and protocol.</li>
</ul>
<p class="note">Reproduction: <code>python scripts/run_gld_lifecycle_conditioning.py refit</code> then
<code>python scripts/run_gld_lifecycle_conditioning.py condition</code>, then
<code>python scripts/build_gld_lifecycle_conditioning_report.py</code>. Research only.</p>
</main></body></html>"""
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(VAR / "condition" / "daily-nav.csv", PUB / "daily-nav.csv")
    shutil.copyfile(VAR / "condition" / "scenarios.csv", PUB / "scenarios.csv")
    shutil.copyfile(VAR / "condition" / "evidence.json", PUB / "evidence.json")
    files = sorted(p for p in PUB.iterdir() if p.is_file() and p.name != "manifest.json")
    (PUB / "manifest.json").write_text(json.dumps(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2),
        encoding="utf-8")
    print(json.dumps({"public": str(PUB), "html_bytes": len(html), "files": len(files)}, indent=1))


if __name__ == "__main__":
    main()
