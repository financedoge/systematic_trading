"""Recalculate the corrected candidate and validate its offline report contract.

Never equate similarity to an old research page with verification of a running
app publication. This command neither publishes analytics nor touches a broker.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.research import fr25_lifecycle_conditional as candidate  # noqa: E402
from systematic_trading.research.fr25_lifecycle_monitoring import calculate_monitored  # noqa: E402
from systematic_trading.research.strategy_catalog import fr25_definition  # noqa: E402
from systematic_trading.backtest.reporting import render_backtest_report_html  # noqa: E402


def main():
    work = ROOT / "var/research/fr25-lifecycle-review-20261020-v1"
    expected = json.loads((work / "primary-calculation.json").read_text(encoding="utf-8"))
    actual = candidate.calculate_tracked()
    output = work / "validated"
    output.mkdir(exist_ok=True)
    config = json.loads((ROOT / "config/strategy-monitoring.json").read_text(encoding="utf-8"))
    documents, observations, _ = calculate_monitored(
        None, None, config, [candidate.definition()], fr25_definition(), output, {})
    detail, report = [json.loads(row["payload"]) for row in documents]
    allocation = report["currentAllocation"]
    actual_targets = {r["symbol"]: float(r["target_weight"]) for r in actual["latest_targets"]}
    expected_targets = {r["symbol"]: float(r["target_weight"]) for r in expected["latest_targets"]}
    checks = dict(
        exact_nav=actual["nav_series"] == expected["nav_series"],
        exact_filled_positions=actual["final_snapshot"] == expected["final_snapshot"],
        targets_within_1e_minus_12=(actual_targets.keys() == expected_targets.keys()
                            and all(abs(w-expected_targets[s]) <= 1e-12 for s, w in actual_targets.items())),
        provenance=actual["input_provenance"] == expected["input_provenance"],
        currency=detail["accounting_currency"] == report["accountingCurrency"] == "USD",
        held_value_reconciles=abs(sum(r["value_cnh"] for r in allocation["holdings"]) - allocation["nav_cnh"]) < .011,
        weights_reconcile=abs(sum(r["weight"] for r in allocation["holdings"]) - 1) < 1e-10,
        targets_include_cash=abs(sum(r["target_weight"] for r in allocation["holdings"]) - 1) < 1e-10,
        allocation_in_output=observations[-1]["family"] == "tracked_strategy_allocation",
        frozen_boundary_disclosed=report["monitoring"]["currentSignalAvailable"] is False,
        future_not_claimed=report["monitoring"]["prospectiveObservations"] == 0,
    )
    html = render_backtest_report_html(report)
    checks["rendered_currency"] = "__ACCOUNTING_CURRENCY__" not in html and "Value USD" in html
    (output / "strategy-report.html").write_text(html, encoding="utf-8")
    for name, payload in (("detail.json", detail), ("report.json", report)):
        (output / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    validation = dict(identity=candidate.KEY, implementation=candidate.VERSION,
                      passed=all(checks.values()), checks=checks, runtime_publication_verified=False,
                      note="Offline historical USD report. Running app publication and current-signal extension remain separate, unverified gates.")
    (output / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    if not validation["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
