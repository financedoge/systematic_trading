"""Focused tests for the app-tracked FR25 conditional candidate."""
import json
from pathlib import Path

import numpy as np
import pytest

from systematic_trading.research import fr25_lifecycle_conditional as candidate
from systematic_trading.research import fr25_lifecycle_monitoring as monitoring
from systematic_trading.research.strategy_catalog import registered_strategy_definition


def test_definition_is_registered_as_candidate():
    definition = registered_strategy_definition(candidate.KEY)
    assert definition.key == "fr25_lifecycle_conditional_v1"
    assert definition.state == "candidate"
    assert definition.scheduler == "dynamic_monthly"
    assert len(definition.universe_members) == 52
    assert any(overlay.kind == "lifecycle_conditional_sleeve" for overlay in definition.overlays)


def test_frozen_parameters_cover_pool_and_condition():
    params = json.loads(candidate.PARAMETERS_PATH.read_text(encoding="utf-8"))
    assert len(params["sleeve"]["short_parameters"]) == 52
    assert len(params["condition"]["breadth_by_session"]) == 2043
    assert params["condition"]["threshold"] == 36.0
    assert params["blend"] == {"fr25_weight": 0.8, "sleeve_weight": 0.2, "budget": 0.98}


def panel_fixture(symbols=("A", "BIL")):
    days = np.array(["2022-12-29", "2022-12-30", "2023-01-03", "2023-01-04", "2023-01-05"])
    prices = np.full((len(days), len(symbols)), 100.)
    fr25 = np.zeros_like(prices)
    fr25[1, 0] = .45  # deliberately cash-heavy core
    return dict(days=days, symbols=np.array(symbols), close=prices, open=prices.copy(),
                fr25=fr25, urth_close=np.full(len(days), 100.), urth_open=np.full(len(days), 100.))


def params_fixture(panel):
    return dict(condition=dict(threshold=1, breadth_by_session=[1] * len(panel["days"])))


def recipe_fixture(panel):
    return dict(universeMembers=[dict(symbol=s, name=s, asset_class="etf", exchange="NYSE",
                                     quote_currency="USD", country="US")
                                 for s in [*panel["symbols"], "URTH"]])


def test_trigger_includes_cash_and_compares_last_adopted_target():
    # A six percentage-point sell is a 12% L1 change after including cash.
    assert candidate.target_distance(np.array([.44]), np.array([.50])) == pytest.approx(.12)
    assert candidate.target_distance(np.array([.48]), np.array([.50])) == pytest.approx(.04)
    panel = panel_fixture()
    active = np.zeros_like(panel["close"], bool)
    active[2, 0] = True
    targets, indices, _ = candidate.build_targets(panel, active, np.zeros_like(active, float),
                                                  params=params_fixture(panel))
    assert list(indices) == [1, 2, 3]
    assert targets[1, 0] == pytest.approx(.8 * .45)  # do not refill core cash
    assert targets[1, 1] == pytest.approx(.2 * .98)  # empty sleeve parks in BIL
    assert targets[2, 0] == pytest.approx(.45)  # final name cap, excess remains cash
    assert targets[3, 1] == pytest.approx(.2 * .98)


def test_rule_a_ranks_new_entries_and_does_not_backfill_initial_holdings():
    panel = panel_fixture(tuple("ABCDEFG") + ("BIL",))
    active = np.zeros_like(panel["close"], bool)
    active[1, 0] = True  # prior-window entry must not seed the account
    active[2:, :7] = True
    score = np.broadcast_to(np.arange(8), active.shape).astype(float)
    targets, _, _ = candidate.build_targets(panel, active, score, params=params_fixture(panel))
    assert targets[1, 7] == pytest.approx(.196)
    assert targets[2, 0] == pytest.approx(.36)  # A was already active; no new entry
    assert all(targets[2, j] > 0 for j in range(1, 7))
    # When all seven enter simultaneously, rank G through B instead of alphabetically.
    active[1, 0] = False
    targets, _, _ = candidate.build_targets(panel, active, score, params=params_fixture(panel))
    assert targets[2, 0] == pytest.approx(.36)
    assert targets[2, 6] > 0


def test_monthly_control_and_future_changes_do_not_change_past_targets():
    panel = panel_fixture()
    active = np.zeros_like(panel["close"], bool)
    active[2:, 0] = True
    scores = np.zeros_like(active, float)
    params = params_fixture(panel)
    _, indices, _ = candidate.build_targets(panel, active, scores, params=params, clock="monthly")
    assert list(indices) == [1]
    first = candidate.build_targets(panel, active, scores, params=params)[0]
    active[-1] = False
    panel["fr25"][-1] = .1
    later = candidate.build_targets(panel, active, scores, params=params)[0]
    np.testing.assert_array_equal(first[:-1], later[:-1])


@pytest.mark.parametrize("delay", [0, 1])
def test_actual_fills_cash_and_decision_close_sizing(delay):
    panel = panel_fixture()
    panel["close"][2:, 0] = [200., 250., 300.]
    replay = candidate._Replay(panel, recipe_fixture(panel), candidate.OOS_START)
    weights = np.zeros((5, 3))
    weights[1, 0] = .5
    result, fills = replay.run_result(weights, np.array([1]), 5, delay)
    payload = candidate.report_payload(replay, result, fills)
    position = result.final_snapshot.positions[0]
    assert position.quantity == 5000  # even with delay, size at Dec 30's $100
    assert float(position.market_price) == 300
    assert float(result.nav_series[-1].cash_cnh) == 499750
    assert float(result.nav_series[-1].nav_cnh) == 1999750
    assert payload["nav_series"][0]["nav_cnh"] == "1000000"
    assert payload["proposals"][0]["as_of"] == "2022-12-30"
    assert payload["proposals"][0]["orders"][0]["quantity"] == 5000
    assert str(fills[0]["date"]) == str(panel["days"][2 + delay])
    calculation = dict(payload, latest_targets=[dict(symbol="A", target_weight=".4")])
    allocation = monitoring.current_allocation(calculation)
    assert allocation["holdings"][0]["quantity"] == 5000
    assert sum(r["value_cnh"] for r in allocation["holdings"]) == pytest.approx(allocation["nav_cnh"])
    assert sum(r["weight"] for r in allocation["holdings"]) == pytest.approx(1)
    assert sum(r["target_weight"] for r in allocation["holdings"]) == pytest.approx(1)
    assert allocation["holdings"][0]["weight"] != allocation["holdings"][0]["target_weight"]


def test_cash_only_decision_and_missing_score_fail_closed():
    panel = panel_fixture()
    replay = candidate._Replay(panel, recipe_fixture(panel), candidate.OOS_START)
    result, fills = replay.run_result(np.zeros((5, 3)), np.array([1]), 5, 0)
    assert not fills and not result.final_snapshot.positions
    assert all(row.cash_cnh == row.nav_cnh for row in result.nav_series)
    with pytest.raises(ValueError, match="ranking scores"):
        candidate.build_targets(panel, np.zeros_like(panel["close"], bool), params=params_fixture(panel))


def test_changed_derived_input_rejected_before_using_publication(tmp_path, monkeypatch):
    import hashlib
    path = tmp_path / "panel.bin"
    path.write_bytes(b"original")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(dict(files={"panel.bin": hashlib.sha256(b"original").hexdigest()})))
    monkeypatch.setattr(candidate, "ROOT", tmp_path)
    monkeypatch.setattr(candidate, "MANIFEST_PATH", manifest)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="input changed"):
        candidate.verified_input_provenance()


def test_parameters_and_manifest_are_in_runtime_revision():
    from systematic_trading.research.tracked_runtime import calculation_code_hashes
    names = {Path(n).as_posix() for n in calculation_code_hashes()}
    assert "research/fr25_lifecycle_inputs.json" in names
    assert "research/fr25_lifecycle_conditional_parameters.json" in names


def test_monitoring_report_declares_currency_and_full_allocation(tmp_path, monkeypatch):
    panel = panel_fixture()
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(json.dumps(recipe_fixture(panel)))
    replay = candidate._Replay(panel, recipe_fixture(panel), candidate.OOS_START)
    result, fills = replay.run_result(np.column_stack([panel["fr25"], np.zeros(5)]), np.array([1]), 5, 0)
    calculation = dict(candidate.report_payload(replay, result, fills),
                       latest_targets=[dict(symbol="A", target_weight=".45")],
                       input_provenance=dict(limitations=["Frozen test panel"]))
    monkeypatch.setattr(candidate, "calculate_tracked", lambda **kw: calculation)
    monkeypatch.setattr(candidate, "_load_panel", lambda: panel)
    monkeypatch.setattr(candidate, "RECIPE_PATH", recipe_path)
    config = dict(method="test", notes="", calculation=dict(transaction_cost_bps="5"))
    docs, observations, _ = monitoring.calculate_monitored(
        None, None, config, [candidate.definition()], candidate.definition(), tmp_path, {})
    detail, report = [json.loads(d["payload"]) for d in docs]
    assert detail["accounting_currency"] == report["accountingCurrency"] == "USD"
    assert report["monitoring"]["prospectiveObservations"] == 0
    assert report["currentAllocation"]["country_exposure_cnh"]
    assert report["decisionDiagrams"] and detail["allocation"]
    assert observations[-1]["family"] == "tracked_strategy_allocation"
    from systematic_trading.backtest.reporting import render_backtest_report_html
    html = render_backtest_report_html(report)
    assert "__ACCOUNTING_CURRENCY__" not in html
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is not None:
        checked = subprocess.run([node, str(Path(__file__).with_name("fr25_report_checks.cjs"))],
                                 input=json.dumps(dict(report=report, html=html)),
                                 text=True, encoding="utf-8", capture_output=True, timeout=20)
        assert checked.returncode == 0, checked.stderr
