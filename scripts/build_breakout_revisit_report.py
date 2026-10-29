"""Shared full report plus implementation, component and chronological evidence."""
from decimal import Decimal
from datetime import UTC, datetime
import html
import json
import shutil
import subprocess

import revisit_breakout_research as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
from systematic_trading.research.fr25_lifecycle_monitoring import current_allocation
from systematic_trading.research.strategy_catalog import StrategyDefinition
from systematic_trading.research.strategy_diagram import label


def table(rows):
    body = "".join(f"<tr><td>{html.escape(r['period'])}</td><td>{html.escape(r['scenario'])}</td>"
        f"<td>{r['cost_bp']}</td><td>{r['delay']}</td><td>{r['cagr']:.2%}</td><td>{r['sharpe']:.3f}</td>"
        f"<td>{r['max_drawdown']:.2%}</td><td>{r['annual_turnover']:.2f}</td><td>{r['annual_cost_bps']:.1f}</td></tr>" for r in rows)
    return "<div style='overflow:auto'><table class='study-table'><thead><tr><th>Period</th><th>Strategy</th><th>bp/side</th><th>Delay</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th><th>Turnover/year</th><th>Cost bp/year</th></tr></thead><tbody>" + body + "</tbody></table></div>"


def main():
    output, work = study.OUTPUT, study.WORK
    protocol = json.loads((output / "protocol.json").read_text())
    if protocol != study.protocol():
        raise ValueError("Study changed")
    evidence = json.loads((output / "results.json").read_text())
    native = json.loads((output / "native-checks.json").read_text())
    if len(native) != 3 or any(r["max_nav_difference"] > .011 for r in native):
        raise ValueError("Native validation incomplete")
    calc = json.loads((work / (study.PRIMARY + "-calculation.json")).read_text())
    # Economic payload uses a shared legacy-named adapter. Replace its inherited
    # descriptive metadata for display; quantities, dates and prices stay exact.
    for proposal in calc["proposals"]:
        for target in proposal["targets"]:
            target["sleeve"] = "breakout-revisit"
            target["rationale"] = "63-session breakout regime; six rank-buffered slots; 6 ATR trailing exit"
            target.pop("hold_horizon_months", None)
    panel = study.frozen._load_panel()
    sessions = [r["trade_date"] for r in calc["nav_series"]]
    prices = {str(s): {str(day): float(quantize_money(Decimal(str(panel["close"][i, j]))))
              for i, day in enumerate(panel["days"]) if str(day) >= sessions[0]} for j, s in enumerate(panel["symbols"])}
    prices["URTH"] = {str(day): float(quantize_money(Decimal(str(panel["urth_close"][i]))))
                      for i, day in enumerate(panel["days"]) if str(day) >= sessions[0]}
    def nav(name):
        return json.loads((work / (name + "-calculation.json")).read_text())["nav_series"]
    report, warnings = build_backtest_report_data(result=calc,
        result_path=work / (study.PRIMARY + "-calculation.json"), split_date="2023-01-01",
        benchmark_nav_series=nav("FR25"), benchmark_name="FR25 · matched USD",
        extra_benchmarks=[dict(id="urth", name="URTH", nav_series=nav("URTH")),
                          dict(id="momentum", name="Monthly momentum control", nav_series=nav("momentum_monthly"))],
        market_prices=prices, market_fx_rates={s: 1. for s in sessions})
    recipe = json.loads(study.frozen.RECIPE_PATH.read_text())
    definition = StrategyDefinition(key="breakout_revisit_63_6_v1", name="Breakout + dynamic exits: research revisit",
        sleeve_name="breakout-revisit", state="research", universe_key="supported52",
        universe_members=tuple(m for m in recipe["universeMembers"] if m["symbol"] != "URTH"),
        scheduler="dynamic_membership_monthly_anchor", description=protocol["entry"] + " " + protocol["exit"] + " " + protocol["selection"])
    steps = [
        ("Verify 52 ETF histories and pinned published hashes", "Adjusted OHLC; audited activity; USD account; retrospective cohort limitation."),
        ("Close above the prior 63-session highest close", "One confirming close; virtual entry at the next open; one common rule for every ETF."),
        ("Track the asset regime with a ratcheting stop", "Initial 3 ATR risk stop; highest close minus 6 ATR; check entry close; exit next open."),
        ("Rank eligible positive-momentum assets", "126-session log momentum / 63-session volatility; keep incumbents through rank 8."),
        ("Adopt up to six fixed slots; park vacancies in BIL", "98% / 6 per slot and 2% cash; membership events plus month-end anchors."),
        ("Execute and compare after costs", "Actual portfolio next open; +1-session and 5/10/20 bp stress; matched monthly/exit controls."),
    ]
    svg = ''.join(f'<rect x="10" y="{15+i*85}" width="880" height="70" rx="8" fill="#eef4fa"/>' + label([a, b], 25, 40+i*85) for i, (a, b) in enumerate(steps))
    current = current_allocation(calc)
    current["notes"] = "Historical USD research snapshot through 2026-10-12. Virtual asset stops gate eligibility; they are not broker stop orders. No current app registration or execution authority."
    report.update(title=definition.name, accountingCurrency="USD", database="Pinned published audited histories",
        modelRegime=study.br.VERSION + "; shared unfitted thresholds", splitLabel="Inspected development boundary",
        sampleLabels={"in_sample": "Initial cash anchor", "out_of_sample": "2023–2026 inspected development"},
        strategyDefinition=definition.to_dict(), currentAllocation=current,
        decisionDiagrams=[dict(title="Complete breakout selection decision flow", note="Research only; no recurring app registration",
            svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 530">' + svg + '</svg>')],
        monitoring=dict(lifecycle="research", method="frozen_research_replay", artifactEndDate=sessions[-1],
            computedAt=datetime.now(UTC).isoformat(),
            monitoredThrough=sessions[-1], priceThrough=sessions[-1], revision=output.name, engine="python/native-LEAN",
            prospectiveStart="Not activated", prospectiveObservations=0, currentSignalAvailable=False, status="historical_only"),
        warnings=[*warnings, *protocol["limitations"], "No passing SOTA gate; do not promote. Asset eligibility stops are virtual regime features, not actual-portfolio loss limits.",
                  "This study uses price-supported membership, without the older panel's rolling dollar-volume admission mask. It does not establish liquidity or execution eligibility.",
                  "Supplementary construction experiment only. It does not answer whether individually fitted ETF signals have alpha; a separate fitted-signal audit follows the operator clarification."])
    rendered = render_backtest_report_html(report)
    rows = evidence["results"]
    primary = [r for r in rows if r["period"] == "late" and r["scenario"] in {study.PRIMARY, "FR25", "momentum_dynamic"}]
    base = [r for r in rows if r["cost_bp"] == 5 and r["delay"] == 0]
    audit = json.loads((output / "implementation-audit.json").read_text())
    attribution = json.loads((output / "late-attribution.json").read_text())
    attr_rows = ''.join(f"<tr><td>{r['symbol']}</td><td>{r['net_pnl_usd']:,.2f}</td><td>{r['fees_usd']:,.2f}</td></tr>"
        for r in sorted(attribution["rows"], key=lambda r: -r["net_pnl_usd"]))
    section = f"""<style>.study-table{{border-collapse:collapse;width:100%;font-size:13px;text-align:right}}
    .study-table td,.study-table th{{padding:8px;border-bottom:1px solid #d8e1eb}}.study-table td:nth-child(2){{text-align:left}}
    .study{{margin:24px;padding:24px;background:#fff;color:#183149;border:1px solid #b5c7d8;border-radius:10px}}
    .study p{{max-width:1100px;line-height:1.6}}</style><section class="study">
    <h1>Breakout and dynamic exits — implementation problems were real; portfolio edge is unproven</h1>
    <p>136 predeclared portfolio replays. Primary fails all 6 SOTA friction gates; passes 4/8 component comparisons,
    all in the earlier period. Nothing is promoted. This is inspected historical research through October 12, 2026.</p>
    <p>Fixed one-close confirmation, asymmetric entry/exit delay, skipped entry-close stops, cooldown bypass,
    confirmation ATR and unfunded fee behavior in a separate version. Exposed close-time decisions separately
    from held positions to remove the scanner's extra signal lag. Frozen legacy code remains unchanged.</p>
    <p>{sum(r['confirm_sessions']==1 for r in audit)} of 52 fitted short rules request one-close confirmation.
    The corrected replay finds {sum(r['entry_close_exits'] for r in audit)} entry-close exits across the full asset histories.
    Legacy fitted activity averages 59.20% versus corrected 58.73% of common-panel asset days: corrections do not solve weak selectivity.</p>
    <p>The unfitted trailing rule earns 4.25% CAGR / 0.360 Sharpe / −18.17% drawdown in the later period, versus
    FR25 16.51% / 1.450 / −8.65%. Momentum-only dynamic selection earns 8.97% / 0.680 / −14.36%.
    The trailing rule reduces early-period drawdown (−13.70% versus momentum's −21.84%) but reverses that advantage later.
    Its 27.00× annual turnover costs 135.0 bp/year at 5 bp/side; the rejection is based on net results, not a cost ceiling.</p>
    <p>Daily ranking replacement helps relative to sticky slots within this tested rule, but monthly versus dynamic timing
    is unstable across eras. Keep breakout/stop distance as hypotheses for ranking or position sizing; do not treat this binary gate
    or universal trailing stop as validated alpha. Larger pools require separate identity/coverage/audit admission and overlap controls.</p>
    <h2>Matched base comparisons</h2>{table(base)}
    <h2>Primary cost and execution delay</h2>{table(primary)}
    <details><summary>All 136 scenarios</summary>{table(rows)}</details>
    <h2>Full-pool net P&amp;L attribution — primary, $1 million initial capital</h2>
    <p>Every pool member is included, plus the zero-position benchmark. Attribution reconciles to NAV within
    ${attribution['reconciliation_error']:.8f}. Fees are already deducted from net P&amp;L.</p>
    <details><summary>53 attribution rows</summary><table class="study-table"><tr><th>ETF</th><th>Net P&amp;L USD</th><th>Fees USD</th></tr>{attr_rows}</table></details>
    <p>Independent native Windows LEAN: {len(native)} cases, maximum NAV deviation
    ${max(r['max_nav_difference'] for r in native):.2f}. These validate portfolio accounting, not signal quality.</p>
    <p>The standard report below contains the primary's NAV, benchmarks, full decision flow, trades, historical target and held weights.
    No forward signals, live authority or prospective observations are claimed.</p></section>"""
    rendered = rendered.replace("<body>", "<body>" + section, 1)
    checks = dict(held_value=abs(sum(r["value_cnh"] for r in current["holdings"]) - current["nav_cnh"]) < .011,
        weights=abs(sum(r["weight"] for r in current["holdings"]) - 1) < 1e-10,
        currency="Value USD" in rendered, native=len(native) == 3,
        full_pool=len(definition.universe_members) == 52, scenarios=len(rows) == 136)
    node = shutil.which("node")
    if not node:
        raise ValueError("Node required to test shipped report renderer")
    subprocess.run([node, str(study.ROOT / "tests/fr25_report_checks.cjs")], input=json.dumps(dict(html=rendered, report=report)),
                   text=True, check=True, capture_output=True)
    checks["client_allocation_renderer"] = True
    if not all(checks.values()):
        raise ValueError(checks)
    (output / "index.html").write_text(rendered, encoding="utf-8")
    study.write(work / "report.json", report)
    study.write(output / "validation.json", dict(passed=True, checks=checks, runtime_publication_verified=False,
        native_validation_script_sha256=study.digest(study.ROOT / "scripts/validate_breakout_revisit.py"),
        report_builder_sha256=study.digest(study.ROOT / "scripts/build_breakout_revisit_report.py")))
    study.write(output / "manifest.json", {p.name: study.digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != "manifest.json"})
    print(output / "index.html")


if __name__ == "__main__":
    main()
