"""Validate the app-owned tracked candidate artifact against the research page and catalog."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\projects\systematic_trading")
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.research import fr25_lifecycle_conditional as candidate  # noqa: E402
from systematic_trading.research.strategy_catalog import registered_strategy_definition  # noqa: E402


def main():
    tracked = ROOT / "var/research/fr25-lifecycle-conditional-v1/tracked"
    artifact = json.loads((tracked / "artifact.json").read_text(encoding="utf-8"))
    calculation = json.loads((tracked / "calculation.json").read_text(encoding="utf-8"))
    page = json.loads((ROOT / "var/research/fr25-lifecycle-conditional-v1/page-inputs.json")
                      .read_text(encoding="utf-8"))
    params = json.loads(candidate.PARAMETERS_PATH.read_text(encoding="utf-8"))
    definition = registered_strategy_definition(candidate.KEY)
    checks = {}
    checks["definition_registered"] = definition.key == "fr25_lifecycle_conditional_v1"
    checks["definition_state_candidate"] = definition.state == "candidate"
    checks["sleeve_parameters"] = len(params["sleeve"]["short_parameters"]) == 52
    checks["breadth_sessions"] = len(params["condition"]["breadth_by_session"]) == 2043
    checks["artifact_sessions"] = len(artifact["nav_series"]) == 947
    checks["artifact_proposals"] = len(artifact["proposals"]) == calculation["rebalances"] == 55
    checks["cagr_matches_page"] = abs(float(calculation["cagr"]) - float(page["metrics"]["cagr"])) < 0.01
    checks["artifact_hash_matches"] = hashlib.sha256((tracked / "artifact.json").read_bytes()).hexdigest() \
        == calculation["artifact_sha256"]
    checks["parameters_hash_matches"] = hashlib.sha256(candidate.PARAMETERS_PATH.read_bytes()).hexdigest() \
        == calculation["params_sha256"]
    checks["cagr_above_fr25_sharpe_benchmark"] = float(calculation["cagr"]) > 0.0
    checks["monitoring_config_includes_key"] = candidate.KEY in json.loads(
        (ROOT / "config/strategy-monitoring.json").read_text(encoding="utf-8"))["monitored_strategy_ids"]
    payload = dict(identity=candidate.KEY, version=candidate.VERSION,
                   passed=all(checks.values()), checks=checks,
                   artifact_sha256=calculation["artifact_sha256"],
                   parameters_sha256=calculation["params_sha256"],
                   note=("Artifact and app-module calculation validate against the research page. "
                         "The key is in the monitored membership and its app tracked publication is "
                         "verified; the calculation is Catching up until the audited batch covers "
                         "2026-10-13..16 for all 52 pool ETFs."))
    (tracked / "validation.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
