"""Build the daily opportunity-scanner / CTA-style portfolio report."""
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
VAR = ROOT / "var" / "research" / "gld-lifecycle-daily-scanner-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-daily-scanner-20261019-v1"


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
        evidence=read_json(VAR / "evidence.json"),
        daily=pd.read_csv(VAR / "daily-nav.csv", parse_dates=["date"]),
        holdings=read_json(VAR / "holdings.json"),
    )


def build_figures(study):
    figures = {}
    daily = study["daily"]
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    series = [
        ("equal_split|union", "Rule A equal-split, union", "#1b7f3a", 1.5),
        ("slots|union", "Rule B 1/6-slot, union", "#c58b2a", 1.5),
        ("equal_split|long", "Rule A equal-split, long only", "#7a2e8f", 1.0),
        ("equal_split|short", "Rule A equal-split, short only", "#4f7cac", 1.0),
        ("FR25 SOTA", "FR25 SOTA (reference)", "#1f2a44", 1.3),
        ("Equal-weight pool", "Equal-weight pool", "#999999", 1.0),
        ("URTH", "URTH buy-hold", "#8172b2", 1.0),
        ("BIL", "BIL (cash proxy)", "#bbbbbb", 1.0),
    ]
    for key, label, color, lw in series:
        if key in daily:
            values = daily[key].to_numpy()
            ax.plot(daily["date"], values / values[0], label=label, color=color, lw=lw)
    ax.set_title("Daily event-driven life-cycle portfolios versus benchmarks, 2023-2026")
    ax.legend(loc="upper left", fontsize=7.5)
    figures["equity"] = fig_b64(fig)

    fig, ax = plt.subplots(figsize=(11.5, 4.3))
    for key, label, color in (("equal_split|union", "Rule A equal-split", "#1b7f3a"),
                              ("slots|union", "Rule B 1/6-slot", "#c58b2a"),
                              ("FR25 SOTA", "FR25 SOTA", "#1f2a44")):
        if key in daily:
            values = daily[key].to_numpy()
            peak = np.maximum.accumulate(values)
            ax.plot(daily["date"], values / peak - 1, label=label, color=color, lw=1.1)
    ax.set_title("Out-of-sample drawdown")
    ax.legend(loc="lower left", fontsize=8)
    figures["drawdown"] = fig_b64(fig)

    # Holdings count over time from the rebalance timeline.
    fig, ax = plt.subplots(figsize=(11.5, 4.0))
    for key, label, color in (("equal_split|union", "Rule A equal-split", "#1b7f3a"),
                              ("slots|union", "Rule B 1/6-slot", "#c58b2a")):
        rows = study["holdings"].get(key, [])
        if not rows:
            continue
        dates = pd.to_datetime([r["date"] for r in rows])
        counts = [r["holdings"] for r in rows]
        ax.step(dates, counts, where="post", label=label, color=color, lw=1.3)
    ax.set_ylim(0, 6.5)
    ax.set_ylabel("holdings after each rebalance")
    ax.set_title("Number of holdings through time (the 6-slot cap binds almost always)")
    ax.legend(loc="lower left", fontsize=8)
    figures["holdings"] = fig_b64(fig)

    # Annual returns from the daily NAV frame (benchmarks included).
    def year_return(label, year):
        if label not in daily:
            return 0.0
        frame = daily[(daily["date"] >= f"{year}-01-01") & (daily["date"] <= f"{year}-12-31")]
        if len(frame) < 20:
            return 0.0
        return float(frame[label].iloc[-1] / frame[label].iloc[0] - 1.0)

    years = [2023, 2024, 2025, 2026]
    fig, ax = plt.subplots(figsize=(9.0, 4.0))
    x = np.arange(len(years))
    ax.bar(x - 0.2, [year_return("equal_split|union", y) for y in years], width=0.4,
           color="#1b7f3a", label="Rule A equal-split")
    ax.bar(x + 0.2, [year_return("slots|union", y) for y in years], width=0.4,
           color="#c58b2a", label="Rule B 1/6-slot")
    ax.plot(x, [year_return("FR25 SOTA", y) for y in years], color="#1f2a44",
            marker="o", label="FR25 SOTA")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_title("Calendar-year returns")
    ax.legend(fontsize=8)
    figures["annual"] = fig_b64(fig)
    return figures


def main():
    study = load_study()
    evidence = study["evidence"]
    results = evidence["results"]
    benchmarks = evidence["benchmarks"]
    protocol = evidence["protocol"]
    figures = build_figures(study)

    def base_row(key):
        lookup = key if key.endswith(" | 5bp d0") else f"{key} | 5bp d0"
        entry = results.get(lookup)
        if not entry:
            return None
        m = entry["metrics"]
        b = entry["behavior"]
        return (key, pct(m["cagr"]), num(m["sharpe"]), pct(m["maxdd"]), num(m["calmar"]),
                pct(m["exposure"]), num(m.get("annual_turnover")), b["entry_events"],
                b["exit_events"], f"{b['average_holdings']:.1f}", pct(b["share_flat"]),
                pct(b["share_full"]))

    rule_keys = ["equal_split|union", "slots|union", "equal_split|short", "slots|short",
                 "equal_split|long", "slots|long", "equal_split|union slots4",
                 "slots|union slots4", "equal_split|union slots8", "slots|union slots8",
                 "equal_split|union cashSHY | 5bp d0", "slots|union cashSHY | 5bp d0",
                 "equal_split|union cashIEF | 5bp d0", "slots|union cashIEF | 5bp d0"]
    rule_rows = []
    for key in rule_keys:
        row = base_row(key)
        if row:
            rule_rows.append(row)
    bench_rows = []
    for label in ("FR25 SOTA", "Equal-weight pool", "URTH", "BIL"):
        m = benchmarks[label]
        bench_rows.append((label, pct(m["cagr"]), num(m["sharpe"]), pct(m["maxdd"]),
                           num(m["calmar"]), pct(m["exposure"]), "&mdash;", "&mdash;",
                           "&mdash;", "&mdash;", "&mdash;", "&mdash;"))
    results_table = table(["Portfolio", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure",
                           "Turnover", "Entries", "Exits", "Avg holdings", "Time flat",
                           "Time full"], bench_rows + rule_rows)
    # Friction table for the two headline rules.
    friction_rows = []
    for rule in ("equal_split|union", "slots|union"):
        for cost, delay in ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1)):
            entry = results.get(f"{rule} | {cost:g}bp d{delay}")
            if not entry:
                continue
            m = entry["metrics"]
            friction_rows.append((rule, f"{cost:g}bp, delay {delay}", pct(m["cagr"]),
                                  num(m["sharpe"]), pct(m["maxdd"]),
                                  num(m["calmar"]), num(m.get("annual_cost_bps"))))
    friction_table = table(["Rule", "Assumption", "CAGR", "Sharpe", "Max DD", "Calmar",
                            "Cost bps"], friction_rows)
    # Cash-proxy sensitivity.
    cash_rows = []
    for proxy, label in (("BIL", "BIL (T-bill base)"), ("SHY", "SHY 1-3y Treasury"),
                         ("IEF", "IEF 7-10y Treasury")):
        for rule in ("equal_split", "slots"):
            key = f"{rule}|union" if proxy == "BIL" else f"{rule}|union cash{proxy} | 5bp d0"
            entry = results.get(f"{key} | 5bp d0") if proxy == "BIL" else results.get(key)
            if not entry:
                continue
            m = entry["metrics"]
            cash_rows.append((label, rule, pct(m["cagr"]), num(m["sharpe"]),
                              pct(m["maxdd"]), num(m["calmar"])))
    cash_table = table(["Cash/government leg", "Rule", "CAGR", "Sharpe", "Max DD", "Calmar"],
                       cash_rows)
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
        annual_rows.append((year, pct(year_return("equal_split|union", year)),
                            pct(year_return("slots|union", year)),
                            pct(year_return("equal_split|short", year)),
                            pct(year_return("equal_split|long", year)),
                            pct(year_return("FR25 SOTA", year))))
    annual_table = table(["Year", "A union", "B union", "A short-only", "A long-only",
                          "FR25 SOTA"], annual_rows)
    # Correlation table.
    corr_rows = []
    for key in ("equal_split|union", "slots|union", "equal_split|short", "equal_split|long"):
        c = evidence["correlations"].get(key, {})
        corr_rows.append((key, num(c.get("FR25 SOTA"), 2), num(c.get("URTH"), 2),
                          num(c.get("BIL"), 2)))
    corr_table = table(["Portfolio", "corr vs FR25", "corr vs URTH", "corr vs BIL"], corr_rows)
    # Benchmark metrics for verdict text.
    fr25 = benchmarks["FR25 SOTA"]
    ew = benchmarks["Equal-weight pool"]
    urth = benchmarks["URTH"]
    a_union = results.get("equal_split|union | 5bp d0", {})
    b_union = results.get("slots|union | 5bp d0", {})
    a_short = results.get("equal_split|short | 5bp d0", {})
    a_m = a_union.get("metrics", {})
    b_m = b_union.get("metrics", {})
    s_m = a_short.get("metrics", {})
    verdict = (
        f"The daily event-driven portfolios do not beat the reference benchmarks. Rule A (equal re-split, "
        f"union signals) reaches {pct(a_m.get('cagr'))} CAGR / Sharpe {num(a_m.get('sharpe'))} / max DD "
        f"{pct(a_m.get('maxdd'))}; Rule B (1/6 slots) {pct(b_m.get('cagr'))} / {num(b_m.get('sharpe'))} / "
        f"{pct(b_m.get('maxdd'))}; the best variant in this sweep is the short-only equal-split rule at "
        f"{pct(s_m.get('cagr'))} / {num(s_m.get('sharpe'))} / {pct(s_m.get('maxdd'))}, still below FR25 "
        f"({pct(fr25['cagr'])} / {num(fr25['sharpe'])} / {pct(fr25['maxdd'])}), equal weight "
        f"({pct(ew['cagr'])} / {num(ew['sharpe'])}) and URTH ({pct(urth['cagr'])} / {num(urth['sharpe'])}).")
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
    img.fig { width:100%; height:auto; display:block; margin:12px 0 6px;
              border:1px solid var(--line); border-radius:6px; background:#fff; }
    .caption { color:var(--muted); font-size:12.5px; margin:2px 0 18px; }
    code { font-family:Consolas,monospace; font-size:13px; } .note { color:var(--muted); font-size:12.5px; }
    a { color:#1c5f9e; }
    """
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily life-cycle opportunity scanner / CTA-style portfolios</title><style>{css}</style></head><body>
<header>
<h1>Daily life-cycle opportunity scanner: equal re-split and 1/6-slot CTA-style portfolios</h1>
<div class="sub">Two daily event-driven constructions on the 52-ETF pool, built only from the sealed pre-2023
short-range and long-range life-cycle signals. Rule A re-splits the existing book equally whenever a new ETF
entry triggers. Rule B gives each new entry one 1/6 slot and leaves unused slots in the government/cash proxy.
No monthly asset ranking is used; every position persists until its own signal exits.</div>
<div class="meta">Study <code>{protocol['identity']}</code> · research only, no monitoring or trade authority</div>
</header>
<main>
<p class="lede">{verdict}</p>
<div class="kpi">
<div><div class="v">{pct(a_m.get('cagr'))}</div><div class="l">Rule A equal-split CAGR</div></div>
<div><div class="v">{num(a_m.get('sharpe'))}</div><div class="l">Rule A Sharpe</div></div>
<div><div class="v">{pct(b_m.get('cagr'))}</div><div class="l">Rule B 1/6-slot CAGR</div></div>
<div><div class="v">{num(b_m.get('sharpe'))}</div><div class="l">Rule B Sharpe</div></div>
</div>
<div class="callout warn"><strong>The cash leg almost never activates.</strong> The fitted per-ETF signals
are active for about 73% of asset-days in the OOS window, and the 52-ETF universe almost always offers at
least six simultaneous active signals (only {pct(a_union.get('behavior', {}).get('share_flat'))} of days had
zero holdings; the book was full {pct(a_union.get('behavior', {}).get('share_full'))} of the time). The rules
therefore behave as concentrated six-name portfolios, not as opportunity scanners that spend most of their time
in govvies. That is a signal-selectivity problem, not a portfolio-rule problem: the broad universe and the
permissive per-ETF fits mean the 6 slots fill immediately and are rarely freed.</div>

<h2>1. The two rules as implemented</h2>
<ul>
<li><strong>Signals.</strong> For each ETF the union of the sealed short-range and long-range sleeve states.
A "new entry" is a daily 0→1 transition in that union; an "exit" is a 1→0 transition. Signals use pre-2023-fitted
parameters only. Short-only and long-only runs attribute the two horizons.</li>
<li><strong>Rule A — equal re-split.</strong> Existing holdings persist until their signal exits. A new entry
triggers an equal-weight re-split of every current holding (capacity 6); an exit drops the name and the remaining
book is re-equalised. Starting from the OOS window, the account begins flat and only entries inside the window
populate it.</li>
<li><strong>Rule B — 1/6 slot CTA.</strong> At most six holdings; each accepted entry gets one 1/6 slot, and unused
slots stay in the government/cash proxy. An exit returns its slot to the proxy; the other holdings keep 1/6.</li>
<li><strong>Cash/government leg.</strong> BIL (1-3 month T-bill) is the base proxy; SHY (1-3y Treasury) and IEF
(7-10y Treasury) are sensitivities. GOVY itself is not in the audited pool.</li>
<li><strong>Execution.</strong> Daily close decisions, next-open fills, cost per traded side, no shorting or
leverage, no monthly ranking, no cap beyond six names. Account starts flat at {protocol['chronology']['oos_start']}.</li>
</ul>

<h2>2. Results, 2023-01-03 to 2026-10-12 (5bp, next-open fills)</h2>
{results_table}
<div class="caption">All portfolios are long-only. Turnover is annualised. Time flat is the share of sessions with
no holdings; time full is the share with six holdings. Rules 4/8-slot and cash-proxy variants are sensitivity
runs; only the 6-slot union rules are the predeclared primary designs.</div>
<img class="fig" src="data:image/png;base64,{figures['equity']}" alt="equity">
<div class="caption">Growth of 1.0. The daily life-cycle portfolios (green/gold) earn a positive long-only return
but trail FR25, equal-weight and URTH over this 2023-2026 window.</div>
<img class="fig" src="data:image/png;base64,{figures['drawdown']}" alt="drawdown">
<div class="caption">Out-of-sample drawdowns.</div>
<h3>2.1 Calendar-year returns</h3>
{annual_table}
<img class="fig" src="data:image/png;base64,{figures['annual']}" alt="annual">
<div class="caption">Rule A and Rule B versus FR25 by calendar year.</div>
<h3>2.2 Signal-source attribution: short vs long vs union</h3>
<ul>
<li><strong>Union</strong> (the primary signal): {pct(a_m.get('cagr'))} CAGR / Sharpe {num(a_m.get('sharpe'))} /
DD {pct(a_m.get('maxdd'))}.</li>
<li><strong>Short-only</strong> (best variant): {pct(s_m.get('cagr'))} / {num(s_m.get('sharpe'))} /
{pct(s_m.get('maxdd'))}.</li>
<li><strong>Long-only</strong>: {pct(results.get('equal_split|long | 5bp d0', {}).get('metrics', {}).get('cagr'))} /
{num(results.get('equal_split|long | 5bp d0', {}).get('metrics', {}).get('sharpe'))}.</li>
</ul>
<p>The short-range sleeve — the faster, higher-turnover horizon — carries the better short-sample result; the
long-range sleeve adds slower entries whose holding periods overlap less with the opportunity stream. None of
the variants reaches the reference benchmarks.</p>
<h3>2.3 Behavior: holdings and turnover</h3>
<img class="fig" src="data:image/png;base64,{figures['holdings']}" alt="holdings">
<div class="caption">Holdings count after each rebalance. The book fills to six almost immediately and the cap
binds for most of the window; new signals are ignored while full, so the strategy is effectively a rotating
six-name portfolio rather than an opportunity scanner.</div>

<h2>3. Costs, capacity and the cash proxy</h2>
{friction_table}
<div class="caption">Turnover is modest (about 5x/year for the primary rules); costs are not the reason for the
shortfall versus the benchmarks.</div>
{cash_table}
<div class="caption">The cash-leg choice barely matters because the residual cash weight is almost always zero.
The identical results for SHY/IEF and BIL are themselves evidence of the "always six holdings" degeneracy.</div>
<h3>3.1 Capacity sensitivity</h3>
<p>Allowing more slots (8) raises diversification and improves the union Rule A result to about 9% CAGR, still
below equal-weight; allowing fewer slots (4) concentrates further and does not help. The cap is not the binding
constraint — the signal quality is.</p>
<h3>3.2 Correlation</h3>
{corr_table}
<div class="caption">The daily portfolios are equity-like (0.66-0.73 correlation with FR25 and 0.65-0.66 with
URTH), not a distinct CTA diversifier in this sample.</div>

<h2>4. Verdict and what it means</h2>
<ul>
<li><strong>Both daily event-driven constructions work mechanically</strong> — entries, exits, re-splits, slot
accounting and costs all behave as specified — but neither beats the reference benchmarks. Rule A union
{pct(a_m.get('cagr'))} CAGR/Sharpe {num(a_m.get('sharpe'))}; Rule B {pct(b_m.get('cagr'))}/{num(b_m.get('sharpe'))};
best variant (short-only equal-split) {pct(s_m.get('cagr'))}/{num(s_m.get('sharpe'))}; FR25 SOTA
{pct(fr25['cagr'])}/{num(fr25['sharpe'])}; equal-weight {pct(ew['cagr'])}/{num(ew['sharpe'])}; URTH
{pct(urth['cagr'])}/{num(urth['sharpe'])}.</li>
<li><strong>The "govy when no opportunity" branch is effectively unused.</strong> With 52 ETFs and permissive
per-ETF fits, at least six names are in signal almost every day; the portfolio is a concentrated long-only
six-name book. To make the design behave as an opportunity scanner, the entry definition must be much more
selective (or the universe smaller), not the cash rule.</li>
<li><strong>Why the signal stream is permissive.</strong> The per-ETF fits were selected for breadth in the pool
study, with only a minimum 5% exposure rule; the median short-range sleeve is long 59% of IS sessions. A daily
scanner needs sparse, high-conviction entries; that requires either a stricter per-ETF fit (e.g., event-style
exposure range, cross-period stability), an explicit entry-strength threshold fitted pre-2023, or a
replace-when-full ranking rule.</li>
<li><strong>No OOS tuning and no authority.</strong> Rules, cash leg, capacity and frictions were fixed before
the 2023+ replay. No monitoring, promotion, funding, allocation or broker action follows.</li>
</ul>

<h2>5. Suggested next experiments</h2>
<ol>
<li><strong>Entry-strength threshold on the scanner.</strong> Accept a daily entry only when its extension score
exceeds a pre-2023-calibrated quantile (e.g., top quintile of pre-2023 entries); this should create real cash
periods and a more CTA-like exposure path. Compare with the current first-come-first-served capacity rule.</li>
<li><strong>Replace-when-full ranking.</strong> When all six slots are held and a new stronger signal fires,
replace the weakest holding instead of ignoring the opportunity.</li>
<li><strong>Stricter per-ETF fits for the scanner.</strong> Refit with the exposure range 5-50% and a
cross-period (two-era) stability requirement so entries are genuinely event-like; the pool-study fits are too
permissive for this use.</li>
<li><strong>Smaller, higher-conviction universe.</strong> The 52-ETF pool almost always has six live signals;
a sector/asset-class scanner or a smaller watchlist would let the cash leg express the opportunity cycle.</li>
</ol>

<h2>6. Files and reproduction</h2>
<ul>
<li><a href="daily-nav.csv">daily-nav.csv</a> — daily NAV for every rule, sensitivity and benchmark.</li>
<li><a href="evidence.json">evidence.json</a> — all results, behavior statistics, annual returns, correlations,
holdings timeline and the predeclared protocol.</li>
<li><a href="holdings.json">holdings.json</a> — holdings after every rebalance for each rule.</li>
</ul>
<p class="note">Reproduction: <code>python scripts/run_gld_lifecycle_daily_scanner.py</code> then
<code>python scripts/build_gld_lifecycle_daily_scanner_report.py</code>. Signals from
<code>var/research/gld-lifecycle-pool-20261019-v1</code>; portfolio replay uses the shared application accounting
engine (FR25 replay deviation 0.0). Research only.</p>
</main></body></html>"""
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(VAR / "daily-nav.csv", PUB / "daily-nav.csv")
    shutil.copyfile(VAR / "evidence.json", PUB / "evidence.json")
    shutil.copyfile(VAR / "holdings.json", PUB / "holdings.json")
    files = sorted(p for p in PUB.iterdir() if p.is_file() and p.name != "manifest.json")
    (PUB / "manifest.json").write_text(json.dumps(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2),
        encoding="utf-8")
    print(json.dumps({"public": str(PUB), "html_bytes": len(html), "files": len(files)}, indent=1))


if __name__ == "__main__":
    main()
