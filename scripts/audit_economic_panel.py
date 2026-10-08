"""Pin the published panel, audit decision coverage and quantify revision leakage.

The latest-vintage comparator is explicitly hindsight diagnostics, never a signal.
No price inputs, strategy selection, backtest, order or portfolio mutation.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from html import escape
import json
from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256
from systematic_trading.live.trading_calendar import previous_us_trading_day, us_equity_market_close
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.economics import EconomicInputs, NY, load_catalog
from systematic_trading.research.economic_features import VERSION, activity_feature
from systematic_trading.runtime_io import atomic_json

ROOT = Path("var/research/economic-panel-20261007-v1")
OUT = Path("research/economic-data-2026-10-07")
PARENT = Path("var/research/fallback-20261007-v1")
PROTOCOL = dict(version=VERSION, purpose="Data eligibility and revision sensitivity, no performance test",
    series=["ICSA", "PERMIT", "IPMAN"], availability="archive_daily",
    claims="four-week average / thirteen-week average - 1; positive means weakening",
    monthly="latest three months / same three months one year earlier - 1; negative means weakening",
    missing="reject incomplete feature windows; no fills", hindsight="latest published vintage truncated at the original endpoint, diagnostics only",
    planned_decisions=130, decision_source=str(PARENT / "baseline_decisions.json"))


def main():
    settings = AppSettings()
    catalog, pin = load_catalog(AnalyticsStore.from_settings(settings))
    if catalog["completed"] != catalog["expected"]:
        raise ValueError("Finish the published capture panel before the coverage study")
    manifest = json.loads((PARENT / "input_manifest.json").read_text())
    parent = PARENT / "baseline_decisions.json"
    if sha256(parent) != manifest["baseline_decisions.json"]:
        raise ValueError("Frozen strategy decision schedule changed")
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT / "protocol.json").exists() and json.loads((ROOT / "protocol.json").read_text()) != PROTOCOL:
        raise ValueError("Economic audit protocol changed")
    atomic_json(ROOT / "protocol.json", PROTOCOL)
    atomic_json(ROOT / "input_pin.json", dict(**pin, protocol_sha256=sha256(ROOT / "protocol.json"),
        decision_sha256=sha256(parent), code={str(p):sha256(p) for p in [Path(__file__),
        Path("src/systematic_trading/research/economic_features.py"), Path("src/systematic_trading/recorders/economics.py")]}))
    reader = EconomicInputs(**pin)
    decisions = json.loads(parent.read_text())
    days = sorted(decisions)
    if len(days) != PROTOCOL["planned_decisions"] or len(set(days)) != len(days):
        raise ValueError("Unexpected decision coverage")
    # Verify every original source and normalized payload before using a feature.
    for entry in catalog["snapshots"]:
        reader.snapshot(entry["series"], entry["vintage"])
    latest = {s:reader.snapshot(s, catalog["through"]) for s in PROTOCOL["series"]}
    output, failures = [], []
    for day in days:
        known = previous_us_trading_day(date.fromisoformat(day))
        vintage = str(known - timedelta(days=1))
        cutoff = datetime.combine(known, us_equity_market_close(known), NY)
        for series in PROTOCOL["series"]:
            try:
                snapshot = reader.snapshot(series, vintage, decision_at=cutoff, availability="archive_daily")
                feature = activity_feature(snapshot)
                revised = dict(latest[series], observations=[r for r in latest[series]["observations"] if r["date"] <= feature["endpoint"]])
                hindsight = activity_feature(revised)
                output.append(dict(decision=day, **feature, hindsight_value=hindsight["value"],
                                   hindsight_weakening=hindsight["weakening"], sign_changed=feature["weakening"] != hindsight["weakening"]))
            except ValueError as exc:
                inspected = reader.snapshot(series, vintage)
                failures.append(dict(decision=day, series=series, reason=str(exc), vintage=vintage,
                    endpoint=inspected["last"], age_days_at_decision=(known-date.fromisoformat(inspected["last"])).days,
                    freshness_limit_days=inspected["series"]["max_age_days"]))
    summary = dict(pin=pin, captures=catalog["completed"], decisions=len(days), feature_rows=len(output), failures=failures,
        per_series={s:dict(rows=sum(r["series"] == s for r in output),
            revised_values=sum(r["series"] == s and Decimal(r["value"]) != Decimal(r["hindsight_value"]) for r in output),
            direction_changes=sum(r["series"] == s and r["sign_changed"] for r in output)) for s in PROTOCOL["series"]},
        current=[activity_feature(latest[s]) for s in PROTOCOL["series"]], limitations=catalog["limitations"])
    atomic_json(ROOT / "features.json", output)
    atomic_json(ROOT / "assessment.json", summary)
    OUT.mkdir(parents=True, exist_ok=True)
    table = ''.join(f'<tr><td>{s}</td><td>{v["rows"]}</td><td>{v["revised_values"]}</td><td>{v["direction_changes"]}</td></tr>' for s,v in summary["per_series"].items())
    samples = [r for r in output if r["sign_changed"]][:12]
    examples = ''.join(f'<tr><td>{r["decision"]}</td><td>{r["series"]}</td><td>{100*float(r["value"]):.3f}%</td><td>{100*float(r["hindsight_value"]):.3f}%</td></tr>' for r in samples)
    gaps = ''.join(f'<tr><td>{r["decision"]}</td><td>{r["series"]}</td><td>{r["endpoint"]}</td><td>{r["age_days_at_decision"]} / {r["freshness_limit_days"]} days</td></tr>' for r in failures)
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Economic data readiness</title>
<style>body{{font:16px/1.7 system-ui;color:#21354c;background:#f4f7fb;margin:0}}main{{max-width:980px;margin:40px auto;padding:32px;background:white;border-radius:16px}}h1{{line-height:1.2}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #dde4ef}}th{{background:#eff4fa}}.muted{{color:#65748a}}code{{overflow-wrap:anywhere;font-size:12px}}a{{color:#315bc2}}</style><main>
<p class="muted">ETF research · October 7, 2026</p><h1>Economic data is now a versioned research input</h1>
<p>{summary["captures"]} published captures cover three indicators and {len(days)} monthly decisions. The audit produced {len(output)} decision/indicator measurements with {len(failures)} coverage failures. This report evaluates data readiness and revision leakage, not strategy returns.</p>
<p><a href="http://127.0.0.1:8000/platform/market-data-audit?view=economics">Open Economic Data in the app</a></p>
<h2>Why the earlier vintage matters</h2><p>The comparison below recomputes the same measurement from the latest revised history, stopping at exactly the original observation endpoint. The later version is hindsight evidence only. Direction changes mean that replacing the original snapshot could change an economic weakening flag.</p>
<table><tr><th>Indicator</th><th>Monthly measurements</th><th>Values revised</th><th>Weakening flag changes</th></tr>{table}</table>
<h2>Examples of revised direction</h2><table><tr><th>Decision</th><th>Indicator</th><th>As archived then</th><th>Latest revised history</th></tr>{examples}</table>
<h2>Freshness failures remain excluded</h2><p>All scheduled snapshots were captured, but these five readings exceed the predeclared age limit. They remain visible for inspection and cannot silently enter a signal. Before a strategy replay, freeze how the optional economic overlay behaves when a reading is unavailable; do not backfill it from later releases or relax the limit after inspecting returns.</p><table><tr><th>Decision</th><th>Indicator</th><th>Latest observed period</th><th>Age / limit</th></tr>{gaps}</table>
<h2>Fixed measurements</h2><p>Claims: four-week mean relative to thirteen-week mean; positive means weakening. Permits and manufacturing: latest three months relative to the same three months one year earlier; negative means weakening. These definitions were fixed before inspecting the revision comparison. No weighting, threshold search or portfolio rule was fitted.</p>
<h2>Availability and limits</h2><p>{'<br>'.join(escape(s) for s in catalog["limitations"])}</p>
<p>US activity cannot be assigned automatically to other countries. Manufacturing output confirms activity; it is not classified here as a leading indicator. Full release calendars, dated consensus estimates, ETF holdings/issuance and sector valuations remain separate data work.</p>
<h2>Next experiment</h2><p>Freeze a small US equity risk-overlay comparison against the unchanged F3 and active SOTA, with matched exposure controls, costs and delays. Use only this pinned panel and published audited ETF prices. No monitored strategy, allocation or execution authority changed.</p>
<p class="muted">Catalog batch: <code>{pin["batch"]}</code><br>Local evidence: {escape(str(ROOT.resolve()))}</p>
<p>Sources: <a href="https://fred.stlouisfed.org/series/ICSA">Claims</a> · <a href="https://fred.stlouisfed.org/series/PERMIT">Permits</a> · <a href="https://fred.stlouisfed.org/series/IPMAN">Manufacturing</a> · <a href="https://alfred.stlouisfed.org/help">ALFRED availability</a></p></main></html>'''
    (OUT / "assessment.html").write_text(html, encoding="utf8")
    atomic_json(OUT / "receipt.json", dict(outputs={str(p):sha256(p) for p in [OUT / "assessment.html", ROOT / "features.json", ROOT / "assessment.json", ROOT / "input_pin.json", ROOT / "protocol.json"]}))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
