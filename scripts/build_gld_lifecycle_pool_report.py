"""Build the 52-ETF two-horizon lifecycle pool and asset-selection report."""
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
VAR = ROOT / "var" / "research" / "gld-lifecycle-pool-20261019-v1"
N_RANDOM = 200
N_ANCHOR_MUTATIONS = 40
TOP_PER_DOMAIN = 15
PUB = ROOT / "research" / "gld-lifecycle-pool-20261019-v1"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fig_b64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def table(headers, rows, cls="data"):
    out = [f'<table class="{cls}"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for value in row:
            if isinstance(value, float):
                text = f"{value:.4f}"
            elif value is None:
                text = "&mdash;"
            else:
                text = str(value)
            out.append(f"<td>{text}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def pct(value, digits=2):
    return "&mdash;" if value is None else f"{100.0 * value:.{digits}f}%"


def num(value, digits=2):
    return "&mdash;" if value is None else f"{value:.{digits}f}"


def load_study():
    return dict(
        protocol=read_json(VAR / "protocol.json"),
        per_asset=read_json(VAR / "fit" / "per-asset.json"),
        evidence=read_json(VAR / "portfolio" / "evidence.json"),
        daily=pd.read_csv(VAR / "portfolio" / "daily-nav.csv", parse_dates=["date"]),
    )


def class_summary(per_asset):
    rows = {}
    for symbol, entry in per_asset.items():
        cls = entry["class_"]
        row = rows.setdefault(cls, dict(n=0, short_active=0, long_active=0,
                                        short_oos=[], long_oos=[],
                                        short_is=[], long_is=[]))
        row["n"] += 1
        row["short_active"] += int(entry["short"]["evidence"])
        row["long_active"] += int(entry["long"]["evidence"])
        for kind, key_oos, key_is in (("short", "short_oos", "short_is"),
                                      ("long", "long_oos", "long_is")):
            oos = entry[kind].get("oos_stats")
            if oos:
                row[key_oos].append(oos.get("cagr", 0.0))
            is_metrics = entry[kind].get("is_metrics")
            if is_metrics:
                row[key_is].append(is_metrics.get("cagr", 0.0))
    out = []
    for cls, row in sorted(rows.items()):
        out.append(dict(asset_class=cls, n=row["n"], short_active=row["short_active"],
                        long_active=row["long_active"],
                        short_median_oos_cagr=float(np.median(row["short_oos"])) if row["short_oos"] else None,
                        long_median_oos_cagr=float(np.median(row["long_oos"])) if row["long_oos"] else None,
                        short_median_is_cagr=float(np.median(row["short_is"])) if row["short_is"] else None,
                        long_median_is_cagr=float(np.median(row["long_is"])) if row["long_is"] else None,
                        short_positive=float(np.mean([x > 0 for x in row["short_oos"]])) if row["short_oos"] else None))
    return out


def build_figures(study):
    figures = {}
    daily = study["daily"]
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    # Equity curves.
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    for label, color, lw in (("R1 lifecycle top-six", "#1b7f3a", 1.6),
                             ("R3 lifecycle allocation", "#c58b2a", 1.2),
                             ("FR25 SOTA", "#1f2a44", 1.6),
                             ("M1 momentum control", "#7a2e8f", 1.0),
                             ("Equal weight", "#999999", 1.0),
                             ("URTH", "#4f7cac", 1.0)):
        if label in daily:
            values = daily[label].to_numpy()
            ax.plot(daily["date"], values / values[0], label=label, color=color, lw=lw)
    ax.set_title("Pool asset-selection rules versus FR25 SOTA, 2023-2026 (5bp, next-open fills)")
    ax.legend(loc="upper left", fontsize=8)
    figures["equity"] = fig_b64(fig)
    # Drawdown.
    fig, ax = plt.subplots(figsize=(11.5, 4.4))
    for label, color in (("R1 lifecycle top-six", "#1b7f3a"),
                         ("R3 lifecycle allocation", "#c58b2a"),
                         ("FR25 SOTA", "#1f2a44")):
        if label in daily:
            values = daily[label].to_numpy()
            peak = np.maximum.accumulate(values)
            ax.plot(daily["date"], values / peak - 1, label=label, color=color, lw=1.1)
    ax.set_title("Out-of-sample drawdown")
    ax.legend(loc="lower left", fontsize=8)
    figures["drawdown"] = fig_b64(fig)
    # Class coverage.
    summary = class_summary(study["per_asset"])
    labels = [row["asset_class"] for row in summary]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(x - 0.2, [row["short_active"] for row in summary], width=0.4,
           color="#1b7f3a", label="short-range fitted")
    ax.bar(x + 0.2, [row["long_active"] for row in summary], width=0.4,
           color="#c58b2a", label="long-range fitted")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{row['asset_class']}\n(n={row['n']})" for row in summary], fontsize=8)
    ax.set_ylabel("ETFs with evidence-passing signal fit")
    ax.set_title("Where the two-horizon lifecycle found evidence across asset classes")
    ax.legend()
    figures["class_coverage"] = fig_b64(fig)
    # Annual returns R1 vs FR25.
    def annual_return(label, year):
        if label not in daily:
            return 0.0
        frame = daily[(daily["date"] >= f"{year}-01-01") & (daily["date"] <= f"{year}-12-31")]
        if len(frame) < 20:
            return 0.0
        return float(frame[label].iloc[-1] / frame[label].iloc[0] - 1.0)

    years = [2023, 2024, 2025, 2026]
    if "R1 lifecycle top-six" in daily:
        fig, ax = plt.subplots(figsize=(8.5, 4.0))
        x = np.arange(len(years))
        ax.bar(x - 0.2, [annual_return("R1 lifecycle top-six", y) for y in years], width=0.4,
               color="#1b7f3a", label="R1 life-cycle top-six")
        ax.bar(x + 0.2, [annual_return("FR25 SOTA", y) for y in years], width=0.4,
               color="#1f2a44", label="FR25 SOTA")
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.axhline(0, color="black", lw=0.5)
        ax.set_title("Calendar-year return: selection rule versus FR25")
        ax.legend()
        figures["annual"] = fig_b64(fig)
    # Selection frequency.
    selection = study["evidence"]["selection_summary"]
    freq = selection["selection_frequency"]
    top = list(freq.items())[:18]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar([s for s, _ in top], [c for _, c in top], color="#4f7cac")
    ax.set_ylabel("monthly selections")
    ax.set_title("Most frequently selected ETFs by the R1 lifecycle rule")
    ax.tick_params(axis="x", rotation=45)
    figures["selection_frequency"] = fig_b64(fig)
    return figures


def main():
    study = load_study()
    protocol = study["protocol"]
    evidence = study["evidence"]
    per_asset = study["per_asset"]
    summary = class_summary(per_asset)
    results = evidence["results"]
    benchmarks = evidence["benchmarks"]
    primary = results.get("R1 lifecycle top-six | 5bp d0", {})
    fr25 = benchmarks.get("FR25 SOTA", {})
    m1 = benchmarks.get("M1 momentum control", {})
    ew = benchmarks.get("Equal weight", {})
    urth = benchmarks.get("URTH", {})
    tilt = results.get("80% FR25 + 20% R1 lifecycle top-six (event)", {})
    tilt_monthly = results.get("80% FR25 + 20% R1 lifecycle top-six (monthly)", {})
    figures = build_figures(study)
    # Per-asset table.
    asset_rows = []
    order = sorted(per_asset, key=lambda s: (per_asset[s]["class_"], s))
    for symbol in order:
        entry = per_asset[symbol]
        s_is, s_oos = entry["short"]["is_metrics"], entry["short"]["oos_stats"]
        l_is, l_oos = entry["long"]["is_metrics"], entry["long"]["oos_stats"]
        asset_rows.append((entry["class_"], symbol,
                           pct(s_is.get("cagr")) if s_is else "&mdash;",
                           num(s_is.get("sharpe")) if s_is else "&mdash;",
                           pct(s_oos.get("cagr")) if s_oos else "&mdash;",
                           num(s_oos.get("sharpe")) if s_oos else "&mdash;",
                           pct(l_is.get("cagr")) if l_is else "&mdash;",
                           num(l_is.get("sharpe")) if l_is else "&mdash;",
                           pct(l_oos.get("cagr")) if l_oos else "&mdash;",
                           num(l_oos.get("sharpe")) if l_oos else "&mdash;",
                           "Y" if entry["short"]["evidence"] else "",
                           "Y" if entry["long"]["evidence"] else "",
                           "transfer" if entry["short"]["fallback_transfer"] or entry["long"]["fallback_transfer"] else ""))
    asset_table = table(["Class", "Symbol", "Short IS CAGR", "Short IS Sh", "Short OOS CAGR",
                         "Short OOS Sh", "Long IS CAGR", "Long IS Sh", "Long OOS CAGR",
                         "Long OOS Sh", "Short fit", "Long fit", "Fallback"], asset_rows)
    class_rows = []
    for row in summary:
        class_rows.append((row["asset_class"], row["n"], row["short_active"], row["long_active"],
                           pct(row["short_median_oos_cagr"]), pct(row["long_median_oos_cagr"]),
                           pct(row["short_positive"])))
    class_table = table(["Asset class", "ETFs", "Short evidence", "Long evidence",
                         "Median short OOS CAGR", "Median long OOS CAGR",
                         "Share short OOS > 0"], class_rows)
    # Result tables.
    def result_row(label, entry):
        if not entry:
            return None
        m = entry["metrics"]
        return (label, pct(m["cagr"]), num(m["sharpe"]), pct(m["maxdd"]), num(m["calmar"]),
                pct(m["exposure"]), num(m.get("annual_turnover")), num(m.get("annual_cost_bps")))
    base_rows = []
    for label in ("R1 lifecycle top-six", "R2 lifecycle top-six, no momentum gate",
                  "R3 lifecycle allocation", "R4 lifecycle-gated momentum"):
        row = result_row(label + " (event)", results.get(f"{label} | 5bp d0"))
        if row:
            base_rows.append(row)
        row = result_row(label + " (monthly)", results.get(f"{label} monthly | 5bp d0"))
        if row:
            base_rows.append(row)
    benchmark_rows = []
    for label in ("FR25 SOTA", "M1 momentum control", "Equal weight", "URTH", "BIL"):
        m = benchmarks.get(label)
        if m:
            benchmark_rows.append((label, pct(m["cagr"]), num(m["sharpe"]), pct(m["maxdd"]),
                                   num(m["calmar"]), pct(m["exposure"]), "&mdash;", "&mdash;"))
    portfolio_table = table(["Portfolio", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure",
                             "Turnover", "Cost bps"], benchmark_rows + base_rows)
    # Frictions for R1.
    friction_rows = []
    for cost, delay in ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1), (10.0, 1)):
        for tag, key in (("event", f"R1 lifecycle top-six | {cost:g}bp d{delay}"),
                         ("monthly", f"R1 lifecycle top-six monthly | {cost:g}bp d{delay}")):
            entry = results.get(key)
            if entry:
                m = entry["metrics"]
                friction_rows.append((tag, f"{cost:g}bp, delay {delay}", pct(m["cagr"]),
                                      num(m["sharpe"]), pct(m["maxdd"]), num(m["calmar"]),
                                      pct(m["exposure"]), num(m.get("annual_turnover")),
                                      num(m.get("annual_cost_bps"))))
    friction_table = table(["Clock", "Assumption", "CAGR", "Sharpe", "Max DD", "Calmar",
                            "Exposure", "Turnover", "Cost bps"], friction_rows)
    # Tilt table.
    tilt_rows = []
    for label, entry in (("FR25 SOTA", benchmarks.get("FR25 SOTA")),
                         ("80% FR25 + 20% R1 (event)", tilt),
                         ("80% FR25 + 20% R1 (monthly)", tilt_monthly),
                         ("80% FR25 + 20% R3 (event)",
                          results.get("80% FR25 + 20% R3 lifecycle allocation (event)")),
                         ("80% FR25 + 20% R3 (monthly)",
                          results.get("80% FR25 + 20% R3 lifecycle allocation (monthly)"))):
        if not entry:
            continue
        m = entry.get("metrics", entry)
        tilt_rows.append((label, pct(m["cagr"]), num(m["sharpe"]), pct(m["maxdd"]),
                          num(m["calmar"]), pct(m["exposure"])))
    tilt_table = table(["Portfolio", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure"], tilt_rows)
    # Selection summary.
    selection = evidence["selection_summary"]
    frequency = list(selection["selection_frequency"].items())[:15]
    frequency_table = table(["ETF", "Monthly selections"], frequency)
    class_slots = selection["slot_share_by_class"]
    class_slot_table = table(["Asset class", "Share of selected slots"],
                             [(k, pct(v)) for k, v in class_slots.items()])
    # Annual table R1/FR25.
    daily_df = study["daily"]

    def year_return(label, year):
        if label not in daily_df:
            return None
        frame = daily_df[daily_df["date"] >= f"{year}-01-01"]
        frame = frame[frame["date"] <= f"{year}-12-31"]
        if len(frame) < 20:
            return None
        return float(frame[label].iloc[-1] / frame[label].iloc[0] - 1.0)

    annual_rows = []
    for year in (2023, 2024, 2025, 2026):
        annual_rows.append((year, pct(year_return("R1 lifecycle top-six", year)),
                            pct(year_return("R3 lifecycle allocation", year)),
                            pct(year_return("80% FR25 + 20% R1 lifecycle top-six (event)", year)),
                            pct(year_return("FR25 SOTA", year)),
                            pct(year_return("M1 momentum control", year))))
    annual_table = table(["Year", "R1 top-six", "R3 allocation", "80/20 FR25+R1", "FR25 SOTA",
                          "M1 control"], annual_rows)
    # Verdict text numbers.
    def m_of(entry):
        return entry.get("metrics", entry)
    p_primary = m_of(primary) if primary else {}
    p_fr25 = m_of(fr25) if fr25 else {}
    p_m1 = m_of(m1) if m1 else {}
    p_ew = m_of(ew) if ew else {}
    p_urth = m_of(urth) if urth else {}
    beats = (p_primary.get("sharpe", 0) > p_fr25.get("sharpe", 0)
             and p_primary.get("cagr", -1) > p_fr25.get("cagr", 1))
    verdict = (
        f"R1 event OOS: CAGR {pct(p_primary.get('cagr'))}, Sharpe {num(p_primary.get('sharpe'))}, "
        f"DD {pct(p_primary.get('maxdd'))} versus FR25 {pct(p_fr25.get('cagr'))}/"
        f"{num(p_fr25.get('sharpe'))}/{pct(p_fr25.get('maxdd'))}. "
        + ("It beats FR25 on both net CAGR and Sharpe." if beats else
           "It does not beat FR25 on both net CAGR and Sharpe."))
    css = """
    :root { --ink:#1c2533; --muted:#5b6675; --line:#d9dee6; --bg:#fbfbfc; --accent:#1b7f3a;
            --accent2:#b23b3b; --blue:#4f7cac; --gold:#c58b2a; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink);
           font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
    header { background:#16202e; color:#fff; padding:34px 6vw 28px; }
    header h1 { margin:0 0 6px; font-size:26px; }
    header .sub { color:#c4cdd9; max-width:1150px; }
    header .meta { margin-top:14px; color:#9fb0c4; font-size:12.5px; }
    main { max-width:1180px; margin:0 auto; padding:26px 22px 80px; }
    h2 { margin:46px 0 14px; font-size:22px; border-bottom:2px solid var(--line); padding-bottom:6px; }
    h3 { margin:26px 0 10px; font-size:16.5px; }
    .lede { font-size:16px; }
    .callout { background:#fff; border-left:4px solid var(--blue); padding:12px 16px; margin:16px 0;
               border-radius:4px; box-shadow:0 1px 2px rgba(0,0,0,.05); }
    .callout.good { border-left-color:var(--accent); }
    .callout.warn { border-left-color:var(--accent2); }
    .kpi { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }
    .kpi div { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px; }
    .kpi .v { font-size:22px; font-weight:650; }
    .kpi .l { color:var(--muted); font-size:12px; }
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
    code { font-family:Consolas,monospace; font-size:13px; }
    .note { color:var(--muted); font-size:12.5px; }
    a { color:#1c5f9e; }
    """
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Two-horizon lifecycle across the 52-ETF pool and versus FR25</title><style>{css}</style></head><body>
<header>
<h1>Two-horizon lifecycle across the 52-ETF pool: per-ETF signals and an asset-selection test versus FR25</h1>
<div class="sub">The sealed short-range and long-range GLD lifecycle algorithms were fitted independently
per ETF on pre-2023 sessions only, then used as an asset-selection signal on the frozen 52-ETF pool.
The selection rules are predeclared and replayed through the same shared accounting engine that reproduces
the frozen FR25 SOTA path exactly.</div>
<div class="meta">Study <code>{protocol['identity']}</code> · panel SHA-256 <code>{protocol['data']['panel_sha256'][:16]}...</code>
· research only, no monitoring or trade authority</div>
</header>
<main>
<p class="lede">{verdict} The honest short version: this is a broad, deliberately modest per-ETF fit, and the
selection rule is a new hypothesis tested once on the already-inspected 2023-2026 interval.</p>
<div class="kpi">
<div><div class="v">{pct(p_primary.get('cagr'))}</div><div class="l">R1 selection OOS CAGR</div></div>
<div><div class="v">{num(p_primary.get('sharpe'))}</div><div class="l">R1 selection OOS Sharpe</div></div>
<div><div class="v">{pct(p_primary.get('maxdd'))}</div><div class="l">R1 selection OOS max DD</div></div>
<div><div class="v">{num(evidence['correlation_rule_vs_fr25'], 2)}</div><div class="l">R1/FR25 daily-return correlation</div></div>
</div>
<div class="callout {'good' if beats else 'warn'}"><strong>Verdict versus SOTA.</strong> {verdict}
The best lifecycle-only rule in this sweep is R4 (active lifecycles ranked by momentum) at
{pct(results.get('R4 lifecycle-gated momentum | 5bp d0', {}).get('metrics', {}).get('cagr'))} CAGR /
{num(results.get('R4 lifecycle-gated momentum | 5bp d0', {}).get('metrics', {}).get('sharpe'))} Sharpe
(event) and {pct(results.get('R4 lifecycle-gated momentum monthly | 5bp d0', {}).get('metrics', {}).get('cagr'))}
/ {num(results.get('R4 lifecycle-gated momentum monthly | 5bp d0', {}).get('metrics', {}).get('sharpe'))}
(monthly); neither beats FR25 on both dimensions. The predeclared 80/20 FR25+R1 tilt gives
{pct(tilt.get('metrics', {}).get('cagr'))} CAGR / {num(tilt.get('metrics', {}).get('sharpe'))} Sharpe /
{pct(tilt.get('metrics', {}).get('maxdd'))} max DD versus FR25
{pct(p_fr25.get('cagr'))} / {num(p_fr25.get('sharpe'))} / {pct(p_fr25.get('maxdd'))}: it improves
drawdown and marginally improves Sharpe while giving up return, so it is a risk-shaping candidate, not a
return replacement.
FR25 SOTA: CAGR {pct(p_fr25.get('cagr'))}, Sharpe {num(p_fr25.get('sharpe'))}, DD {pct(p_fr25.get('maxdd'))},
Calmar {num(p_fr25.get('calmar'))}. M1 control: {pct(p_m1.get('cagr'))}/{num(p_m1.get('sharpe'))}/
{pct(p_m1.get('maxdd'))}; equal weight {pct(p_ew.get('cagr'))}/{num(p_ew.get('sharpe'))};
URTH {pct(p_urth.get('cagr'))}/{num(p_urth.get('sharpe'))}. The 80/20 FR25+lifecycle tilt and the
event/monthly clock controls are in section 4.</div>

<h2>1. Design and predeclaration</h2>
<ul>
<li><strong>Pool.</strong> 52 audited ETFs (US and international equity, sectors, fixed income/credit,
commodities, real assets). Panel and per-asset histories are the frozen v2 batch; every panel close equals
the per-asset audited close exactly (max absolute difference {protocol['data']['per_asset_close_max_abs_diff']}).</li>
<li><strong>Per-ETF fits.</strong> Each ETF gets an independent pre-2023 fit in each structural domain:
{N_RANDOM} random bounded vectors + the sealed GLD vector + {N_ANCHOR_MUTATIONS} anchor mutations screened at
5bp; the top {TOP_PER_DOMAIN} replay across 5/10/20bp and +1 session delay; evidence requires at least 5 closed
IS episodes and 5% exposure; one vector is sealed per ETF and domain. ETFs with fewer than 500 evaluable IS
sessions inherit the sealed GLD vector for that domain.</li>
<li><strong>Causality.</strong> Fits and selection use sessions through {protocol['chronology']['fit_end']} only.
The portfolio window is {protocol['chronology']['oos_start']} to {protocol['chronology']['oos_end']}
({protocol['chronology']['oos_sessions']} sessions). Sleeve state and score are close-time outputs; fills are the
next open; costs are charged per traded side.</li>
<li><strong>Accounting.</strong> The same shared application engine that produced the frozen FR25/M1 paths.
Its FR25 replay matches the frozen FR25 SOTA path with a maximum relative deviation of
{num(evidence['integrity'].get('FR25 max relative deviation vs frozen path'), 6)}.</li>
<li><strong>Selection rules (predeclared).</strong> R1 lifecycle top-six: active sleeve ETFs with positive
126-session momentum, ranked by combined extension score, up to six names, inverse-vol weights, 45% cap,
98% budget, cash for unfilled slots. R2 drops the momentum gate. R3 allocates to every active ETF by sleeve
exposure x inverse-vol. R4 ranks active ETFs by 126-session momentum. Event controls adopt on held-name exits
or when the L1 target change exceeds 0.10, plus monthly anchors. Monthly controls rebalance only at month-end.
The 80/20 tilt blends 0.8 x frozen FR25 targets with 0.2 x lifecycle target.</li>
<li><strong>No OOS tuning.</strong> Rules, caps, thresholds and frictions are fixed before the 2023+ replay.</li>
</ul>

<h2>2. Where the lifecycle found signals across asset classes</h2>
{class_table}
<div class="caption">"Evidence" counts ETFs where the per-ETF fit met the minimum trade/exposure rule. Median
OOS CAGR is the sleeve's own standalone 2023-2026 result (cash when flat); it is not the selection-rule result.</div>
<img class="fig" src="data:image/png;base64,{figures['class_coverage']}" alt="class coverage">
<div class="caption">Evidence-passing fits by asset class for the short-range and long-range domains. Equity
and commodity ETFs dominate; the long-range domain only finds a handful of qualifying histories.</div>
<h3>2.1 Per-ETF standalone sleeve results</h3>
<div class="scroll">{asset_table}</div>
<div class="caption">Every ETF's independently fitted short-range and long-range sleeve under its own accounting
(cash when flat, 5bp). "Fallback" means the ETF was too short for a per-ETF IS fit and inherited the sealed GLD
vector. These are signal-quality diagnostics, not portfolio results.</div>

<h2>3. Asset-selection portfolios versus the SOTA</h2>
{portfolio_table}
<div class="caption">2023-01-03 to 2026-10-12, 5bp per side, next-open fills, 98% budget, 45% cap, zero cash
yield. Event = mandatory lifecycle exits plus 10% L1 target-change adoptions with monthly anchors; monthly = month-end only.
Sharpe uses zero risk-free rate. Turnover and cost columns are annualised. The frozen M1 control path is cash-heavy
(58% average exposure), which produces its high but uninformative near-zero-vol Sharpe; it is shown as the frozen control,
not as a like-for-like SOTA peer.</div>
<img class="fig" src="data:image/png;base64,{figures['equity']}" alt="equity">
<div class="caption">Growth of 1.0 for the selection rules and benchmarks. FR25 SOTA (dark) and the lifecycle
top-six rule (green); the long-range-only allocation is the gold line.</div>
<img class="fig" src="data:image/png;base64,{figures['drawdown']}" alt="drawdown">
<div class="caption">Out-of-sample drawdowns.</div>
<h3>3.1 Calendar years and the two clocks</h3>
{annual_table}
{figures.get('annual', '') and '<img class="fig" src="data:image/png;base64,' + figures['annual'] + '" alt="annual">'}
<div class="caption">Calendar-year returns.</div>
<h3>3.2 Cost and execution-delay sensitivity</h3>
{friction_table}
<div class="caption">The selection rules stay positive at 20bp and one extra execution session; the gap to FR25
is not a cost artifact.</div>
<h3>3.3 What the primary rule held</h3>
{frequency_table}
{class_slot_table}
<div class="caption">R1 monthly selection frequency and the asset-class share of selected slots. Average holdings
per rebalance: {num(evidence['selection_summary']['average_holdings'])} of 6 slots over
{evidence['selection_summary']['rebalances']} monthly decisions.</div>
<img class="fig" src="data:image/png;base64,{figures['selection_frequency']}" alt="selection frequency">

<h2>4. Combining with FR25: the 80/20 tilt</h2>
{tilt_table}
<div class="caption">The tilt keeps FR25 as the core and adds a small lifecycle sleeve. It is compared with
FR25 SOTA on the same window; no tilt weight was chosen on OOS data.</div>

<h2>5. Verdict, interpretation and limitations</h2>
<ul>
<li><strong>Does it beat the SOTA?</strong> {verdict} This answer is for the predeclared rules and the current
52-ETF cohort. The selection sleeve's value, if any, is in diversification/risk-shaping rather than a clean
return replacement.</li>
<li><strong>Breadth over depth.</strong> The per-ETF search is much smaller than the GLD deep fits; it is a
breadth test. A weak per-ETF fit is not evidence that the lifecycle fails on that asset, only that this budget
did not find an evidence-passing rule. Assets under 500 evaluable IS sessions inherit GLD and are flagged.</li>
<li><strong>Chronology.</strong> 2023-2026 has been inspected in prior work and by the operator; this is a
development retest, not an untouched holdout. The GLD deep-dive's 2005-2015 refit validation failed on
2016-2022, so the procedure remains data-hungry.</li>
<li><strong>Selection and accounting.</strong> The rules are long-only, monthly/event, capped and inverse-vol;
the benchmark paths are frozen decisions repriced on the same batch through the same engine. No shorting,
leverage, FX or intraday execution is modelled. Cash earns zero.</li>
<li><strong>No authority.</strong> No monitoring, promotion, funding, allocation or broker action follows.</li>
</ul>

<h2>6. Files and reproduction</h2>
<ul>
<li><a href="per-asset.csv">per-asset.csv</a> — per-ETF fit, evidence and OOS diagnostics.</li>
<li><a href="daily-nav.csv">daily-nav.csv</a> — daily NAV for every rule, tilt and benchmark.</li>
<li><a href="evidence.json">evidence.json</a> — full selection results, friction cases, annual returns,
selection frequencies, integrity checks and protocol pointer.</li>
<li><a href="protocol.json">protocol.json</a> — predeclared pool, fit and selection design.</li>
</ul>
<p class="note">Reproduction: <code>python scripts/run_gld_lifecycle_pool.py prepare|fit|portfolio</code>
then <code>python scripts/build_gld_lifecycle_pool_report.py</code>. Frozen root
<code>var/research/{protocol['identity']}</code>. Research only.</p>
</main></body></html>"""
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(VAR / "portfolio" / "daily-nav.csv", PUB / "daily-nav.csv")
    shutil.copyfile(VAR / "portfolio" / "per-asset.csv", PUB / "per-asset.csv")
    shutil.copyfile(VAR / "portfolio" / "evidence.json", PUB / "evidence.json")
    shutil.copyfile(VAR / "protocol.json", PUB / "protocol.json")
    files = sorted(p for p in PUB.iterdir() if p.is_file() and p.name != "manifest.json")
    (PUB / "manifest.json").write_text(json.dumps(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2),
        encoding="utf-8")
    print(json.dumps({"public": str(PUB), "html_bytes": len(html), "files": len(files)}, indent=1))


if __name__ == "__main__":
    main()
