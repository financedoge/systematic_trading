"""Freeze and audit the expanded published economic panel; no portfolio outcomes."""
from datetime import date, datetime, timedelta
from html import escape
import json
from pathlib import Path
import shutil

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256
from systematic_trading.live.trading_calendar import previous_us_trading_day, us_equity_market_close
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.economics import EconomicInputs, NY, load_catalog
from systematic_trading.research.economic_leading_features import SPEC, LEADING, CONTEXT, panel
from systematic_trading.research.momentum_replay import checked_files
from systematic_trading.runtime_io import atomic_json

ROOT = Path("var/research/economic-leading-panel-20261007-v2")
OUT = Path("research/economic-leading-data-2026-10-07")
PARENT = Path("var/research/fallback-20261007-v1")


def main():
    catalog, pin = load_catalog(AnalyticsStore.from_settings(AppSettings()))
    if catalog["completed"] != catalog["expected"]:
        raise ValueError("Expanded historical panel is not fully published")
    checked_files(PARENT, "input_manifest.json")
    decisions = json.loads((PARENT/"baseline_decisions.json").read_text())
    if len(decisions) != 130:
        raise ValueError("Unexpected frozen decision schedule")
    if ROOT.exists():
        raise FileExistsError("Keep frozen evidence; use a new version for another audit")
    ROOT.mkdir(parents=True)
    atomic_json(ROOT/"protocol.json", dict(**SPEC, purpose="Data readiness only, no returns or selection",
        decision_sha256=sha256(PARENT/"baseline_decisions.json"), decisions=130))
    atomic_json(ROOT/"input_pin.json", pin)
    # Freeze executable source as well as its hashes before reading feature outcomes.
    paths = [Path(__file__), Path("src/systematic_trading/research/economic_leading_features.py"),
             Path("src/systematic_trading/recorders/economics.py"), Path("config/economic-recorders.json")]
    for p in paths:
        target = ROOT/"source"/p.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    atomic_json(ROOT/"source_manifest.json", {p.name:sha256(p) for p in (ROOT/"source").iterdir()})
    reader = EconomicInputs(**pin)
    for entry in catalog["snapshots"]:
        reader.snapshot(entry["series"], entry["vintage"])
    rows = {}
    for day in sorted(decisions):
        known = previous_us_trading_day(date.fromisoformat(day))
        if decisions[day]["known_through"] != str(known):
            raise ValueError("Decision clock mismatch")
        cutoff = datetime.combine(known, us_equity_market_close(known), NY)
        rows[day] = panel(reader, str(known-timedelta(days=1)), cutoff)
    atomic_json(ROOT/"features.json", rows)
    old_pin = json.loads(Path("var/research/economic-panel-20261007-v1/input_pin.json").read_text())
    old_reader = EconomicInputs(old_pin["root"], old_pin["batch"])
    new_entries = {(r["series"],r["vintage"]):r for r in catalog["snapshots"]}
    for entry in old_reader.catalog["snapshots"]:
        if new_entries[entry["series"], entry["vintage"]] != entry:
            raise ValueError("Original publication was replaced during expansion")
    summary = dict(pin=pin, captures=catalog["completed"], original_captures_preserved=len(old_reader.catalog["snapshots"]),
        decisions=len(rows), leading_ready=sum(r["leading_ready"] for r in rows.values()),
        context_ready=sum(r["context_ready"] for r in rows.values()),
        combined_ready=sum(r["leading_ready"] and r["context_ready"] for r in rows.values()),
        per_series={s:dict(captures=sum(e["series"]==s for e in catalog["snapshots"]),
            usable_decisions=sum(s in r["sources"] for r in rows.values())) for s in LEADING+CONTEXT},
        unavailable=[dict(decision=day, **u) for day,r in rows.items() for u in r["unavailable"]],
        limits=catalog["limitations"], source_gaps=catalog["config"]["source_gaps"])
    atomic_json(ROOT/"assessment.json", summary)
    OUT.mkdir(parents=True, exist_ok=True)
    table = ''.join(f'<tr><td>{escape(s["name"])}<br><small>{s["id"]}</small></td>'
        f'<td>{"Leading candidate" if s["id"] in LEADING else "Context only"}</td>'
        f'<td>{summary["per_series"][s["id"]]["captures"]}</td>'
        f'<td>{summary["per_series"][s["id"]]["usable_decisions"]} / 130</td>'
        f'<td><a href="{escape(s["reference_url"])}">Source</a> · {escape(s["role"])}</td></tr>'
        for s in catalog["config"]["series"])
    unavailable = ''.join(f'<tr><td>{r["decision"]}</td><td>{r["series"]}</td><td>{r["endpoint"]}</td>'
        f'<td>{r["age_days"]} / {r["max_age_days"]} days</td><td>{r["reason"]}</td></tr>' for r in summary["unavailable"])
    gaps = ''.join(f'<li><strong>{escape(s["name"])}:</strong> {escape(s["detail"])} '
        f'<a href="{escape(s["reference_url"])}">Source</a></li>' for s in summary["source_gaps"])
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Leading economic data readiness</title><style>body{{font:16px/1.65 system-ui;color:#21354c;background:#f4f7fb;margin:0}}main{{max-width:1120px;margin:32px auto;padding:32px;background:white;border-radius:16px}}h1{{line-height:1.2}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dde4ef}}th{{background:#eff4fa}}small,.muted{{color:#65748a}}code{{overflow-wrap:anywhere;font-size:12px}}a{{color:#315bc2}}.scroll{{overflow:auto}}li{{margin-bottom:12px}}</style><main>
<p class="muted">ETF research · October 7, 2026 · Data audit</p><h1>Leading signals first, inflation and employment in context</h1>
<p>Expanded from three to eleven indicators: seven leading candidates and four context series. Published {summary["captures"]:,} exact-vintage captures and preserved all {summary["original_captures_preserved"]} original publications. GDP is excluded. This is data readiness evidence; no portfolio return improvement is claimed.</p>
<p><a href="http://127.0.0.1:8000/platform/market-data-audit?view=economics">Inspect Economic Data in the app</a></p>
<h2>Coverage available at the decision cutoff</h2><p>Of 130 monthly decisions, the full leading group is usable at {summary["leading_ready"]}, the context group at {summary["context_ready"]}, and both at {summary["combined_ready"]}. Missing or stale features stay unavailable. A captured vintage is not necessarily a usable prediction input.</p>
<div class="scroll"><table><tr><th>Indicator</th><th>Research role</th><th>Vintages</th><th>Usable decisions</th><th>Source and limits</th></tr>{table}</table></div>
<h2>How the next comparison uses this panel</h2><p>Fit a small decision tree separately for each ETF, alongside a regularized linear model using identical dates and inputs. Compare leading-only models first, then add the context group as a separate test. Retain unchanged SOTA and defensive-cash parents as controls. Allocation can increase for predicted beneficiaries and decrease for weaker assets, subject to the parent eligibility and invested budget. Compare costs, delays, turnover, Sharpe and Calmar with complete shared portfolio reports.</p>
<p>Use expanding chronological training and the feature vintage originally available for each row. A return label is eligible only after its entire holding period is known; preprocessing uses training data only. Previously inspected history is retrospective validation, not untouched out-of-sample evidence. More features do not create more independent monthly observations.</p>
<h2>Measurements frozen before portfolio outcomes</h2><p>{escape(SPEC["transformations"])}</p><p>National PMI is not supplied by the two Philadelphia survey series. New orders are nominal. Payrolls and CPI are not labelled leading. Economic changes are not consensus surprises, and a leading economic measure need not lead asset prices.</p>
<h2>Further source work</h2><ul>{gaps}</ul>
<h2>Unavailable historical readings</h2><div class="scroll"><table><tr><th>Decision</th><th>Series</th><th>Latest period</th><th>Age / allowed</th><th>Reason</th></tr>{unavailable}</table></div>
<h2>Availability and provenance</h2><p>{escape(' '.join(summary["limits"]))}</p><p>Catalog batch: <code>{pin["batch"]}</code>. All requested snapshot manifests and original bytes verified. Actual first capture is in October 2026; historical availability uses an explicit daily-archive assumption, not certified intraday release timestamps.</p>
</main></html>'''
    (OUT/"assessment.html").write_text(html, encoding="utf8")
    atomic_json(ROOT/"artifact_manifest.json", {str(p.relative_to(ROOT)):sha256(p) for p in ROOT.rglob("*") if p.is_file()})
    print(json.dumps({k:v for k,v in summary.items() if k not in {"limits", "source_gaps", "unavailable", "per_series"}}, indent=2))


if __name__ == "__main__":
    main()
