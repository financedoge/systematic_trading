"""Audit loss-feedback timing on immutable baseline trades; no adaptive P&L.

Write a compact full-pool diagnostic and figures. Input bars remain the existing
hash-verified published-history report cache; this does not fetch market data.
"""
from __future__ import annotations

import gzip
import hashlib
import html
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import research_latent_slope as study  # noqa: E402
from systematic_trading.research.strategy_health import loss_streaks  # noqa: E402

OUT = ROOT / "research/strategy-health-20261026-v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def audit_trades(chart):
    """Use only newly entered, closed trades; exclude exit-day post-fill close."""
    days = np.array(chart["days"], dtype="datetime64[D]")
    close = np.asarray(chart["close"], float)
    rows = []
    for ep in chart["trades"]:
        if ep["exit"] is None or ep["entry"] < chart["evaluation_start"]:
            continue
        a = int(np.searchsorted(days, np.datetime64(ep["entry"])))
        b = int(np.searchsorted(days, np.datetime64(ep["exit"])))
        if str(days[a]) != ep["entry"] or str(days[b]) != ep["exit"]:
            raise ValueError("Trade calendar mismatch")
        held = close[a:b]  # exit fills at the open, before this day's close
        peak = a + int(np.argmax(held)) if len(held) else None
        gross = ep["exit_price"] / ep["entry_price"] - 1
        mfe = max(0., float(np.max(held) / ep["entry_price"] - 1)) if len(held) else None
        mae = min(0., float(np.min(held) / ep["entry_price"] - 1)) if len(held) else None
        rows.append(dict(entry=ep["entry"], exit=ep["exit"], net_return=ep["net_return"],
                         reason=ep["reason"], close_mfe=mfe, close_mae=mae,
                         peak_date=str(days[peak]) if peak is not None else None,
                         sessions_to_peak=peak-a if peak is not None else None,
                         close_peak_giveback=mfe-gross if mfe is not None else None,
                         baseline_cumulative_at_exit=chart["nav"][b] / 100 - 1))
    if any(a["exit"] > b["exit"] for a, b in zip(rows, rows[1:])):
        raise ValueError("Trades not ordered by completed outcome")
    for row, streak in zip(rows, loss_streaks([r["net_return"] for r in rows]), strict=True):
        row["loss_streak"] = streak
        row["threshold_event"] = "defensive threshold" if streak == 3 else "pause/refit threshold" if streak == 4 else None
        ix = int(np.searchsorted(days, np.datetime64(row["exit"]))) + 1
        row["earliest_action"] = str(days[ix]) if ix < len(days) else None
    return rows


def null_run_probability(n, k, loss_probability=.5):
    """Exact toy IID null; this is not a significance test for ETF outcomes."""
    alive = np.zeros(k); alive[0] = 1.
    for _ in range(n):
        nxt = np.zeros(k)
        nxt[0] = alive.sum() * (1-loss_probability)
        nxt[1:] = alive[:-1] * loss_probability
        alive = nxt
    return float(1-alive.sum())


def figure(chart, trades, symbol, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as dates
    import matplotlib.pyplot as plt

    days = np.array(chart["days"], dtype="datetime64[D]")
    close, volume = np.asarray(chart["close"], float), np.asarray(chart["volume"], float)
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(13, 10), layout="constrained",
                             height_ratios=(2.3, .65, 1, .8))
    axes[0].plot(days, close, color="#173d54", label="Adjusted close")
    axes[0].plot(days, np.asarray(chart["stop"], float), color="#bd5361", lw=1,
                 label="Existing close-test protection")
    for ep in chart["trades"]:
        if ep["entry"] < chart["evaluation_start"]:
            continue
        a = np.datetime64(ep["entry"])
        b = np.datetime64(ep["exit"]) if ep["exit"] else days[-1]
        axes[0].axvspan(a, b, color="#008b77", alpha=.08)
        axes[0].scatter(a, ep["entry_price"], marker="^", color="#008b77", s=30)
        if ep["exit"]:
            axes[0].scatter(b, ep["exit_price"], marker="v", color="#be4656", s=30)
    axes[0].set_ylabel("Adjusted USD")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[1].bar(days, volume / 1e6, color="#9eabb7", width=1.5)
    axes[1].set_ylabel("Raw volume\n(million shares)")
    exits = np.array([r["exit"] for r in trades], dtype="datetime64[D]")
    returns = np.array([r["net_return"] * 100 for r in trades])
    axes[2].bar(exits, returns, width=10, color=np.where(returns < 0, "#be4656", "#008b77"))
    axes[2].axhline(0, color="#555", lw=.5)
    axes[2].set_ylabel("Closed trade\nnet return (%)")
    axes[3].step(exits, [r["loss_streak"] for r in trades], where="post", color="#173d54")
    for threshold, color in ((3, "#b07512"), (4, "#be4656")):
        axes[3].axhline(threshold, color=color, ls="--", lw=.8, label=f"{threshold} losses")
        first = next((r for r in trades if r["loss_streak"] == threshold), None)
        if first:
            x = np.datetime64(first["exit"])
            for ax in axes:
                ax.axvline(x, color=color, ls=":", lw=1)
            axes[0].annotate(f"First {threshold} losses\n{first['exit']}",
                (x, close[int(np.searchsorted(days, x))]), xytext=(10, 35 if threshold == 3 else -40),
                textcoords="offset points", fontsize=8, color=color,
                arrowprops=dict(arrowstyle="-", color=color))
    axes[3].set_ylabel("Consecutive\nnet losses")
    axes[3].legend(loc="upper right", fontsize=8)
    axes[3].xaxis.set_major_locator(dates.MonthLocator(interval=3))
    axes[3].xaxis.set_major_formatter(dates.DateFormatter("%Y-%m"))
    axes[3].tick_params(axis="x", rotation=35)
    for ax in axes:
        ax.grid(alpha=.16)
        ax.axvline(np.datetime64(chart["evaluation_start"]), color="#777", lw=.8, ls="--")
    fig.suptitle(f"{symbol} | loss-warning timing on the unchanged strategy\n"
                 "Entry/exit fills and close-based protection; no adaptive-return claim", fontsize=13)
    fig.savefig(path, dpi=145)
    plt.close(fig)


def main():
    fits = study.verified()
    manifest = json.loads((study.OUT / "manifest.json").read_text())
    inputs = ("chart-data.json.gz", "asset-results.json", "diagnostics.json", "protocol.json", "fit-manifest.json")
    for name in inputs:
        if digest(study.OUT / name) != manifest["files"][name]:
            raise ValueError("Changed frozen source " + name)
    OUT.mkdir(exist_ok=True)
    recipe = dict(identity=OUT.name, purpose="Diagnostic only, no adaptive returns or new model fit",
        source_inputs={name: digest(study.OUT / name) for name in inputs},
        rules="Full risky ETF pool; training-selected primary 5bp/side,next open; reset monitor at evaluation boundary; newly entered completed trades only; net<0 loss; zero breaks streak; first3/4 close events actionable next session. MFE/MAE use held closes excluding exit-day close and are hindsight diagnostics.",
        controller="Research reference: actual3 losses defensive at.5 risk,4 pause/refit event; fresh shadow4 trades >=3 wins and positive sumR/compound return ->.25 probation;3 actual probation trades >=2 wins and positive sumR/compound return ->normal;2 probation losses repause. One declared refit candidate per pause. No fitting or routing authority.",
        code={str(p.relative_to(ROOT)).replace(chr(92), "/"): digest(p) for p in (
            Path(__file__), ROOT / "src/systematic_trading/research/strategy_health.py",
            ROOT / "tests/test_strategy_health.py", ROOT / "tests/test_strategy_health_audit.py")})
    protocol_path = OUT / "protocol.json"
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != recipe:
        raise ValueError("Diagnostic recipe changed; version the experiment")
    write(protocol_path, recipe)
    charts = json.loads(gzip.decompress((study.OUT / "chart-data.json.gz").read_bytes()))
    primary = [r for r in json.loads((study.OUT / "asset-results.json").read_text())
               if r["variant"] == "selected" and r["cost_bp"] == 5 and r["delay"] == 0 and r["symbol"] != "BIL"]
    results, ledgers = [], {}
    for r in primary:
        symbol, era = r["symbol"], r["era"]
        family = fits[symbol][era]["selected"]["selected"]["parameters"]["family"]
        key = f"{symbol}_{era}"
        trades = audit_trades(charts[f"{key}_{family}"])
        ledgers[key] = trades
        events = {k: next((t for t in trades if t["loss_streak"] == k), None) for k in (3, 4)}
        results.append(dict(symbol=symbol, era=era, family=family, baseline_return=r["cumulative"],
            closed_new_trades=len(trades), max_loss_streak=max([t["loss_streak"] for t in trades], default=0),
            first_three=events[3], first_four=events[4]))
    summary = {}
    for era in ("late", "early"):
        rows = [r for r in results if r["era"] == era]
        positive = [r for r in rows if r["baseline_return"] > 0]
        weakest = min(rows, key=lambda r: (r["baseline_return"], r["symbol"]))
        summary[era] = dict(cases=len(rows), with_three=sum(r["first_three"] is not None for r in rows),
            with_four=sum(r["first_four"] is not None for r in rows), profitable_cases=len(positive),
            profitable_with_three=sum(r["first_three"] is not None for r in positive),
            profitable_with_four=sum(r["first_four"] is not None for r in positive), weakest=weakest["symbol"])
        key = f"{weakest['symbol']}_{era}"
        figure(charts[f"{key}_{weakest['family']}"], ledgers[key], weakest["symbol"], OUT / f"{key}_warnings.png")
    summary["iid_fair_outcome_example"] = {f"at_least_{k}_losses_in14": null_run_probability(14, k) for k in (3, 4)}
    write(OUT / "summary.json", summary)
    write(OUT / "pool-audit.json", results)
    write(OUT / "trade-diagnostics.json", ledgers)
    pct = lambda x: f"{100*x:+.2f}%"
    table = []
    for r in sorted(results, key=lambda x: (x["era"] != "late", x["baseline_return"], x["symbol"])):
        event = lambda n: r[n]["exit"] if r[n] else "—"
        table.append(f'<tr data-era="{r["era"]}"><td>{r["symbol"]}</td><td>{r["era"]}</td>'
                     f'<td>{pct(r["baseline_return"])}</td><td>{r["closed_new_trades"]}</td>'
                     f'<td>{r["max_loss_streak"]}</td><td>{event("first_three")}</td><td>{event("first_four")}</td></tr>')
    weat = ledgers["WEAT_late"]
    trades_html = "".join(f'<tr><td>{t["entry"]}</td><td>{t["exit"]}</td><td>{pct(t["net_return"])}</td>'
        f'<td>{pct(t["close_mfe"])}</td><td>{t["peak_date"]}</td><td>{t["loss_streak"]}</td>'
        f'<td>{html.escape(t["reason"])}</td></tr>' for t in weat)
    body = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Learning from losses — strategy health</title><style>
body{font:16px/1.55 system-ui;max-width:1200px;margin:40px auto;padding:0 22px;color:#17364c;background:#f7f9fb}
h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}img{width:100%;background:white;border:1px solid #d7e1e7}
table{border-collapse:collapse;width:100%;font-size:14px;background:white}td,th{padding:8px 10px;text-align:right;border-bottom:1px solid #e1e6eb}td:first-child,th:first-child{text-align:left}
.note{padding:18px;background:#fff1d9;border-left:4px solid #b07512}.scroll{overflow:auto}code{background:#e8eff3;padding:2px 5px}
</style><h1>Learning from losses</h1><p>26 October 2026 · Research controller and frozen-trade diagnostic</p>
<p class="note"><b>This is a warning-timing audit, not an adaptive strategy backtest.</b> Entries, exits and returns below belong to the unchanged training-selected strategies. Changing risk, exits or refitting would change their subsequent trades; those must be resimulated before claiming improvement.</p>
<h2>Proposed response</h2><table><tr><th>Health state</th><th>Trigger / recovery</th><th>Risk budget</th></tr>
<tr><td>Normal</td><td>Original market signal and protection</td><td>100%</td></tr>
<tr><td>Defensive</td><td>3 consecutive completed net losses; recover after 2 consecutive wins and positive phase net/R totals</td><td>50%</td></tr>
<tr><td>Paused</td><td>4 consecutive net losses; request one refit review; collect fresh shadow evidence</td><td>0 new exposure</td></tr>
<tr><td>Probation</td><td>4 fresh shadow trades, at least 3 wins and positive net/R totals; then 3 actual trades, at least 2 wins and positive net/R totals restore normal</td><td>25%</td></tr></table>
<p>Two consecutive probation losses pause again. Refit means a new candidate, not automatic replacement. All changes take effect no earlier than the next session after evidence is known. These are proposed research constants, not fitted optimal thresholds.</p>
<p><a href="../../docs/strategy-health-framework-2026-10-26.md">Full design, mathematical rules and next experiment</a> · <a href="../latent-slope-20261025-v1/index.html">All ETF trend charts and exact-date inspection</a></p>
<h2>WEAT: when would a streak warning become available?</h2><img src="WEAT_late_warnings.png" alt="WEAT price, volume, trade outcomes and first three/four-loss warning dates">
<p>Green triangles = entries; red triangles = exits; shaded spans = held periods. Warnings use completed net outcomes and are actionable next session. A winning trade resets a consecutive-loss streak, even if earlier losses remain unrecovered.</p>
<div class="scroll"><table><tr><th>Entry</th><th>Exit</th><th>Net return</th><th>Best held-close gain</th><th>Close-peak date</th><th>Loss streak</th><th>Exit reason</th></tr>__WEAT__</table></div>
<p>Best held-close gain is a hindsight diagnostic, excludes the exit session's later close, includes neither intraday highs nor an executable take-profit assumption. It cannot be used as an entry-time feature.</p>
<h2>Full supported risky pool</h2><p>Late = 2023–October 2026; early = 2020–2022. Monitor starts neutral at each evaluation boundary; carried-in and still-open outcomes are excluded. The return column retains the original whole-period result. Cash reference BIL is excluded.</p>
<p>__SUMMARY__</p><label>Evaluation <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option><option value="all">Both</option></select></label>
<div class="scroll"><table id="pool"><thead><tr><th>ETF</th><th>Era</th><th>Original net return</th><th>Fresh closed trades</th><th>Max losing streak</th><th>First 3 losses</th><th>First 4 losses</th></tr></thead><tbody>__POOL__</tbody></table></div>
<h2>Earlier weakest case: MCHI</h2><img src="MCHI_early_warnings.png" alt="MCHI earlier evaluation loss-warning audit">
<p><a href="pool-audit.json">Full pool audit</a> · <a href="trade-diagnostics.json">Trade diagnostics</a> · <a href="protocol.json">Pinned diagnostic recipe</a></p>
<script>const era=document.getElementById('era');function filter(){for(const r of document.querySelectorAll('#pool tbody tr'))r.hidden=era.value!=='all'&&r.dataset.era!==era.value}era.addEventListener('change',filter);filter();</script></html>'''
    sentence = "; ".join(f'{era}: {s["with_three"]}/{s["cases"]} have a three-loss run, including '
        f'{s["profitable_with_three"]}/{s["profitable_cases"]} of the ultimately profitable cases'
        for era, s in summary.items() if era in ("late", "early"))
    (OUT / "index.html").write_text(body.replace("__WEAT__", trades_html).replace("__POOL__", "".join(table))
        .replace("__SUMMARY__", sentence + ". A streak is a risk warning, not proof of a new market regime."), encoding="utf-8")
    write(OUT / "manifest.json", {p.name: digest(p) for p in OUT.iterdir() if p.is_file() and p.name != "manifest.json"})
    print(json.dumps(dict(summary=summary, weat=weat), indent=2))


if __name__ == "__main__":
    main()
