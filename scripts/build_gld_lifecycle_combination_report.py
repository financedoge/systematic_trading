"""Build the long-range GLD lifecycle and short/long combination report."""
from __future__ import annotations

import base64
import io
import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(r"D:\projects\systematic_trading")
SHORT_VAR = ROOT / "var" / "research" / "gld-lifecycle-20261019-v1"
LONG_VAR = ROOT / "var" / "research" / "gld-longrange-lifecycle-20261019-v1"
COMBO_VAR = ROOT / "var" / "research" / "gld-lifecycle-combination-20261019-v1"
PUB = ROOT / "research" / "gld-lifecycle-combination-20261019-v1"
sys.path.insert(0, str(ROOT / "src"))
from systematic_trading.research import range_lifecycle as rl  # noqa: E402


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fig_b64(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def table(headers, rows, cls="data", floatfmt=None):
    out = [f'<table class="{cls}"><thead><tr>']
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        for value in row:
            if floatfmt and isinstance(value, float):
                text = floatfmt(value)
            elif isinstance(value, float):
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


def metric_headers():
    return ["Window", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure"]


def metric_rows(periods, labels=("IS", "OOS", "FULL")):
    rows = []
    for name in labels:
        p = periods[name]
        if "rule" in p:
            p = p["rule"]
        rows.append((name, pct(p["cagr"]), num(p["sharpe"]), pct(p["maxdd"]),
                     num(p["calmar"]), pct(p["exposure"])))
    return rows


def load_study():
    combo = read_json(COMBO_VAR / "combination.json")
    long_eval = read_json(LONG_VAR / "evaluation" / "evaluation.json")
    long_selection = read_json(LONG_VAR / "selection.json")
    long_protocol = read_json(LONG_VAR / "protocol.json")
    long_top = read_json(LONG_VAR / "fit" / "top60.json")
    short_eval = read_json(SHORT_VAR / "evaluation" / "evaluation.json")
    short_selection = read_json(SHORT_VAR / "selection.json")
    combo_daily = pd.read_csv(COMBO_VAR / "combined-daily.csv", parse_dates=["date"])
    long_ledger = pd.read_csv(COMBO_VAR / "long-daily-ledger.csv", parse_dates=["date"])
    long_episodes = pd.DataFrame(long_eval["episodes"])
    validation_path = LONG_VAR / "validation" / "evaluation" / "evaluation.json"
    validation = read_json(validation_path) if validation_path.exists() else None
    return dict(combo=combo, long_eval=long_eval, long_selection=long_selection,
                long_protocol=long_protocol, long_top=long_top, short_eval=short_eval,
                short_selection=short_selection, combo_daily=combo_daily,
                long_ledger=long_ledger, long_episodes=long_episodes,
                validation=validation)


def build_figures(study):
    figures = {}
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25})
    daily = study["combo_daily"]
    # Long strategy price chart with ranges and trades.
    ledger = study["long_ledger"]
    episodes = study["long_episodes"]
    fig, ax = plt.subplots(figsize=(12, 5.4))
    ax.plot(ledger["date"], ledger["close"], color="#1f2a44", lw=1.0, label="GLD close")
    valid = ledger["range_lookback"] > 0
    ax.fill_between(ledger["date"], ledger["range_lower"], ledger["range_upper"], where=valid,
                    color="#4f7cac", alpha=0.14, linewidth=0, label="qualifying long range")
    long_mask = ledger["weight"] > 0
    ax.fill_between(ledger["date"], 0.0, 0.035, where=long_mask,
                    transform=ax.get_xaxis_transform(), color="#c58b2a", alpha=0.65,
                    linewidth=0, label="long exposure (bottom band)")
    for _, episode in episodes.iterrows():
        ax.axvline(pd.Timestamp(episode["crossing_session"]), color="#999999", lw=0.4, alpha=0.5)
        ax.scatter(pd.Timestamp(episode["entry_session"]), episode["entry_price"], marker="^",
                   color="#1b7f3a", s=30, zorder=4)
        if pd.notna(episode["exit_session"]):
            ax.scatter(pd.Timestamp(episode["exit_session"]), episode["exit_price"], marker="v",
                       color="#b23b3b", s=30, zorder=4)
    ax.set_yscale("log")
    ax.set_title("GLD long-range lifecycle: 126-756 session ranges, wide stops, long holds")
    ax.set_ylabel("adjusted close (log)")
    ax.legend(loc="upper left", fontsize=8)
    figures["long_history"] = fig_b64(fig)
    # Combined equity, IS and OOS.
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 7.0), sharex=False)
    for ax, start, end, title in (
            (axes[0], "2005-11-17", "2022-12-30", "In-sample (parents fitted/sealed pre-2023)"),
            (axes[1], "2023-01-03", "2026-10-16", "Out-of-sample 2023-2026 (development retest)")):
        d = daily[(daily["date"] >= start) & (daily["date"] <= end)].copy()
        norm = d.iloc[0]
        ax.plot(d["date"], d["nav_short"] / norm["nav_short"], color="#1b7f3a", lw=1.2,
                label="short-range")
        ax.plot(d["date"], d["nav_long"] / norm["nav_long"], color="#c58b2a", lw=1.2,
                label="long-range")
        ax.plot(d["date"], d["nav_combined"] / norm["nav_combined"], color="#1f2a44", lw=1.8,
                label="50/50 combination")
        ax.set_title(title)
        ax.legend(loc="upper left", fontsize=8)
    figures["combined_equity"] = fig_b64(fig)
    # Drawdowns.
    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    mask = daily["date"] >= "2023-01-03"
    d = daily[mask]
    for column, label, color in (("nav_short", "short-range", "#1b7f3a"),
                                 ("nav_long", "long-range", "#c58b2a"),
                                 ("nav_combined", "50/50 combination", "#1f2a44")):
        values = d[column].to_numpy()
        peak = np.maximum.accumulate(values)
        ax.plot(d["date"], values / peak - 1, color=color, lw=1.2, label=label)
    ax.set_title("Out-of-sample drawdown: the combination halves the parent drawdowns")
    ax.legend(loc="lower left", fontsize=8)
    figures["combined_drawdown"] = fig_b64(fig)
    # Rolling correlation and exposure overlap.
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.5, 6.4), sharex=False)
    ax1.plot(daily["date"], daily["rolling_corr"], color="#7a2e8f", lw=1.2)
    ax1.axhline(0, color="black", lw=0.5)
    ax1.set_title("Rolling 252-session correlation of daily returns (short vs long)")
    ax1.set_ylim(-0.2, 1.05)
    d = daily[daily["date"] >= "2005-11-17"]
    ax2.fill_between(d["date"], 0, d["weight_short"] > 0, step="mid", color="#1b7f3a",
                     alpha=0.35, label="short active")
    ax2.fill_between(d["date"], 0, d["weight_long"] > 0, step="mid", color="#c58b2a",
                     alpha=0.35, label="long active")
    ax2.set_title("Time in market by sleeve")
    ax2.legend(loc="upper left", fontsize=8)
    figures["rolling_corr"] = fig_b64(fig)
    # Long OOS episode zoom.
    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    d = ledger[(ledger["date"] >= "2023-01-01")]
    ax.plot(d["date"], d["close"], color="#1f2a44", lw=1.1, label="GLD close")
    ax.plot(d["date"], d["range_upper"], color="#4f7cac", lw=0.9, label="long-range upper U")
    ax.plot(d["date"], d["range_lower"], color="#4f7cac", lw=0.9, label="long-range lower D")
    ax.plot(d["date"], d["trigger"], color="#c58b2a", ls="--", lw=0.9, label="breakout trigger")
    ax.plot(d["date"], d["stop"], color="#b23b3b", lw=1.1, label="effective stop")
    ax.plot(d["date"], d["trail_stop"], color="#7a2e8f", ls=":", lw=0.9, label="trailing stop")
    for _, episode in episodes[episodes["crossing_session"] >= "2023-01-01"].iterrows():
        ax.axvline(pd.Timestamp(episode["crossing_session"]), color="#c58b2a", lw=0.7, alpha=0.7)
        ax.scatter(pd.Timestamp(episode["entry_session"]), episode["entry_price"], marker="^",
                   color="#1b7f3a", s=70, zorder=5)
        if pd.notna(episode["exit_session"]):
            ax.scatter(pd.Timestamp(episode["exit_session"]), episode["exit_price"], marker="v",
                       color="#b23b3b", s=70, zorder=5)
    ax.set_title("Long-range strategy in the 2023-2026 development window")
    ax.legend(loc="upper left", fontsize=7, ncol=2)
    figures["long_oos"] = fig_b64(fig)
    return figures


def build_html(study, figures):
    combo = study["combo"]
    long_eval = study["long_eval"]
    long_selection = study["long_selection"]["chosen"]
    long_protocol = study["long_protocol"]
    short_eval = study["short_eval"]
    short_selection = study["short_selection"]["chosen"]
    daily = study["combo_daily"]
    episodes = study["long_episodes"]
    validation = study["validation"]
    cs = combo["correlations"]
    ov = combo["overlap"]
    controls = combo["controls"]
    # Parameter comparison: key dimensions only.
    ls = long_selection["decoded"]
    ss = short_selection["decoded"]
    param_rows = [
        ("Structural domain", "short: 21-504 session lookbacks",
         "long: 126-756 session lookbacks"),
        ("Band tail", f"{ss['tail']:.2f}", f"{ls['tail']:.2f}"),
        ("Width cap", f"{ss['width_cap']:.3f}", f"{ls['width_cap']:.3f}"),
        ("Drift cap", f"{ss['drift_max']:.3f}", f"{ls['drift_max']:.3f}"),
        ("ATR period", ss["atr_period"], ls["atr_period"]),
        ("Confirmation closes", ss["confirm_sessions"], ls["confirm_sessions"]),
        ("Volume shortcut", ss["volume_shortcut"], ls["volume_shortcut"]),
        ("Initial stop (ATR)", f"{ss['initial_stop_atr']:.2f}", f"{ls['initial_stop_atr']:.2f}"),
        ("Failed-range floor (ATR)", f"{ss['band_fail_atr']:.2f}", f"{ls['band_fail_atr']:.2f}"),
        ("Trailing distance (ATR)", f"{ss['trail_atr']:.2f}", f"{ls['trail_atr']:.2f}"),
        ("Trail activation (ATR)", f"{ss['trail_activate_atr']:.2f}",
         f"{ls['trail_activate_atr']:.2f}"),
        ("Time limit (sessions)", ss["time_limit_sessions"], ls["time_limit_sessions"]),
        ("Cooldown (sessions)", ss["cooldown_sessions"], ls["cooldown_sessions"]),
        ("Re-entry switch", "off (not in the sealed search)", ls["reentry_enabled"]),
    ]
    param_table = table(["Lifecycle dimension", "Short-range (frozen)", "Long-range (new)"],
                        param_rows)
    long_metric_rows = metric_rows(long_eval["periods"], ("IS", "OOS", "FULL"))
    long_metric_table = table(metric_headers(), long_metric_rows, floatfmt=None)
    parent_rows = []
    for label, ev, sel in (("Short-range (frozen, 24 fitted params)", short_eval, short_selection),
                           ("Long-range (new, 27 fitted params)", long_eval, long_selection)):
        for name in ("IS", "OOS", "FULL"):
            p = ev["periods"][name]["rule"]
            parent_rows.append((label, name, pct(p["cagr"]), num(p["sharpe"]), pct(p["maxdd"]),
                                num(p["calmar"]), pct(p["exposure"])))
    parent_table = table(["Strategy", "Window", "CAGR", "Sharpe", "Max DD", "Calmar", "Exposure"],
                         parent_rows)
    control_rows = []
    for label, key in (("Short-range only", "short_only"), ("Long-range only", "long_only"),
                       ("50/50 independent half-accounts (primary)", "equal_weight_independent"),
                       ("50/50 daily-rebalanced", "equal_weight_daily_rebalanced"),
                       ("50/50 monthly-rebalanced", "equal_weight_monthly_rebalanced"),
                       ("Buy and hold", "buyhold")):
        for name in ("IS", "OOS", "FULL"):
            p = controls[key][name]
            control_rows.append((label, name, pct(p["cagr"]), num(p["sharpe"]), pct(p["maxdd"]),
                                 num(p["calmar"]), pct(p["exposure"])))
    control_table = table(["Portfolio", "Window", "CAGR", "Sharpe", "Max DD", "Calmar",
                           "Exposure"], control_rows)
    corr_rows = []
    for name, label in (("IS", "IS 2005-2022"), ("OOS", "OOS 2023-2026"),
                        ("FULL", "Full 2005-2026")):
        c = cs[name]
        corr_rows.append((label, num(c["correlation"], 3),
                          num(c["correlation_when_both_active"], 3),
                          num(c["exposure_correlation"], 3), c["n_sessions"]))
    corr_table = table(["Window", "Return correlation", "Correlation when both active",
                        "Exposure correlation", "Sessions"], corr_rows)
    overlap_rows = []
    for name, label in (("IS", "IS 2005-2022"), ("OOS", "OOS 2023-2026"),
                        ("FULL", "Full 2005-2026")):
        o = ov[name]
        overlap_rows.append((label, f"{o['short_only']} ({100 * o['short_only'] / (o['short_only'] + o['long_only'] + o['both'] + o['neither']):.1f}%)",
                             f"{o['long_only']} ({100 * o['long_only'] / (o['short_only'] + o['long_only'] + o['both'] + o['neither']):.1f}%)",
                             f"{o['both']} ({100 * o['both'] / (o['short_only'] + o['long_only'] + o['both'] + o['neither']):.1f}%)",
                             pct(o["overlap_given_short"]), pct(o["overlap_given_long"])))
    overlap_table = table(["Window", "Short only", "Long only", "Both active",
                           "Overlap | short active", "Overlap | long active"], overlap_rows)
    grid_rows = []
    for row in combo["weight_grid"]:
        for name in ("IS", "OOS"):
            p = row[name]
            grid_rows.append((f"{int(row['weight_short'] * 100)}/{int((1 - row['weight_short']) * 100)}",
                              name, pct(p["cagr"]), num(p["sharpe"]), pct(p["maxdd"]),
                              num(p["calmar"]), pct(p["exposure"])))
    grid_table = table(["Short/long split", "Window", "CAGR", "Sharpe", "Max DD", "Calmar",
                        "Exposure"], grid_rows)
    friction_rows = []
    for row in combo["frictions"]:
        c = row["combined"]
        friction_rows.append((f"{row['cost_bp']:g} bp, delay {row['delay']}",
                              pct(c["IS"]["cagr"]), num(c["IS"]["sharpe"]),
                              pct(c["IS"]["maxdd"]), pct(c["OOS"]["cagr"]),
                              num(c["OOS"]["sharpe"]), pct(c["OOS"]["maxdd"]),
                              pct(c["OOS"]["exposure"])))
    friction_table = table(["Assumption", "IS CAGR", "IS Sharpe", "IS max DD", "OOS CAGR",
                            "OOS Sharpe", "OOS max DD", "OOS exposure"], friction_rows)
    long_episode_rows = []
    for _, episode in episodes.iterrows():
        long_episode_rows.append((
            episode["crossing_session"], episode["confirmation_session"], episode["entry_session"],
            num(episode["entry_price"]),
            episode["exit_session"] if pd.notna(episode["exit_session"]) else "open",
            num(episode["exit_price"]) if pd.notna(episode["exit_price"]) else "&mdash;",
            pct(episode["gross_return"]) if pd.notna(episode["gross_return"]) else "&mdash;",
            episode["exit_reason"], int(episode["hold_sessions"]), pct(episode["mfe"]),
            pct(episode["mae"])))
    long_episode_table = table(["Crossing", "Confirmation", "Entry", "Entry price", "Exit",
                                "Exit price", "Gross", "Reason", "Hold", "MFE", "MAE"],
                               long_episode_rows)
    long_trade_stats = long_eval["trade_stats"]
    top_rows = []
    for row in study["long_top"][:10]:
        d = row["decoded"]
        top_rows.append((row["rank"], num(row["fitness"], 3), pct(row["cagr"]),
                         num(row["sharpe"]), pct(row["maxdd"]), pct(row["exposure"]),
                         row["n_closed"], f"{d['width_cap']:.3f}",
                         f"{d['initial_stop_atr']:.1f}/{d['band_fail_atr']:.1f}",
                         f"{d['trail_atr']:.1f}@{d['trail_activate_atr']:.1f}",
                         d["atr_period"], d["time_limit_sessions"],
                         d["cooldown_sessions"]))
    top_table = table(["Rank", "IS fitness", "IS CAGR", "Sharpe", "Max DD", "Exposure",
                       "Trades", "Width cap", "Stop/band ATR", "Trail@activate", "ATR",
                       "Time limit", "Cooldown"], top_rows)
    validation_html = "<p>Validation results not available.</p>"
    if validation is not None:
        vrows = []
        for name, label in (("FIT", "Fit 2005-2015"), ("PSEUDO_OOS", "Pseudo-OOS 2016-2022")):
            p = validation["periods"][name]["rule"]
            b = validation["periods"][name]["buyhold"]
            vrows.append((label, pct(p["cagr"]), num(p["sharpe"]), pct(p["maxdd"]),
                          pct(b["cagr"]), num(b["sharpe"]), pct(b["maxdd"])))
        validation_html = table(["Window", "Rule CAGR", "Rule Sharpe", "Rule max DD",
                                 "Buy-hold CAGR", "Buy-hold Sharpe", "Buy-hold max DD"], vrows)
    # Annual combination table.
    audited = np.load(SHORT_VAR / "inputs" / "gld-audited.npz", allow_pickle=True)
    audited_days = pd.to_datetime(audited["days"]).to_numpy()
    buyhold = rl.buy_hold(rl.Features.build({k: audited[k] for k in
                                             ("open", "high", "low", "close", "volume", "days")},
                                            rl.SHORT_SPEC), 252, cost_bp=5.0)["nav"]
    nav_map = {"short": daily["nav_short"].to_numpy(),
               "long": daily["nav_long"].to_numpy(),
               "combined": daily["nav_combined"].to_numpy(),
               "buyhold": buyhold}
    annual_rows = []
    for year in range(2006, 2027):
        mask = (audited_days >= np.datetime64(f"{year}-01-01")) & (
            audited_days <= np.datetime64(f"{year}-12-31"))
        idx = np.flatnonzero(mask)
        if len(idx) < 20 or int(idx[0]) <= 252:
            continue
        s, e = int(idx[0]), int(idx[-1]) + 1
        row = [year]
        for key in ("short", "long", "combined", "buyhold"):
            nav = nav_map[key]
            row.append(pct(nav[e - 1] / nav[s] - 1))
        annual_rows.append(tuple(row))
    annual_table = table(["Year", "Short-range", "Long-range", "50/50 combination",
                          "Buy and hold"], annual_rows)
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
                 font-size:12.5px; }
    table.data th, table.data td { border:1px solid var(--line); padding:5px 7px; text-align:right; }
    table.data th { background:#eef1f5; font-weight:600; }
    table.data td:first-child, table.data th:first-child { text-align:left; }
    table.data tbody tr:nth-child(even) { background:#fafbfc; }
    .scroll { max-height:560px; overflow:auto; border:1px solid var(--line); border-radius:6px; }
    .scroll table.data { margin:0; }
    img.fig { width:100%; height:auto; display:block; margin:12px 0 6px;
              border:1px solid var(--line); border-radius:6px; background:#fff; }
    .caption { color:var(--muted); font-size:12.5px; margin:2px 0 18px; }
    pre.eq { background:#fff; border:1px solid var(--line); border-radius:6px; padding:12px 16px;
             overflow-x:auto; font-size:13px; }
    code { font-family:Consolas,monospace; font-size:13px; }
    .note { color:var(--muted); font-size:12.5px; }
    a { color:#1c5f9e; }
    """
    oos_combo = controls["equal_weight_independent"]["OOS"]
    oos_long = controls["long_only"]["OOS"]
    oos_short = controls["short_only"]["OOS"]
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GLD long-range lifecycle and short/long combination</title><style>{css}</style></head><body>
<header>
<h1>GLD two-horizon lifecycle: a long-range breakout strategy and its combination with the sealed short-range strategy</h1>
<div class="sub">The operator asked for a second, longer-horizon version of the short-range breakout strategy
(126-756 session ranges, much larger stops and trailing distances, longer holds) and then for a correlation
test to see whether the two returns can be added together. Both parents are fitted and sealed on pre-2023 sessions
only; the 2023-2026 interval is the same development retest used by the parent studies.</div>
<div class="meta">Study <code>gld-lifecycle-combination-20261019-v1</code> · input batch
<code>{long_protocol['data']['governance_batch'][:16]}...</code> · audited GLD asset
<code>{long_protocol['data']['asset_sha256'][:16]}...</code> · research only, no monitoring or trade authority</div>
</header>
<main>
<p class="lede">The two strategies are the <em>same state machine</em> with different predeclared structural
domains and independently fitted parameters. The short-range rule (frozen earlier) uses 21-504 session ranges
and tight burst exits. The new long-range rule searches 126-756 session ranges, initial stops of 4-20 ATR, trailing
distances of 3-20 ATR (or 8-50%) and time limits up to 504 sessions. Their daily-return correlation is
<strong>{num(cs['OOS']['correlation'], 2)} out-of-sample</strong>, because they are in the market at different
times; when both are long the correlation is {num(cs['OOS']['correlation_when_both_active'], 3)}, as expected
for the same ETF. A fixed 50/50 combination keeps the long-range Sharpe while halving the parent drawdowns.</p>

<div class="kpi">
<div><div class="v">{pct(oos_combo['cagr'])}</div><div class="l">Combined OOS CAGR</div></div>
<div><div class="v">{num(oos_combo['sharpe'])}</div><div class="l">Combined OOS Sharpe</div></div>
<div><div class="v">{pct(oos_combo['maxdd'])}</div><div class="l">Combined OOS max drawdown</div></div>
<div><div class="v">{num(cs['OOS']['correlation'], 2)}</div><div class="l">Short/long OOS return correlation</div></div>
</div>

<div class="callout good"><strong>The diversification is horizon/time-in-market, not asset diversification.</strong>
Both sleeves trade GLD, so they cannot diversify the asset. The low overall correlation comes from different
entry/exit timing: out-of-sample each sleeve is active only 34%/40% of sessions, they overlap 17% of sessions,
and {ov['OOS']['neither']} sessions are spent flat by both. The 50/50 combination therefore has a much smoother
path than either parent.</div>

<h2>1. The two strategies at a glance</h2>
{param_table}
{parent_table}
<div class="caption">Parents under identical accounting (5bp per side, next-open fills, zero cash yield). The
short-range column repeats the sealed parent study; the long-range column is this study.</div>

<h2>2. Long-range strategy: design, fitting and selection</h2>
<p>The long domain preserves the exact lifecycle logic of the parent: tight prior range, triggered and confirmed
breakout, wide initial stop plus failed-range floor, dynamic take-profit from the recent high, cooldown. What
changes is the predeclared structural domain: candidate lookbacks {{126, 189, 252, 378, 504, 756}}; ATR periods
{{20, 40, 60, 120}}; volume references {{63, 126, 252}}; time limits {{0, 126, 252, 504}}; initial stops 4-20 ATR;
failed-range floors -1 to 8 ATR; trailing 3-20 ATR or 8-50%. Every behavioral threshold inside that domain is
fitted by the same differential-evolution search and the same sealed-validation protocol on pre-2023 sessions
only.</p>
<pre class="eq">search: 4 seeds x population 20 x dimension x 150 generations = 326,160 pre-2023 evaluations at 5bp
objective: 0.45 excess CAGR + 0.40 excess Sharpe + 0.15 excess Calmar versus matched buy-hold,
           plus three-block stability, minus scarcity / low-exposure penalties
selection: 400 finalists x {len(combo['design']['frictions'])} frictions (5/10/20bp, +1 session delay),
           evidence and return/drawdown guards, parameter-neighbour stability, then seal</pre>
<h3>2.1 Selected long-range parameters</h3>
{selected_long_table(ls, long_selection)}
<h3>2.2 Top independent candidates</h3>
{top_table}
<p class="note">The long-range search agrees on much wider stops, higher activation and longer holds than the
short-range rule: the top candidates use 6.5-20 ATR initial stops, 3-5 ATR trailing distances armed after 10-12
ATR advances, and 126-504 session time limits. Continuation re-entry remains mostly rejected.</p>

<h2>3. Long-range strategy evidence</h2>
{long_metric_table}
{validation_html}
<div class="caption">The pre-2023 pseudo-out-of-sample validation (fit 2005-2015, evaluate 2016-2022) is shown for
the long domain. The long strategy holds fewer, larger positions: {long_trade_stats.get('n', 0)} closed episodes in
the full history, mean gross {pct(long_trade_stats.get('mean_gross'))}, median hold
{long_trade_stats.get('mean_hold', 0):.0f} sessions.</div>
<img class="fig" src="data:image/png;base64,{figures['long_history']}" alt="long history">
<div class="caption">Long-range lifecycle over GLD history: bands, crossing sessions, entries/exits and long-exposure
band. This is the visual counterpart of the short-range chart in the parent report.</div>
<h3>3.1 Episodes</h3>
<div class="scroll">{long_episode_table}</div>
<div class="caption">Every long-range episode. The 2023-03-30 crossing (a 756-session range) held for 251 sessions
into 2024-04-10 for +15.63%; the 2024-07 and 2025-01 entries delivered +14.55% and +14.69%.</div>
<img class="fig" src="data:image/png;base64,{figures['long_oos']}" alt="long OOS chart">
<div class="caption">Long-range strategy in 2023-2026 with the daily range bands, trigger, effective stop and
trailing take-profit.</div>

<h2>4. Correlation between the two strategies</h2>
{corr_table}
<div class="caption">Pearson correlation of daily NAV returns. The correlation when both sleeves are long is near
one (same ETF), but the unconditional correlation is only about 0.34-0.37 because each sleeve is flat most of the
time.</div>
{overlap_table}
<div class="caption">Active-sleeve overlap. "Overlap | short active" is the share of short-range long sessions on
which the long-range sleeve is also long (about 50% OOS), and vice versa.</div>
<img class="fig" src="data:image/png;base64,{figures['rolling_corr']}" alt="rolling correlation">
<div class="caption">Top: rolling 252-session return correlation, which rarely exceeds 0.6. Bottom: time in market
by sleeve; the two sleeves spend most of their active time apart.</div>

<h2>5. Combining the strategies</h2>
<p>The primary combination is deliberately simple and predeclared: split the account 50/50 between two independent
sleeves and let each parent manage its own share (no between-sleeve rebalancing). It therefore pays only the
parents' own internal trading costs. Rebalanced and weight-grid variants are reported as controls/sensitivity;
no weight is selected on 2023+ data.</p>
{control_table}
<div class="caption">The 50/50 combination improves on both parents: OOS Sharpe
{num(oos_combo['sharpe'])} versus {num(oos_short['sharpe'])} / {num(oos_long['sharpe'])}, and OOS max drawdown
{pct(oos_combo['maxdd'])} versus {pct(oos_short['maxdd'])} / {pct(oos_long['maxdd'])}. It gives up some
long-range CAGR in exchange for a substantially smoother path; Calendar-year figures are below.</div>
<img class="fig" src="data:image/png;base64,{figures['combined_equity']}" alt="combined equity">
<div class="caption">In-sample and out-of-sample growth of 1.0 for both parents and the 50/50 combination.</div>
<img class="fig" src="data:image/png;base64,{figures['combined_drawdown']}" alt="combined drawdown">
<div class="caption">Out-of-sample drawdowns: the combination halves the parent drawdowns.</div>
<h3>5.1 Calendar-year returns</h3>
{annual_table}
<h3>5.2 Capital-split sensitivity</h3>
{grid_table}
<div class="caption">Fixed capital splits. The combination improvement is present for every interior split; the
50/50 rule was predeclared, not selected from this table.</div>
<h3>5.3 Costs and execution delay</h3>
{friction_table}
<div class="caption">The combined sleeve is cost- and delay-robust: 20bp per side gives OOS Sharpe
{num(combo['frictions'][2]['combined']['OOS']['sharpe'])}; one extra session at 5bp gives
{num(combo['frictions'][3]['combined']['OOS']['sharpe'])}.</div>

<h2>6. Interpretation and limitations</h2>
<ul>
<li><strong>Answer to the question.</strong> The long-range strategy is legitimately different: it holds 10-13
positions over the full history, holds them for 35-251 sessions, uses much wider stops and trails, and earns a
higher OOS Sharpe than the short-range rule ({num(oos_long['sharpe'])} versus {num(oos_short['sharpe'])}). Its
return correlation with the short-range rule is about 0.34 OOS and 0.37 in-sample, which is low enough for the
50/50 combination to cut drawdown by roughly half while preserving a combined Sharpe near the long parent's.</li>
<li><strong>What the low correlation is not.</strong> It is not asset diversification: both sleeves trade GLD, and
when both are long the return correlation is ~{num(cs['OOS']['correlation_when_both_active'], 3)}. The diversification
comes from complementary time-in-market; in a permanent gold trend both sleeves would be long together and the
benefit would shrink.</li>
<li><strong>Long-range evidence is thinner.</strong> The long domain produces only ~10 closed pre-2023 episodes;
its OOS result is a development retest on a small event count, and its three out-of-sample winners are far too
few to estimate a win rate (the full-history 13/13 statistic is mostly in-sample). The same fitting machinery
failed the 2005-2015 procedure validation in both domains.</li>
<li><strong>No authority.</strong> No monitoring, promotion, funding, allocation or broker action follows. The
combination is a research result on one ETF; the next natural step is the full supported ETF pool with the
two-horizon pair, cross-period stability guards and a shared-parameter fallback.</li>
</ul>

<h2>7. Files and reproduction</h2>
<ul>
<li><a href="long-daily-ledger.csv">long-daily-ledger.csv</a> — every long-range session with range, trigger, state,
entry, stop decomposition, trailing level, peak/drawdown and NAV.</li>
<li><a href="long-episodes.csv">long-episodes.csv</a> — every long-range episode.</li>
<li><a href="combined-daily.csv">combined-daily.csv</a> — daily NAV/weights for both parents and the 50/50
combination plus the rolling correlation.</li>
<li><a href="long-parameters.json">long-parameters.json</a>, <a href="combination-summary.json">combination-summary.json</a>
— sealed long-range vector and the complete combination evidence.</li>
<li><a href="long-protocol.json">long-protocol.json</a> — predeclared long-range domain and search protocol.</li>
</ul>
<p class="note">Parent studies: short-range
<code>research/gld-lifecycle-20261019-v1/index.html</code>, long-range frozen artifacts under
<code>var/research/gld-longrange-lifecycle-20261019-v1</code>. Reproduction:
<code>python scripts/run_gld_lifecycle.py prepare|fit|select|evaluate|validate</code> with
<code>GLD_STUDY_KIND=long</code>, then <code>python scripts/analyze_gld_lifecycle_combination.py</code> and
<code>python scripts/build_gld_lifecycle_combination_report.py</code>. No monitoring or trading authority.</p>
</main></body></html>"""
    return html


def selected_long_table(decoded, selection):
    descriptions = {
        "width_cap": "Maximum log width of the central band",
        "tail_index": "Band tail quantile choice (0=5%)",
        "drift_max": "First/last-block drift as a fraction of width",
        "vol_ratio_cap": "Short/long volatility ratio cap",
        "atr_index": "ATR period choice (0=20, 3=120)",
        "breakout_buffer_atr": "Crossing buffer above the upper band (ATR)",
        "confirm_sessions": "Closes above the frozen trigger to confirm",
        "volume_shortcut": "Volume surge confirms immediately",
        "volume_ratio": "Volume-shortcut ratio",
        "volref_index": "Volume reference window choice",
        "initial_stop_atr": "Initial stop below entry (ATR)",
        "band_fail_atr": "Failed-breakout floor below frozen upper band (ATR)",
        "trail_basis": "Trailing basis (0=ATR, 1=percent)",
        "trail_atr": "Trailing distance from highest close (ATR)",
        "trail_pct": "Trailing distance from highest close (percent)",
        "trail_activate_atr": "Peak advance required to arm the trail (ATR)",
        "heat_enabled": "Overheat tightening enabled",
        "heat_ext_atr": "Overheat extension threshold (ATR)",
        "heat_vol_ratio": "Overheat volume ratio",
        "heat_near_high_atr": "Overheat near-high distance (ATR)",
        "heat_trail_mult": "Overheat trail multiplier",
        "time_exit_index": "Time-exit deadline choice",
        "time_exit_gain_atr": "Progress hurdle for the time exit (ATR)",
        "cooldown_sessions": "Flat sessions after exit",
        "reentry_enabled": "Continuation re-entry enabled",
        "reentry_buffer_atr": "Re-entry buffer above previous peak (ATR)",
        "reentry_wait_index": "Re-entry waiting-window choice",
    }
    rows = []
    for name, value in decoded.items():
        if name in ("tail", "atr_period", "volume_reference", "trail_basis_name",
                    "time_limit_sessions", "reentry_wait_sessions", "domain"):
            continue
        if isinstance(value, float):
            value_text = f"{value:.4f}"
        else:
            value_text = str(value)
        rows.append((name, descriptions.get(name, ""), value_text))
    extra = [
        ("tail (decoded)", "Band tail quantile", f"{decoded['tail']:.2f}"),
        ("atr_period (decoded)", "ATR period in sessions", str(decoded["atr_period"])),
        ("volume_reference (decoded)", "Volume median window", str(decoded["volume_reference"])),
        ("time_limit_sessions (decoded)", "Time-exit deadline in sessions",
         str(decoded["time_limit_sessions"])),
        ("trail_basis_name (decoded)", "Trailing basis", str(decoded["trail_basis_name"])),
        ("reentry_wait_sessions (decoded)", "Re-entry waiting window",
         str(decoded["reentry_wait_sessions"])),
    ]
    rows.extend(extra)
    return table(["Parameter", "Role", "Sealed value"], rows)


def main():
    study = load_study()
    figures = build_figures(study)
    html = build_html(study, figures)
    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "index.html").write_text(html, encoding="utf-8")
    shutil.copyfile(COMBO_VAR / "combined-daily.csv", PUB / "combined-daily.csv")
    shutil.copyfile(COMBO_VAR / "long-daily-ledger.csv", PUB / "long-daily-ledger.csv")
    shutil.copyfile(COMBO_VAR / "long-episodes.csv", PUB / "long-episodes.csv")
    long_selection = study["long_selection"]["chosen"]
    (PUB / "long-parameters.json").write_text(json.dumps(dict(
        identity="gld-longrange-lifecycle-20261019-v1",
        selected=long_selection["decoded"],
        parameter_vector=long_selection["parameter_vector"],
        final_score=long_selection["final_score"], evidence=long_selection["evidence"],
        guards=long_selection["guards"],
        neighbour_fraction=long_selection.get("neighbour_fraction"),
        domain=study["long_protocol"]["parameterization"]["structural_domain"],
        bounds=study["long_protocol"]["parameterization"]["parameters"],
        protocol=study["long_protocol"],
    ), indent=2, default=str), encoding="utf-8")
    (PUB / "long-protocol.json").write_text(
        json.dumps(study["long_protocol"], indent=2, default=str), encoding="utf-8")
    summary = dict(identity=study["combo"]["identity"], design=study["combo"]["design"],
                   correlations=study["combo"]["correlations"],
                   overlap=study["combo"]["overlap"], controls=study["combo"]["controls"],
                   weight_grid=study["combo"]["weight_grid"],
                   frictions=study["combo"]["frictions"],
                   long_periods=study["long_eval"]["periods"],
                   short_periods=study["short_eval"]["periods"],
                   long_trade_stats=study["long_eval"]["trade_stats"],
                   limitations=study["combo"]["limitations"])
    (PUB / "combination-summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                                  encoding="utf-8")
    files = sorted(p for p in PUB.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (PUB / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"public": str(PUB), "files": len(files), "html_bytes": len(html)}, indent=1))


if __name__ == "__main__":
    import hashlib
    main()
