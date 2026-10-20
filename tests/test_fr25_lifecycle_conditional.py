"""Focused tests for the app-tracked FR25 conditional candidate."""
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\projects\systematic_trading")
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.research import fr25_lifecycle_conditional as candidate  # noqa: E402
from systematic_trading.research.strategy_catalog import registered_strategy_definition  # noqa: E402


def test_definition_is_registered_as_candidate():
    definition = registered_strategy_definition(candidate.KEY)
    assert definition.key == "fr25_lifecycle_conditional_v1"
    assert definition.state == "candidate"
    assert definition.scheduler == "dynamic_monthly"
    assert any(overlay.kind == "lifecycle_conditional_sleeve" for overlay in definition.overlays)


def test_frozen_parameters_cover_pool_and_condition():
    params = json.loads(candidate.PARAMETERS_PATH.read_text(encoding="utf-8"))
    assert len(params["sleeve"]["short_parameters"]) == 52
    assert len(params["condition"]["breadth_by_session"]) == 2043
    assert params["condition"]["threshold"] == 36.0
    assert params["blend"] == {"fr25_weight": 0.8, "sleeve_weight": 0.2, "budget": 0.98}


def test_tracked_artifact_matches_research_page_cagr():
    artifact_path = ROOT / "var/research/fr25-lifecycle-conditional-v1/tracked/artifact.json"
    page_inputs = ROOT / "var/research/fr25-lifecycle-conditional-v1/page-inputs.json"
    if not artifact_path.exists() or not page_inputs.exists():
        return
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    page = json.loads(page_inputs.read_text(encoding="utf-8"))
    assert len(artifact["nav_series"]) == 947
    assert artifact["proposals"]
    assert abs(float(artifact["metrics"]["cagr"]) - float(page["metrics"]["cagr"])) < 0.01
