"""Build the cost/delay-charged conditional FR25 overlay robustness report."""
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
VAR = ROOT / "var" / "research" / "gld-lifecycle-overlay-robustness-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-overlay-robustness-20261019-v1"


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
        candidate=read_json(VAR / "candidate.json"),
        daily=pd.read_csv(VAR / "daily-nav.csv", parse_dates=["date"]),
    )


def build_figures(study):
    figures = {}
    daily = study["daily"]
    evidence = study["evidence"]
    best = evidence["best_conditional"]
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    for label, color, lw in (
            ("FR25 SOTA", "#1f2a44", 1.7),
            (best, "#1b7f3a", 1.6),
            ("fixed_monthly_conditional", "#c58b2a", 1.2),
            ("dynamic_unconditional_t0.10", "#7a2e8f", 1.0),
            ("dynamic_random_seed11_t0.00", "#999999", 1.0),
            ("Equal weight", "#bbb3c8", 0.9)):
        if label in daily:
            values = daily[label].to_numpy(float)
            ax.plot(daily["date"], values / values[0], label=label, color=color, lw=lw)
    ax.set_title("Cost-charged conditional FR25 overlay versus benchmarks, 2023-2026")
    ax.legend(loc="upper left", fontsize=7.5)
    figures["equity"] = fig_b64(fig)

    fig, ax = plt.subplots(figsize=(11.5, 4.3))
    for label, color in (("FR25 SOTA", "#1f2a44"), (best, "#1b7f3a"),
                         ("fixed_monthly_conditional", "#c58b2a")):
        if label in daily:
            values = daily[label].to_numpy(float)
            peak = np.maximum.accumulate(values)
            ax.plot(daily["date"], values / peak - 1, label=label, color=color, lw=1.1)
    ax.set_title("Drawdown: frozen FR25 versus the best conditional overlay and its fixed-monthly control")
    ax.legend(loc="lower left", fontsize=8)
    figures["drawdown"] = fig_b64(fig)

    # Robustness of the best scenario across costs/delays versus matched FR25.
    robustness = evidence["candidate"]["robustness_versus_matched_fr25"]
    labels, sharpes, dds = [], [], []
    for key, name in (("base", "5bp"), ("cost_10bp", "10bp"), ("cost_20bp", "20bp"),
                      ("delay_1", "+1 delay")):
        row = robustness.get(key)
        if not row:
            continue
        results = evidence["results"]
        cost = row["cost_bp"]
        delay = row["delay"]
        m = results[f"{best} | {cost:g}bp d{delay}"]["metrics"]
        labels.append(name)
        sharpes.append(m["sharpe"])
        dds.append(m["maxdd"])
    fig, ax = plt.subplots(figsize=(9.0, 4.0))
    x = np.arange(len(labels))
    ax.bar(x - 0.2, sharpes, width=0.4, color="#1b7f3a", label="conditional overlay Sharpe")
    bench_sharpes = [evidence["benchmarks"][b]["sharpe"] for b in
                     ("FR25 SOTA", "FR25 10bp", "FR25 20bp", "FR25 +1 delay")]
    ax.bar(x + 0.2, bench_sharpes, width=0.4, color="#1f2a44", label="matched FR25 Sharpe")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Sharpe under cost and delay stress: overlay versus frozen FR25 at the same assumption")
    ax.legend(fontsize=8)
    figures["robustness"] = fig_b64(fig)
    return figures


def main():
    study = load_study()
    evidence = study["evidence"]
    candidate = study["candidate"]
    results = evidence["results"]
    benchmarks = evidence["benchmarks"]
    best = evidence["best_conditional"]
    figures = build_figures(study)
    fr25 = benchmarks["FR25 SOTA"]
    best_m = candidate["best_5bp"]
    robustness = candidate["robustness_versus_matched_fr25"]
    # Main scenario table (5bp d0).
    rows = []
    for label in ("FR25 SOTA", "Equal weight", "URTH"):
        m = benchmarks[label]
        rows.append((label, pct(m["cagr"]), num(m["sharpe"]), num(m["sortino"]),
                     pct(m["maxdd"]), num(m["calmar"]), "&mdash;", "&mdash;", "&mdash;"))
    scenario_labels = [
        ("dynamic_conditional_t0.00", "dynamic conditional, trigger 0%"),
        ("dynamic_conditional_t0.05", "dynamic conditional, trigger 5%"),
        ("dynamic_conditional_t0.10", "dynamic conditional, trigger 10% (candidate)"),
        ("fixed_monthly_conditional", "fixed-monthly conditional control"),
        ("dynamic_unconditional_t0.10", "dynamic unconditional control"),
        ("dynamic_random_seed7_t0.00", "random-condition control, seed 7"),
        ("dynamic_random_seed11_t0.00", "random-condition control, seed 11"),
        ("dynamic_random_seed23_t0.00", "random-condition control, seed 23"),
    ]
    for key, label in scenario_labels:
        row = results.get(f"{key} | 5bp d0")
        if not row:
            continue
        m = row["metrics"]
        rows.append((label, pct(m["cagr"]), num(m["sharpe"]), num(m["sortino"]),
                     pct(m["maxdd"]), num(m["calmar"]), num(m["annual_turnover"]),
                     num(m.get("annual_cost_bps")), str(row["rebalances"])))
    scenario_table = table(["Scenario", "CAGR", "Sharpe", "Sortino", "Max DD", "Calmar",
                            "Turnover", "Cost bps", "Rebalances"], rows)
    # Robustness table.
    robust_rows = []
    for key, name in (("base", "5bp, no delay"), ("cost_10bp", "10bp, no delay"),
                      ("cost_20bp", "20bp, no delay"), ("delay_1", "5bp, +1 session")):
        gate = robustness.get(key)
        if not gate:
            continue
        m = results[f"{best} | {gate['cost_bp']:g}bp d{gate['delay']}"]["metrics"]
        passed = [name for name, ok in (("Sharpe", gate["sharpe"]), ("Sortino", gate["sortino"]),
                                        ("maxDD", gate["maxdd"]), ("Calmar", gate["calmar"]),
                                        ("CAGR", gate["cagr"])) if ok]
        robust_rows.append((name, pct(m["cagr"]), num(m["sharpe"]), num(m["sortino"]),
                            pct(m["maxdd"]), num(m["calmar"]),
                            f"{gate['n_risk_measures']}/4", ", ".join(passed)))
    robust_table = table(["Assumption", "CAGR", "Sharpe", "Sortino", "Max DD", "Calmar",
                          "Risk measures beaten", "Measures beaten"], robust_rows)
    # Gate table for all scenarios.
    gate_rows = []
    for row in evidence["gate"]:
        gate_rows.append((row["scenario"], "Y" if row["beats_sharpe"] else "",
                          "Y" if row["beats_maxdd"] else "",
                          "Y" if row["beats_calmar"] else "",
                          "Y" if row["beats_return"] else "",
                          f"{row['n_measures']}/3"))
    gate_table = table(["Scenario", "Sharpe", "Max DD", "Calmar", "CAGR", "Score"], gate_rows)
    # Candidate summary numbers.
    sharpe_delta = best_m["sharpe"] - fr25["sharpe"]
    dd_delta = best_m["maxdd"] - fr25["maxdd"]
    calmar_delta = best_m["calmar"] - fr25["calmar"]
    gate = candidate["gate"]
    gate_score = f"{gate['n_measures']}/3"
    delay_metrics = results[f"{best} | 5bp d1"]["metrics"]
    verdict = (
        f"The best cost-charged conditional overlay ({best.replace('_', ' ')}) delivers "
        f"{pct(best_m['cagr'])} CAGR / Sharpe {num(best_m['sharpe'])} / Sortino "
        f"{num(best_m['sortino'])} / max DD {pct(best_m['maxdd'])} / Calmar {num(best_m['calmar'])} "
        f"at 5bp, versus frozen FR25 {pct(fr25['cagr'])} / {num(fr25['sharpe'])} / "
        f"{num(fr25['sortino'])} / {pct(fr25['maxdd'])} / {num(fr25['calmar'])}. It beats FR25 on "
        f"all four risk-adjusted measures (Sharpe {sharpe_delta:+.3f}, max DD {dd_delta:+.2%}, "
        f"Calmar {calmar_delta:+.2f}) at 5bp, 10bp and 20bp, but gives up "
        f"{pct(fr25['cagr'] - best_m['cagr'])} CAGR and fails the +1-session delay test "
        f"(Sharpe {num(delay_metrics['sharpe'])} versus matched FR25 "
        f"{num(benchmarks['FR25 +1 delay']['sharpe'])}).")
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
<title>Cost-charged conditional FR25 + life-cycle overlay, fixed monthly versus dynamic rebalancing</title>
<style>{css}</style></head><body>
<header>
<h1>Cost-charged conditional 80/20 FR25 + Rule A short overlay: fixed monthly versus dynamic rebalancing</h1>
<div class="sub">The overlay is now implemented as one portfolio in the shared application accounting engine:
80% of the target budget follows the frozen FR25 monthly weights, 20% follows the Rule A short-only
daily sleeve only in months whose pre-2023-calibrated stable life-cycle breadth is high. Every
rebalance and inter-sleeve flow is charged, and execution delay is explicit. The dynamic
target-change clock is tested against the fixed-monthly control and against unconditional and
random-condition counterfactuals.</div>
<div class="meta">Study <code>{evidence['identity']}</code> · research only · candidate for monitoring
review, not a monitored or funded strategy</div>
</header>
<main>
<p class="lede">{verdict}</p>
<div class="kpi">
<div><div class="v">{pct(best_m['cagr'])}</div><div class="l">candidate CAGR</div></div>
<div><div class="v">{num(best_m['sharpe'])}</div><div class="l">candidate Sharpe</div></div>
<div><div class="v">{pct(best_m['maxdd'])}</div><div class="l">candidate max DD</div></div>
<div><div class="v">{gate_score}</div><div class="l">risk measures beaten vs FR25 (5bp)</div></div>
</div>
<div class="callout good"><strong>Promotion status: research candidate only.</strong> The operator
asked to keep this as a potential candidate to add to monitored. This study provides the cost/delay
evidence and the candidate dossier (<code>candidate.json</code>), but no monitored, funded or
broker-authoritative strategy was created or changed. Adding it to monitoring requires an
app-tracked versioned strategy, paper-trading evidence, operator approval, risk limits and a
rollback plan.</div>

<h2>1. Construction and test design</h2>
<ul>
<li><strong>Portfolio.</strong> One shared-engine portfolio: FR25 frozen target weights at 80% of the
budget, Rule A short-only sleeve at 20% when the condition is true. Blended targets are executed at
the next open; the engine charges every trade, so both intra-FR25 and inter-sleeve turnover are in the
costs.</li>
<li><strong>Condition.</strong> Sleeve enabled only when stable union-signal breadth is at or above the
pre-2023 median ({evidence['threshold']:.0f} of 52 active names; condition true in
{pct(evidence['condition_share'])} of 2023-2026 months). Known at the decision close.</li>
<li><strong>Fixed-monthly control.</strong> Adopt the blended target only at FR25 month-end decisions
(46 rebalances); the sleeve snapshot is frozen between month-ends.</li>
<li><strong>Dynamic candidate.</strong> Adopt at month-end anchors and whenever the latest theoretical
blended target differs from the last adopted target by an L1 threshold; thresholds 0%, 5% and 10% are
tested, with the 10% version selected as the candidate by the multi-measure gate.</li>
<li><strong>Controls.</strong> Unconditional sleeve (always 20%) and random-condition counterfactuals
with the same number of true months (three seeds).</li>
<li><strong>Stress.</strong> 5/10/20bp per side and 5bp with one extra execution session; the overlay is
compared with the frozen FR25 path at the same friction.</li>
</ul>

<h2>2. Results at 5bp, next-open fills, 2023-2026</h2>
{scenario_table}
<div class="caption">All scenarios use the same engine and data. The candidate is
<strong>{best}</strong>; random-condition seeds preserve the number of true months but shuffle which
months. Turnover/cost are annualised; FR25 benchmark rows have no overlay turnover.</div>
<img class="fig" src="data:image/png;base64,{figures['equity']}" alt="equity">
<div class="caption">Frozen FR25 (dark), candidate dynamic conditional overlay (green), fixed-monthly
conditional control (gold), unconditional dynamic control (purple), random-condition control (grey).</div>
<img class="fig" src="data:image/png;base64,{figures['drawdown']}" alt="drawdown">
<div class="caption">Drawdowns: the overlay's advantage is risk reduction, not return.</div>

<h2>3. Multi-measure gate and robustness</h2>
<p>The candidate beats FR25 on all four risk-adjusted measures at 5bp, and repeats that at 10bp and
20bp; it does not beat FR25's CAGR at any assumption, and it fails the +1-session delay test except
on max drawdown. Those are the two honest caveats.</p>
{robust_table}
<div class="caption">Same-assumption comparison: each row compares the candidate with the frozen FR25
path built at that friction. "Risk measures beaten" counts Sharpe, Sortino, max DD and Calmar out
of four.</div>
<img class="fig" src="data:image/png;base64,{figures['robustness']}" alt="robustness">
<div class="caption">Sharpe under cost and delay stress: candidate versus matched FR25. The cost
robustness is clear; the delay case is not.</div>
<h3>3.1 Full gate table</h3>
{gate_table}
<div class="caption">Gate versus frozen FR25 at 5bp. Only the dynamic conditional variants beat
Sharpe, max DD and Calmar; the fixed-monthly conditional beats Sharpe and max DD but not Calmar; the
unconditional and random controls do not beat Sharpe.</div>

<h2>4. Candidate dossier</h2>
<pre class="note" style="white-space:pre-wrap;background:#fff;border:1px solid var(--line);border-radius:6px;padding:12px">{json.dumps(candidate, indent=2)}</pre>

<h2>5. Verdict</h2>
<ul>
<li><strong>Dynamic target-change rebalancing beats the fixed-monthly control on the risk measures</strong>
(the fixed-monthly conditional is Sharpe {num(results['fixed_monthly_conditional | 5bp d0']['metrics']['sharpe'])}
/ DD {pct(results['fixed_monthly_conditional | 5bp d0']['metrics']['maxdd'])} / Calmar
{num(results['fixed_monthly_conditional | 5bp d0']['metrics']['calmar'])}; the candidate is
Sharpe {num(best_m['sharpe'])} / DD {pct(best_m['maxdd'])} / Calmar {num(best_m['calmar'])}).</li>
<li><strong>The condition matters:</strong> the unconditional dynamic control does not beat FR25 Sharpe,
and the three random-condition seeds do not beat it on more than two measures; the real condition
beats it on all four risk-adjusted measures.</li>
<li><strong>It is not a return improvement:</strong> every conditional variant gives up CAGR versus
FR25. It is a risk-shaping overlay.</li>
<li><strong>Delay remains the weak spot:</strong> at +1 session the candidate's Sharpe/Calmar/Sortino
fall below matched FR25. Any monitoring candidate must be re-evaluated with the actual execution clock
and should not be promoted on the 5bp result alone.</li>
<li><strong>No authority change:</strong> research candidate only; no monitored strategy, allocation,
funding or broker change.</li>
</ul>

<h2>6. Files and reproduction</h2>
<ul>
<li><a href="daily-nav.csv">daily-nav.csv</a> — daily NAV for all scenarios and benchmarks.</li>
<li><a href="scenarios.csv">scenarios.csv</a> — all results at every cost/delay.</li>
<li><a href="candidate.json">candidate.json</a> — candidate dossier and promotion prerequisites.</li>
<li><a href="evidence.json">evidence.json</a> — full protocol, gate, robustness and protocol metadata.</li>
</ul>
<p class="note">Reproduction: <code>python scripts/run_gld_lifecycle_overlay_robustness.py</code> then
<code>python scripts/build_gld_lifecycle_overlay_report.py</code>. Research only.</p>
</main></body></html>"""
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(VAR / "daily-nav.csv", PUB / "daily-nav.csv")
    shutil.copyfile(VAR / "scenarios.csv", PUB / "scenarios.csv")
    shutil.copyfile(VAR / "candidate.json", PUB / "candidate.json")
    shutil.copyfile(VAR / "evidence.json", PUB / "evidence.json")
    files = sorted(p for p in PUB.iterdir() if p.is_file() and p.name != "manifest.json")
    (PUB / "manifest.json").write_text(json.dumps(
        {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2),
        encoding="utf-8")
    print(json.dumps({"public": str(PUB), "html_bytes": len(html), "files": len(files)}, indent=1))


if __name__ == "__main__":
    main()
