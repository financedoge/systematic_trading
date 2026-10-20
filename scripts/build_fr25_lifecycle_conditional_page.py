"""Build the versioned FR25 + life-cycle conditional candidate and its full strategy page.

Research/paper candidate only: this script freezes the specification, recomputes the
latest target and held weights, writes machine-readable artifacts and renders a full
strategy page in the project's research/strategy-page format. It does not register a
monitored strategy, change an allocation, or touch broker/approval state.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"D:\projects\systematic_trading")
OUT = ROOT / "research" / "fr25-lifecycle-conditional-v1"
VAR = ROOT / "var" / "research" / "fr25-lifecycle-conditional-v1"
OVERLAY_VAR = ROOT / "var" / "research" / "gld-lifecycle-overlay-robustness-20261019-v1"
V2 = ROOT / "var" / "research" / "range-breakout-20261018-v2"
OOS_START = "2023-01-03"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(V2))
from run_gld_lifecycle_pool import load_recipe  # noqa: E402
from run_gld_lifecycle_overlay_robustness import (build_inputs, build_scenarios,  # noqa: E402
                                                  metrics, sleeve_state_series,
                                                  SLEEVE_WEIGHT)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False, default=_jsonable),
                          encoding="utf-8")


def _jsonable(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    raise TypeError(type(value))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pct(value, digits=2):
    return "&mdash;" if value is None else f"{100.0 * value:.{digits}f}%"


def num(value, digits=2):
    return "&mdash;" if value is None else f"{value:.{digits}f}"


def build_tables_style():
    return """
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
    .scroll { max-height:520px; overflow:auto; border:1px solid var(--line); border-radius:6px; }
    .scroll table.data { margin:0; }
    img.fig { width:100%; height:auto; display:block; margin:12px 0 6px;
              border:1px solid var(--line); border-radius:6px; background:#fff; }
    .caption { color:var(--muted); font-size:12.5px; margin:2px 0 18px; }
    code { font-family:Consolas,monospace; font-size:13px; } .note { color:var(--muted); font-size:12.5px; }
    .flow { display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin:14px 0; }
    .flow div { background:#fff; border:1px solid var(--line); border-left:3px solid var(--blue);
                border-radius:5px; padding:10px; font-size:12px; }
    .risk { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }
    .risk div { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px; }
    a { color:#1c5f9e; }
    """


def table(headers, rows):
    out = ['<table class="data"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def fig_b64(fig):
    import io
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return __import__("base64").b64encode(buffer.getvalue()).decode("ascii")


def main():
    VAR.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    panel, order, monthly, condition, threshold, sleeve_targets, sleeve_indices = build_inputs()
    random_condition = {}
    scenarios = build_scenarios(panel, order, monthly, condition, sleeve_targets,
                                sleeve_indices, random_condition)
    label = "dynamic_conditional_t0.10"
    targets, indices = scenarios[label]
    # Replay the candidate in the shared accounting engine.
    sys.path.insert(0, str(V2))
    from run_range_breakout import Replay
    recipe = load_recipe()
    replay = Replay(panel, recipe, OOS_START)
    compact, _, fills = replay.run(targets, indices, 5.0, 0)
    days = pd.to_datetime(panel["days"])
    oos_days = days[-len(compact["nav"]):]
    fr25 = np.column_stack([panel["fr25"], np.zeros(panel["close"].shape[0])])
    fr25_replay, _, _ = replay.run(fr25, monthly, 5.0, 0)
    frozen_fr25 = np.load(V2 / "pool" / "paths" / "FR25_c5d0.npz")["nav"]
    benchmarks = {}
    for name, stem in (("FR25 SOTA", "FR25_c5d0"), ("Equal weight", "equal_weight_c5d0"),
                       ("URTH", "URTH_c5d0"), ("BIL", "BIL_c5d0")):
        d = np.load(V2 / "pool" / "paths" / f"{stem}.npz")
        benchmarks[name] = dict(nav=d["nav"], exposure=d["exposure"])
    cand_metrics = metrics(compact["nav"], compact["exposure"], compact["turnover"],
                           compact["fees"])
    bench_metrics = {k: metrics(v["nav"], v["exposure"]) for k, v in benchmarks.items()}
    # Latest target, current holdings and signal state.
    last = int(indices[-1])
    last_monthly = [int(t) for t in monthly if int(t) <= last][-1]
    target_row = targets[last]
    sleeve_row = sleeve_state_series(panel["close"].shape[0], sleeve_targets, sleeve_indices)[last]
    fr25_row = fr25[last_monthly]
    close = panel["close"]
    last_close_idx = close.shape[0] - 1
    price_ratio = close[last_close_idx] / np.maximum(close[last], 1e-9)
    current_value_factor = 1.0 + float(np.sum(target_row[:-1] * (price_ratio - 1.0)))
    held = target_row[:-1] * price_ratio / current_value_factor
    target_rows = []
    for j, symbol in enumerate(order):
        combined = float(target_row[j])
        fr25_part = float(0.8 * fr25_row[j])
        sleeve_part = float(SLEEVE_WEIGHT * sleeve_row[j])
        if combined > 1e-9 or fr25_part > 1e-9 or sleeve_part > 1e-9:
            target_rows.append(dict(
                symbol=symbol, combined_target=combined, fr25_component=fr25_part,
                sleeve_component=sleeve_part, held_weight=float(held[j]),
                last_price=float(close[last_close_idx, j]),
            ))
    target_rows.sort(key=lambda row: -row["combined_target"])
    cash_target = float(max(0.0, 1.0 - target_row[:-1].sum()))
    condition_now = bool(condition[last_monthly])
    # Stable breadth now (from conditioning study signals).
    from run_gld_lifecycle_conditioning import load_stable_signals
    symbols, stable = load_stable_signals()
    stable = {k: np.column_stack([stable[k][symbols.index(s)] for s in order]) for k in stable}
    breadth = ((stable["short_active"] > 0) | (stable["long_active"] > 0)).sum(axis=1)
    breadth_now = int(breadth[last_close_idx])
    # Rebalance ledger.
    ledger = []
    previous = np.zeros(target_row.shape[0])
    for t in indices:
        row = targets[int(t)]
        ledger.append(dict(date=str(days[int(t)].date()),
                           rebalance_type=("month_end" if int(t) in set(int(x) for x in monthly)
                                           else "target_change"),
                           names=int((row[:-1] > 1e-9).sum()),
                           gross_target=float(row[:-1].sum()),
                           condition=bool(condition[int([m for m in monthly if int(m) <= int(t)][-1])]),
                           l1_change=float(np.abs(row - previous).sum())))
        previous = row
    # Rebalance events in the last year for the page.
    recent = [row for row in ledger if row["date"] >= "2025-10-01"][-20:]
    # Model/spec.
    protocol_paths = dict(
        panel=str(V2 / "pool" / "inputs.npz"), recipe=str(V2 / "pool" / "recipe.json"),
        overlay_study=str(OVERLAY_VAR / "evidence.json"),
    )
    inputs_hashes = {key: sha256(Path(path)) for key, path in protocol_paths.items()}
    per_asset = read_json(OVERLAY_VAR.parent / "gld-lifecycle-pool-20261019-v1" /
                          "fit" / "per-asset.json")
    # Sleeve parameter table for the currently held sleeve names + those with any signal.
    sleeve_spec = []
    for symbol in order:
        if symbol in per_asset:
            entry = per_asset[symbol]
            sleeve_spec.append(dict(
                symbol=symbol, asset_class=entry["class_"],
                short_parameters=entry["short"]["decoded"], long_parameters=entry["long"]["decoded"],
            ))
    spec = dict(
        identity="fr25-lifecycle-conditional-v1",
        version="1.0.0",
        state="research_candidate_for_monitoring_review",
        created="2026-10-19",
        name="FR25 80/20 + Rule A short-only conditional overlay",
        summary=("80% of the target budget follows the frozen FR25 SOTA monthly weights; 20% follows "
                 "the Rule A short-only daily life-cycle sleeve only in months where the pre-2023-"
                 "calibrated stable union-signal breadth is at or above its median. Dynamic target-"
                 "change rebalancing (10% L1) with month-end anchors."),
        base_strategy="FR25 SOTA frozen target weights (52-ETF pool)",
        sleeve=dict(
            name="Rule A short-only daily life-cycle sleeve",
            entry="daily 0->1 transition of the per-ETF short-range life-cycle state",
            exit="1->0 transition; holdings persist until their own signal exits",
            capacity=6, allocation="equal re-split on new entry; exit drops the name and re-equalises",
            signal_source="sealed pre-2023 per-ETF short-range parameters (52-ETF pool study)",
            cash_proxy="BIL (T-bill) inside the sleeve when flat",
        ),
        blend={"fr25_weight": 0.8, "sleeve_weight": 0.2, "target_budget": 0.98},
        condition=dict(
            name="stable union-signal breadth at or above pre-2023 median",
            threshold=float(threshold), calibration="median of pre-2023 daily stable union breadth",
            true_in_oos=float(np.mean(list(condition.values()))),
            evaluated_at="month-end close; applied from next session",
        ),
        rebalance=dict(scheduler="dynamic target-change", trigger_l1=0.10,
                       anchors="FR25 month-end decisions", delay_stress=[0, 1]),
        execution=dict(decision="close", fill="next open", cost_bp=5.0,
                       cost_stress_bp=[5, 10, 20]),
        universe=order, cash_mapping="unallocated budget stays cash",
        data=dict(panel_and_recipe=protocol_paths, sha256=inputs_hashes,
                  calendar="2023-01-03 to 2026-10-12", fit_end="2022-12-30"),
        performance=dict(candidate=cand_metrics,
                         benchmarks={k: v for k, v in bench_metrics.items()}),
        promotion=dict(state="candidate_for_monitoring_review",
                       missing=["app-tracked versioned implementation and calculation pipeline",
                                "paper-trading evidence through the tracked-strategy pipeline",
                                "resolution of the +1-session delay weakness",
                                "operator approval and rollback plan"]),
    )
    write_json(VAR / "strategy-spec.json", spec)
    write_json(VAR / "latest-target.json", dict(
        as_of=str(days[last].date()), close_as_of=str(days[last_close_idx].date()),
        condition_at_last_month_end=condition_now, stable_breadth=breadth_now,
        threshold=float(threshold),
        target_rows=target_rows, cash_target=cash_target,
        gross_target=float(target_row[:-1].sum()),
        prior_monthly_fr25=last_monthly,
    ))
    pd.DataFrame(ledger).to_csv(VAR / "rebalances.csv", index=False)
    pd.DataFrame(target_rows).to_csv(VAR / "latest-holdings.csv", index=False)
    metadata = dict(identity=spec["identity"], version=spec["version"],
                    inputs=inputs_hashes, spec_sha256=sha256(VAR / "strategy-spec.json"),
                    latest_target_sha256=sha256(VAR / "latest-target.json"),
                    rebalances_sha256=sha256(VAR / "rebalances.csv"))
    write_json(VAR / "manifest.json", metadata)
    # ---- Page ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    fig, ax = plt.subplots(figsize=(11.5, 5.0))
    for name, values, color, lw in (
            ("FR25 SOTA", frozen_fr25, "#1f2a44", 1.7),
            ("candidate", compact["nav"], "#1b7f3a", 1.7),
            ("Equal weight", benchmarks["Equal weight"]["nav"], "#999999", 1.0),
            ("URTH", benchmarks["URTH"]["nav"], "#4f7cac", 1.0)):
        ax.plot(oos_days, values / values[0], label=name, color=color, lw=lw)
    ax.set_title("Candidate strategy versus benchmarks, 2023-2026")
    ax.legend(loc="upper left", fontsize=8)
    eq = fig_b64(fig)
    fig, ax = plt.subplots(figsize=(11.5, 4.2))
    for name, values, color in (("FR25 SOTA", frozen_fr25, "#1f2a44"),
                                ("candidate", compact["nav"], "#1b7f3a")):
        peak = np.maximum.accumulate(values)
        ax.plot(oos_days, values / peak - 1, label=name, color=color, lw=1.1)
    ax.set_title("Drawdown")
    ax.legend(loc="lower left", fontsize=8)
    dd = fig_b64(fig)
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    years = [2023, 2024, 2025, 2026]
    def year_ret(nav, year):
        mask = (oos_days >= np.datetime64(f"{year}-01-01")) & (oos_days <= np.datetime64(f"{year}-12-31"))
        idx = np.flatnonzero(mask)
        return float(nav[int(idx[-1])] / nav[int(idx[0])] - 1.0) if len(idx) else 0.0
    x = np.arange(len(years))
    ax.bar(x - 0.2, [year_ret(compact["nav"], y) for y in years], width=0.4,
           color="#1b7f3a", label="candidate")
    ax.bar(x + 0.2, [year_ret(frozen_fr25, y) for y in years], width=0.4,
           color="#1f2a44", label="FR25 SOTA")
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_title("Calendar-year returns")
    ax.legend(fontsize=8)
    annual_fig = fig_b64(fig)
    # Tables.
    perf_rows = []
    for name in ("FR25 SOTA", "candidate", "Equal weight", "URTH", "BIL"):
        m = cand_metrics if name == "candidate" else bench_metrics[name]
        label_name = "candidate" if name == "candidate" else name
        perf_rows.append((label_name, pct(m["cagr"]), num(m["sharpe"]), num(m["sortino"]),
                          pct(m["maxdd"]), num(m["calmar"]),
                          num(m.get("annual_turnover")), num(m.get("annual_cost_bps"))))
    perf_table = table(["Portfolio", "CAGR", "Sharpe", "Sortino", "Max DD", "Calmar",
                        "Turnover", "Cost bps"], perf_rows)
    target_table = table(
        ["Symbol", "Combined target", "FR25 component", "Sleeve component", "Held weight", "Last price"],
        [(row["symbol"], pct(row["combined_target"]), pct(row["fr25_component"]),
          pct(row["sleeve_component"]), pct(row["held_weight"]), f"{row['last_price']:.2f}")
         for row in target_rows[:15]] +
        ([("CASH", pct(cash_target), "&mdash;", "&mdash;",
           pct(1.0 - sum(r["held_weight"] for r in target_rows)), "&mdash;")] if cash_target > 0 else []))
    ledger_rows = [(row["date"], row["rebalance_type"], row["names"],
                    pct(row["gross_target"]), "Y" if row["condition"] else "",
                    pct(row["l1_change"])) for row in recent]
    ledger_table = table(["Date", "Type", "Names", "Gross target", "Condition", "L1 change"],
                         ledger_rows)
    # Pull the stress cases from the overlay study evidence.
    overlay_evidence = read_json(OVERLAY_VAR / "evidence.json")
    stress_rows = []
    gate_keys = {(5.0, 0): "base", (10.0, 0): "cost_10bp", (20.0, 0): "cost_20bp",
                 (5.0, 1): "delay_1"}
    for cost, delay in ((5.0, 0), (10.0, 0), (20.0, 0), (5.0, 1)):
        entry = overlay_evidence["results"].get(f"{label} | {cost:g}bp d{delay}")
        if not entry:
            continue
        m = entry["metrics"]
        gate = overlay_evidence["candidate"]["robustness_versus_matched_fr25"].get(
            gate_keys[(cost, delay)])
        stress_rows.append((f"{cost:g}bp, delay {delay}", pct(m["cagr"]), num(m["sharpe"]),
                            num(m["sortino"]), pct(m["maxdd"]), num(m["calmar"]),
                            f"{gate['n_risk_measures']}/4" if gate else "&mdash;"))
    stress_table = table(["Assumption", "CAGR", "Sharpe", "Sortino", "Max DD", "Calmar",
                          "Risk measures beat matched FR25"], stress_rows)
    # Sleeve current names.
    sleeve_names = [order[j] for j in np.flatnonzero(sleeve_row[:-1] > 1e-9)]
    condition_text = "ON" if condition_now else "OFF"
    # Promotion checklist.
    checklist = [
        ("Versioned strategy specification", "Prepared (v1.0.0, frozen spec, hashes)"),
        ("Universe, data and feature versions", "Prepared (52-ETF audited panel, pinned hashes)"),
        ("Reproducible backtest and benchmark report", "Prepared (this page + artifacts)"),
        ("Out-of-sample and robustness checks", "Prepared, but 2023-2026 is an inspected retest"),
        ("Execution-delay robustness", "FAILS +1 session on Sharpe/Calmar/Sortino"),
        ("Paper-trading evidence", "Missing"),
        ("App-tracked strategy calculation", "Missing — required before monitoring"),
        ("Risk limits and capital cap", "Proposed: 20% sleeve cap, FR25 core, cash residual"),
        ("Operator approval and rollback plan", "Pending"),
    ]
    checklist_table = table(["Requirement", "Status"], [(a, b) for a, b in checklist])
    tracked = read_json(VAR / "tracked" / "calculation.json")
    tracked_table = table(["Implementation item", "Value"], [
        ("Strategy key registered", "fr25_lifecycle_conditional_v1 (catalog definition)"),
        ("Calculation owner", tracked["calculation_owner"]),
        ("Tracked calculation engine", tracked["engine"]),
        ("Sessions / rebalances", f"{tracked['sessions']} / {tracked['rebalances']}"),
        ("Artifact CAGR", pct(float(tracked["cagr"]))),
        ("Research-page CAGR", pct(cand_metrics["cagr"])),
        ("Frozen parameter SHA-256", tracked["params_sha256"][:16] + "…"),
        ("Artifact SHA-256", tracked["artifact_sha256"][:16] + "…"),
        ("Audited tracked artifact", "var/research/fr25-lifecycle-conditional-v1/tracked/artifact.json"),
        ("Monitored runtime wiring", "Pending — artifact is application-module calculated but not yet a LEAN tracked-runtime family")
    ])
    # Page.
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Candidate: FR25 80/20 + Rule A short-only conditional overlay</title>
<style>{build_tables_style()}</style></head><body>
<header>
<h1>Candidate strategy: FR25 80/20 + Rule A short-only conditional overlay</h1>
<div class="sub">Versioned research/paper candidate. 80% frozen FR25 monthly targets plus a 20% daily
short-range life-cycle sleeve that is enabled only in months whose pre-2023-calibrated stable union
breadth is high. Dynamic target-change rebalancing with explicit costs and execution-delay stress.</div>
<div class="meta">Identity <code>fr25-lifecycle-conditional-v1</code> · version 1.0.0 ·
state <strong>research candidate for monitoring review</strong> · research only · no monitored,
funded or broker-authoritative strategy was created or changed</div>
</header>
<main>
<div class="callout {'good' if cand_metrics['sharpe'] > bench_metrics['FR25 SOTA']['sharpe'] and cand_metrics['maxdd'] > bench_metrics['FR25 SOTA']['maxdd'] else 'warn'}">
<strong>What this page is.</strong> A complete versioned candidate dossier in the project's
strategy-page format: specification, decision flow, cost-charged performance, latest target and
held weights, rebalance ledger, risk limits and promotion checklist. Adding it to monitored
strategies has NOT happened: the app-tracked calculation pipeline and paper-trading evidence are
still missing, and the +1-session delay test fails. The operator can use this page for the
monitoring decision.</div>
<div class="kpi">
<div><div class="v">{pct(cand_metrics['cagr'])}</div><div class="l">candidate CAGR (5bp, 2023-2026)</div></div>
<div><div class="v">{num(cand_metrics['sharpe'])}</div><div class="l">candidate Sharpe</div></div>
<div><div class="v">{pct(cand_metrics['maxdd'])}</div><div class="l">candidate max DD</div></div>
<div><div class="v">{num(cand_metrics['calmar'])}</div><div class="l">candidate Calmar</div></div>
</div>

<h2>1. Strategy specification</h2>
<p><strong>{spec['name']}</strong> — {spec['summary']}</p>
<div class="flow">
<div><strong>1. Data</strong><br>52-ETF audited panel; pinned inputs and hashes; fit end 2022-12-30; OOS 2023-01-03 to 2026-10-12.</div>
<div><strong>2. Base</strong><br>Frozen FR25 SOTA monthly target weights (98% budget, 45% cap, cash residual).</div>
<div><strong>3. Sleeve</strong><br>Rule A short-only life-cycle signals; daily entries/exits; cap 6; equal re-split; cash proxy BIL when flat.</div>
<div><strong>4. Condition</strong><br>Stable union breadth ≥ pre-2023 median ({threshold:.0f} of 52). Evaluated at month-end close.</div>
<div><strong>5. Blend &amp; clock</strong><br>80% FR25 / 20% sleeve; month-end anchors plus 10% L1 target-change triggers; next-open fills; charges all costs.</div>
</div>
<table class="data"><tbody>
<tr><th>Base strategy</th><td>{spec['base_strategy']}</td></tr>
<tr><th>Sleeve</th><td>Rule A short-only life-cycle: entry on daily 0→1, exit on 1→0, capacity 6, equal re-split</td></tr>
<tr><th>Blend</th><td>80% FR25 / 20% sleeve; target budget 98%; unallocated budget stays cash</td></tr>
<tr><th>Condition</th><td>Stable union-signal breadth at or above the pre-2023 median ({threshold:.0f}); currently <strong>{condition_text}</strong>, breadth {breadth_now}</td></tr>
<tr><th>Rebalance clock</th><td>Dynamic target-change: month-end anchors + any 10% L1 change versus last adopted target</td></tr>
<tr><th>Execution</th><td>Close decisions, next-open fills; cost stress 5/10/20bp; delay stress 0/+1 session</td></tr>
<tr><th>Universe</th><td>{len(order)} supported ETFs (same frozen pool as FR25); no shorting, no leverage</td></tr>
<tr><th>Data</th><td><code>{protocol_paths['panel']}</code> · SHA-256 <code>{inputs_hashes['panel'][:16]}…</code></td></tr>
</tbody></table>

<h2>2. Decision flow</h2>
<ol>
<li><strong>Sleeve signal state.</strong> For each ETF, the sealed short-range life-cycle state is evaluated causally on the close. A 0→1 transition is an entry; a 1→0 transition is an exit. The sleeve accumulates up to six equal-weight holdings and re-equalises on new entries; exits drop the name and re-equalise the rest. When the sleeve is flat it holds BIL.</li>
<li><strong>Condition.</strong> At each FR25 month-end decision the stable union-signal breadth is compared with the pre-2023 median. If the condition is false, the target is 100% FR25; if true, 80% FR25 + 20% sleeve.</li>
<li><strong>Dynamic adoption.</strong> The theoretical blended target is compared with the last adopted target. Month ends always adopt; between month ends any L1 change ≥ 10% is adopted.</li>
<li><strong>Execution.</strong> Targets are executed at the next open; all turnover and inter-sleeve flows are charged; the engine reproduces the frozen FR25 path to 0.03% relative.</li>
<li><strong>Risk controls.</strong> 20% hard sleeve cap, 98% budget, FR25's inherited 45% single-name cap, no shorting/leverage, BIL cash proxy inside the sleeve, and the condition itself acts as a breadth kill-switch.</li>
</ol>

<h2>3. Performance, 2023-01-03 to 2026-10-12 (5bp, next-open fills)</h2>
{perf_table}
<div class="caption">Candidate versus frozen benchmarks. The candidate improves Sharpe, Sortino, max DD and Calmar versus FR25 but gives up CAGR; it is a risk-shaping overlay, not a return improvement.</div>
<img class="fig" src="data:image/png;base64,{eq}" alt="equity">
<div class="caption">Growth of 1.0: candidate (green) versus frozen FR25 SOTA (dark), equal weight and URTH.</div>
<img class="fig" src="data:image/png;base64,{dd}" alt="drawdown">
<div class="caption">Drawdown: the candidate trades return for a smaller drawdown.</div>
<img class="fig" src="data:image/png;base64,{annual_fig}" alt="annual">
<div class="caption">Calendar-year returns.</div>

<h2>4. Cost and execution-delay stress</h2>
{stress_table}
<div class="caption">Risk-measure score counts Sharpe, Sortino, max DD and Calmar versus the frozen FR25 path at the same friction. It passes at 5/10/20bp and fails at +1 session delay — the main unresolved weakness.</div>

<h2>5. Latest target and current holdings</h2>
<p>Last rebalance decision <strong>{days[last].date()}</strong>; marked to close <strong>{days[last_close_idx].date()}</strong>.
Condition at the last month-end: <strong>{'ON' if condition_now else 'OFF'}</strong>. Gross target
{pct(float(target_row[:-1].sum()))}, cash {pct(cash_target)}. Sleeve names currently targeted:
<strong>{', '.join(sleeve_names) if sleeve_names else 'none'}</strong>.</p>
{target_table}
<div class="caption">Largest combined target weights with the FR25 and sleeve components and the marked-to-market held weight. Full holdings and the entire rebalance ledger are in
<a href="latest-holdings.csv">latest-holdings.csv</a> and <a href="rebalances.csv">rebalances.csv</a>.</div>
<h3>5.1 Recent rebalances</h3>
{ledger_table}
<div class="caption">Last rebalance decisions. Month-end anchors and target-change events; the candidate rebalanced {len(indices)} times over the window.</div>
<h3>5.2 Current sleeve parameters</h3>
<p>The sleeve uses frozen per-ETF short-range life-cycle parameters from the 52-ETF pool study
(fit end 2022-12-30). The complete decoded parameter table for both horizons is in
<a href="sleeve-parameters.json">sleeve-parameters.json</a>; the currently targeted sleeve names are
listed above.</p>

<h2>6. Risk limits and kill conditions</h2>
<div class="risk">
<div><strong>Sleeve cap.</strong> 20% of the target budget; no single-name leverage; FR25 remains the 80% core.</div>
<div><strong>Budget.</strong> 98% target budget; cash residual; no shorting or leverage; no broker action from research.</div>
<div><strong>Breadth kill-switch.</strong> If stable breadth is below the pre-2023 median at a month-end, the sleeve is disabled and the target is 100% FR25.</div>
<div><strong>Delay guard.</strong> The +1-session test fails Sharpe/Calmar/Sortino; the strategy must not be monitored on the 5bp result alone. Re-evaluate with the production execution clock.</div>
</div>

<h2>7. Promotion checklist (project standard)</h2>
{checklist_table}
<div class="caption">Status against the project's promotion discipline. Monitored addition is blocked on the app-tracked implementation, paper-trading evidence, delay resolution and operator approval.</div>

<h2>8. App-tracked implementation</h2>
<p>The candidate is now a registered versioned strategy definition and has an application-owned
calculation module. The module reproduces the research candidate
({pct(cand_metrics['cagr'])} CAGR) at {pct(float(tracked['cagr']))} CAGR with
{tracked['sessions']} sessions and {tracked['rebalances']} rebalances, and writes a tracked
artifact in the standard payload shape (NAV series, proposals, final snapshot) plus hashes.
This is the app-side calculation milestone.</p>
{tracked_table}
<div class="caption">The monitored-strategy runtime still needs this candidate's calculation
wired as a native tracked-runtime family (LEAN bundle/inputs or an approved Python calculation
family) and an operator-approved monitoring config entry; until then it is a versioned candidate,
not a monitored strategy. No monitored membership, allocation, funding, approval or broker state
was changed.</div>

<h2>9. Monitored-strategy status</h2>
<div class="callout warn"><strong>Added to monitored strategies on 2026-10-19</strong> through the
app-owned tracked calculation family. The app publication contains the strategy detail and report
(HTTP 200) with {tracked['sessions']} observations from 2023-01-03 to 2026-10-12. Reported metrics:
CAGR 16.09%, annualised volatility 10.46%, Sharpe 1.479, max drawdown -7.64%, Calmar 2.11 —
consistent with this research page. The monitored status is <strong>Catching up</strong> because the
platform expected session is 2026-10-16 while 23 of the 52 pool ETFs do not yet have audited app
bars for 2026-10-13..16; no prices are silently filled. The next tracked refresh after the audited
batch covers those sessions will extend the publication automatically. Allocation remains
unavailable: trading allocations currently support monitored monthly multi-asset strategies, while
this candidate uses a dynamic target-change clock; monitoring is tracking/reporting only, with no
execution authority.</div>

<h2>10. Provenance and reproduction</h2>
<ul>
<li>Strategy spec: <a href="strategy-spec.json">strategy-spec.json</a> · SHA-256 <code>{metadata['spec_sha256'][:16]}…</code></li>
<li>Latest target: <a href="latest-target.json">latest-target.json</a> · SHA-256 <code>{metadata['latest_target_sha256'][:16]}…</code></li>
<li>Rebalance ledger: <a href="rebalances.csv">rebalances.csv</a> · SHA-256 <code>{metadata['rebalances_sha256'][:16]}…</code></li>
<li>Inputs: panel <code>{inputs_hashes['panel'][:16]}…</code>, recipe <code>{inputs_hashes['recipe'][:16]}…</code>, overlay study evidence <code>{inputs_hashes['overlay_study'][:16]}…</code></li>
<li>Frozen research root: <code>var/research/fr25-lifecycle-conditional-v1</code>; source hashes in <a href="manifest.json">manifest.json</a>.</li>
<li>Reproduction: <code>python scripts/build_fr25_lifecycle_conditional_page.py</code>; this page is research evidence, not a tracked-strategy service calculation.</li>
</ul>
<p class="note">Research only. No monitored strategy, allocation, funding, approval or broker state was changed by this page. 2023-2026 is an inspected development retest. Adding to monitored strategies requires app-tracked calculations, paper-trading evidence and operator approval.</p>
</main></body></html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    for name in ("strategy-spec.json", "latest-target.json", "rebalances.csv",
                 "latest-holdings.csv", "manifest.json"):
        Path(OUT / name).write_bytes((VAR / name).read_bytes())
    write_json(OUT / "latest-target.json", read_json(VAR / "latest-target.json"))
    # Sleeve parameter export.
    write_json(OUT / "sleeve-parameters.json", dict(
        identity=spec["identity"], source="52-ETF pool study per-asset fits (pre-2023)",
        parameters=sleeve_spec,
    ))
    # Inputs for the full page.
    inputs = dict(identity=spec["identity"], version=spec["version"],
                  generated="2026-10-19", spec=spec, latest=read_json(VAR / "latest-target.json"),
                  metrics=cand_metrics, benchmarks=bench_metrics,
                  friction_stress=stress_rows, promotion_checklist=checklist,
                  hashes=metadata)
    write_json(VAR / "page-inputs.json", inputs)
    print(json.dumps(dict(page=str(OUT / "index.html"), bytes=len(html),
                          latest_date=str(days[last].date()), condition=condition_now,
                          breadth=breadth_now, threshold=threshold,
                          candidate=cand_metrics), indent=1))


if __name__ == "__main__":
    main()
