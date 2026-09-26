from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import BacktestRunSpec, sha256
from systematic_trading.lean.fixtures import make_fixture_bundle
from systematic_trading.lean.reference import run_reference
from systematic_trading.lean.runner import compare_outputs, run_python_bundle
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research.flow_concentration import FlowConcentrationSpec
from systematic_trading.research.strategy_catalog import (
    etf_activity_lag20_definition, registered_strategy_definition, current_sota_definition,
)
from systematic_trading.research.strategy_diagram import decision_diagrams
from systematic_trading.research.tracked_inputs import validated_fx_observations
from systematic_trading.research.tracked_runtime import report_result, latest_allocation, buy_hold_benchmark


@pytest.fixture(scope="module")
def fixture_bundle(tmp_path_factory):
    path = tmp_path_factory.mktemp("tracked") / "bundle"
    make_fixture_bundle(path, mode="shared")
    return path


def test_registered_lag20_matches_previously_tested_overlay_and_ignores_future(fixture_bundle):
    bars = json.loads((fixture_bundle / "bars.json").read_text())
    day = date(2024, 11, 1)
    expected = targets_for_day(bars, day, flow_overlay=FlowConcentrationSpec(difference_lag=20))
    definition = etf_activity_lag20_definition()
    actual = targets_for_day(bars, day, definition=definition)
    assert [t.target_weight for t in actual] == [t.target_weight for t in expected]
    clean = {s: [r for r in rows if r['trade_date'] < str(day)] for s, rows in bars.items()}
    assert targets_for_day(clean, day, definition=definition) == actual
    assert definition.state == "tracked" and current_sota_definition().state == "sota"
    with pytest.raises(ValueError, match="executable definition"):
        registered_strategy_definition("unimplemented")


def test_deployed_tree_not_applied_before_declared_boundary(fixture_bundle, monkeypatch):
    from systematic_trading.research import chronological_tree
    bars = json.loads((fixture_bundle / "bars.json").read_text())
    def invalid(*args):
        raise ValueError("Missing causal model")
    monkeypatch.setattr(chronological_tree, "select_base_tree", invalid)
    with pytest.raises(ValueError, match="Missing causal model"):
        targets_for_day(bars, date(2024, 11, 1), base_tree_models={}, fixed_model_from="2025-01-01")
    assert targets_for_day(bars, date(2025, 1, 2), base_tree_models={}, fixed_model_from="2025-01-01")
    with pytest.raises(ValueError, match="cannot precede 2023"):
        BacktestRunSpec(start_date="2016-01-04", end_date="2026-09-25", warmup_start="2012-01-05",
            source_hash="a", strategy_hash="b", repository_commit="c", fixed_model_from="2016-01-01", base_tree_model_schedule=True)


def test_python_engine_runs_frozen_definition_without_native_claim(fixture_bundle, tmp_path):
    spec = json.loads((fixture_bundle / "spec.json").read_text())
    for k in ("source_hash", "strategy_hash", "repository_commit"):
        spec.pop(k)
    spec.update(strategy="registered", strategy_definition=etf_activity_lag20_definition().to_dict())
    bundle = freeze_bundle(root=tmp_path / "registered", bars=json.loads((fixture_bundle/"bars.json").read_text()),
        fx=json.loads((fixture_bundle/"fx.json").read_text()), provenance={"source":"fixture"}, spec_values=spec)
    receipt = run_python_bundle(bundle=bundle, output=tmp_path/"run")
    assert receipt["engine"] == "python" and "no native LEAN parity" in receipt["validation"]
    actual = json.loads((tmp_path/"run/economic.json").read_text())
    assert compare_outputs(run_reference(bundle), actual, BacktestRunSpec.model_validate_json((bundle/"spec.json").read_text()))["passed"]
    assert receipt["manifest_sha256"] == sha256(bundle/"manifest.json")


def test_held_quantities_and_latest_targets_are_separate(fixture_bundle):
    economic = run_reference(fixture_bundle)
    bars = json.loads((fixture_bundle/"bars.json").read_text())
    quotes = json.loads((fixture_bundle/"quotes.json").read_text())
    inputs = dict(latest_bars=bars, provenance=dict(price_through="2025-01-15"))
    result = latest_allocation(current_sota_definition(), inputs, economic, quotes)
    assert result["target_known_through"] == "2025-01-15"
    assert result["next_rebalance"] == "2025-02-03"
    assert sum(r["value_cnh"] for r in result["holdings"]) == pytest.approx(result["nav_cnh"], abs=.01)
    assert sum(r["weight"] for r in result["holdings"]) == pytest.approx(1)
    assert sum(r["target_weight"] for r in result["holdings"]) == pytest.approx(1)
    normalized = report_result(economic, quotes, "1000000", "2024-10-30")
    assert normalized["nav_series"][0]["cash_cnh"] == "1000000"
    assert len(normalized["proposals"]) == len(economic["decisions"])


def test_fx_requires_real_matching_completed_cnh_leg(tmp_path):
    row = dict(trade_date="2026-09-25", open="6.7", high="6.8", low="6.6", close="6.72", volume=0)
    payload = dict(source="interactive-brokers", data_type="MIDPOINT", pair="USD/CNH",
        observed_at="2026-09-25T21:01:00+00:00", legs={"USD/CNH":[row]}, rates=[row])
    path = tmp_path/"fx.json";path.write_text(json.dumps(payload))
    result, _ = validated_fx_observations([path])
    assert result["2026-09-25"]["rate"] == "6.72"
    payload["observed_at"] = "2026-09-25T20:59:59+00:00";path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="precedes"):
        validated_fx_observations([path])
    payload["observed_at"] = "2026-09-25T21:01:00+00:00"
    payload["rates"] = [dict(row, close="6.73")];path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="differs"):
        validated_fx_observations([path])


def test_urth_requires_complete_prices_and_charges_matching_fees():
    rows = [dict(trade_date=d, open="100", close="100") for d in ("2026-09-24","2026-09-25")]
    nav = buy_hold_benchmark(rows, {"2026-09-24":"7","2026-09-25":"7"}, ["2026-09-25"], "1000000", "2026-09-24", "5")
    assert nav[1]["nav_cnh"] < nav[0]["nav_cnh"]
    with pytest.raises(ValueError, match="missing audited"):
        buy_hold_benchmark(rows[:1], {}, ["2026-09-25"], "1000000", "2026-09-24", "5")


def test_full_chart_has_pipeline_and_actual_frozen_tree():
    charts = decision_diagrams(etf_activity_lag20_definition())
    text = " ".join(d["svg"] for d in charts)
    assert "Inverse-volatility" in text and "second difference, lag 20" in text
    assert "Leaf forecast" in text and "fallback" in text and "URTH" in text


def test_refresh_endpoint_only_queues_app_calculation():
    from systematic_trading.web.api import refresh_strategy_calculations
    service = SimpleNamespace(request_refresh=lambda: {"queued":True,"owner":"application"})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(analytics_service=service)))
    assert refresh_strategy_calculations(request) == {"queued":True,"owner":"application"}


def test_source_changes_require_restart_before_calculation(monkeypatch):
    from systematic_trading.research import tracked_runtime
    monkeypatch.setattr(tracked_runtime, "_LOADED_CODE_HASHES", {})
    with pytest.raises(ValueError, match="restart the application"):
        tracked_runtime.calculation_revision({}, {}, [])
