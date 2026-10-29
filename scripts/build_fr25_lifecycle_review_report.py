"""Add the frozen correction retest to the shared full strategy report."""
from hashlib import sha256
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "research/fr25-lifecycle-review-20261020-v1"
VALIDATED = ROOT / "var/research/fr25-lifecycle-review-20261020-v1/validated"


def main():
    validation = json.loads((VALIDATED / "validation.json").read_text(encoding="utf-8"))
    if not validation["passed"]:
        raise ValueError("Validate the corrected app calculation before rendering")
    evidence = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    rows = evidence["results"]
    selected = [r for r in rows if r["scenario"] in {
        "FR25", "conditional_dynamic_0.10", "conditional_monthly"}]
    table = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{:.2%}</td><td>{:.3f}</td>"
        "<td>{:.3f}</td><td>{:.2%}</td><td>{:.3f}</td><td>{:.2f}</td><td>{:.2f}</td></tr>".format(
            html.escape(r["scenario"]), r["cost_bp"], r["delay"], r["cagr"], r["sharpe"],
            r["sortino"], r["max_drawdown"], r["calmar"], r["annual_turnover"], r["annual_cost_bps"])
        for r in selected)
    native = json.loads((OUTPUT / "native-checks.json").read_text(encoding="utf-8"))
    section = f"""
    <section style="margin:20px;padding:24px;border:2px solid #ba573d;background:#fffaf6;color:#172b43">
      <h1>October 20 correction review — do not promote</h1>
      <p>The fixed 10% dynamic candidate passes 2 of 6 matched friction gates.
      All three added-session-delay tests fail. At 20 bp without extra delay,
      corrected Sortino is below FR25. Two of three random-condition controls
      beat the candidate's base Sharpe when the clock and threshold are matched.</p>
      <p>This is a historical USD replay through October 12, 2026. The first fill
      and cost are included using the initial cash anchor. It is an inspected
      development retest, not prospective evidence. Monitoring membership,
      funding and execution authority are unchanged. Current signal extension is
      not implemented; new prices alone cannot extend this report.</p>
      <p>Independent native LEAN checks: {len(native)} passed, maximum NAV
      difference {max(r['max_nav_difference'] for r in native):.2f} USD.
      The daily open remains a proxy for TWAP; the retest does not establish actual
      intraday execution-clock performance.</p>
      <div style="overflow:auto"><table style="width:100%;text-align:right">
      <thead><tr><th>Scenario</th><th>bp/side</th><th>Extra sessions</th><th>CAGR</th>
      <th>Sharpe</th><th>Sortino</th><th>Max DD</th><th>Calmar</th><th>Turnover/year</th>
      <th>Cost bp/year</th></tr></thead><tbody>{table}</tbody></table></div>
      <p>The full standard report below covers the 5 bp, next-open primary candidate.
      Internal money-field names are legacy; all displayed monetary values are USD.</p>
    </section>"""
    rendered = (VALIDATED / "strategy-report.html").read_text(encoding="utf-8")
    if "<body>" not in rendered:
        raise ValueError("Shared report body not found")
    (OUTPUT / "index.html").write_text(rendered.replace("<body>", "<body>" + section, 1), encoding="utf-8")
    (OUTPUT / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    manifest = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(OUTPUT.iterdir())
                if p.is_file() and p.name != "manifest.json"}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Full report:", OUTPUT / "index.html")


if __name__ == "__main__":
    main()
