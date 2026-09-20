import json
import shutil
import subprocess
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain.pnl import PnLBaseline
from systematic_trading.live.pnl import build_pnl_baseline
from systematic_trading.research import current_sota_definition
from systematic_trading.web.operator import _OPERATOR_HTML


@pytest.fixture
def dashboard(tmp_path):
    app = create_app(AppSettings(database_path=tmp_path / "dashboard.db", data_dir=tmp_path, automation_enabled=False))
    with TestClient(app) as client:
        yield client, app.state.store, tmp_path


def snapshot(root, name, day="2026-07-14", captured="2026-07-14T16:00:00Z", cash="100", positions=None):
    path = root / "live" / "account_snapshots" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"as_of": day, "captured_at": captured,
        "cash": [{"currency": "CNH", "amount": cash}], "positions": positions or []}), encoding="utf-8")
    return path


def performance(client):
    response = client.get("/api/v1/dashboard/performance")
    assert response.status_code == 200
    return response.json()


def test_reset_filters_by_capture_time_and_preserves_boundary_after_collapse(dashboard):
    client, store, root = dashboard
    snapshot(root, "before.json", captured="2026-07-14T15:00:00Z", cash="9999")
    snapshot(root, "future_asof_before_capture.json", day="2026-07-15", captured="2026-07-14T15:00:00Z", cash="8888")
    reset = snapshot(root, "reset.json", cash="100")
    snapshot(root, "a_later.json", captured="2026-07-14T18:00:00Z", cash="120")
    snapshot(root, "z_earlier.json", captured="2026-07-14T17:00:00Z", cash="110")
    before = {p: p.read_bytes() for p in reset.parent.glob("*.json")}
    baseline = PnLBaseline(cutoff_at=datetime(2026, 7, 14, 16, tzinfo=UTC),
        source="ib_broker_authoritative_reset", account_reset_at=datetime(2026, 7, 14, 16, tzinfo=UTC),
        account_snapshot_path=str(reset))
    store.save_pnl_baseline(baseline)
    collapsed = build_pnl_baseline(store, cutoff_date=date(2026, 7, 15))
    store.save_pnl_baseline(collapsed)
    payload = performance(client)
    assert collapsed.account_reset_at == baseline.account_reset_at
    assert collapsed.account_snapshot_path == str(reset)
    assert [(p["trade_date"], p["nav_cnh"]) for p in payload["account"]] == [("2026-07-14", "120.00")]
    assert payload["account_alignment_date"] is None
    assert all(path.read_bytes() == data for path, data in before.items())


def test_latest_holdings_prefers_capture_timestamp_over_filename(dashboard):
    client, _, root = dashboard
    snapshot(root, "a_later.json", captured="2026-07-14T18:00:00Z", cash="120")
    snapshot(root, "z_earlier.json", captured="2026-07-14T17:00:00Z", cash="110")
    assert client.get("/api/v1/dashboard/holdings").json()["account_nav_cnh"] == "120.00"


def test_legacy_reset_report_and_bad_timestamps_do_not_break_history(dashboard):
    client, store, root = dashboard
    reset = snapshot(root, "reset.json", captured=None, cash="100")
    snapshot(root, "ib_paper_account_snapshot_20261340_259999.json", captured=None, cash="999")
    baseline = PnLBaseline(cutoff_at=datetime(2026, 7, 14, 16), source="ib_broker_authoritative_reset")
    store.save_pnl_baseline(baseline)
    reports = root / "reconciliation"
    reports.mkdir()
    (reports / "ib_paper_reconciliation_20260714_160000_0.json").write_text(json.dumps({"reset_applied": True, "checked_at": "invalid"}))
    (reports / "ib_paper_reconciliation_20260714_160000_1.json").write_text(json.dumps({
        "reset_applied": True, "checked_at": "2026-07-14T16:00:00Z",
        "pnl_reset_baseline_id": baseline.baseline_id, "account_snapshot_path": str(reset)}))
    payload = performance(client)
    assert payload["account_reset_at"] == "2026-07-14T16:00:00Z"
    assert [point["nav_cnh"] for point in payload["account"]] == ["100.00"]
    assert any("invalid checked_at" in warning for warning in payload["warnings"])


def test_alignment_starts_with_positions_and_values_non_sota_currency(dashboard):
    client, _, root = dashboard
    strategy = root / "backtests" / "sota_current" / f"{current_sota_definition().key}.json"
    strategy.parent.mkdir(parents=True)
    strategy.write_text(json.dumps({"nav_series": [
        {"trade_date": "2026-07-13", "nav_cnh": "1000"},
        {"trade_date": "2026-07-14", "nav_cnh": "1100"}]}))
    snapshot(root, "cash.json", day="2026-07-13", captured="2026-07-13T16:00:00Z")
    snapshot(root, "invested.json", positions=[{"symbol": "OUTSIDE", "quantity": 2,
        "average_cost": "50", "currency": "HKD"}])
    client.put("/api/v1/market-data/fx-rates", json={"rate_date": "2026-07-14", "base_currency": "HKD", "quote_currency": "CNH", "rate": "0.9"})
    payload = performance(client)
    assert payload["account_tracking_start_date"] == payload["account_alignment_date"] == "2026-07-14"
    assert Decimal(payload["account_alignment_nav_cnh"]) == Decimal("190")
    assert Decimal(payload["account_alignment_strategy_index"]) == Decimal("110")
    assert any("average cost" in warning for warning in payload["warnings"])


def test_unpriced_position_does_not_turn_into_a_cash_only_nav(dashboard):
    client, _, root = dashboard
    snapshot(root, "missing_price.json", positions=[{"symbol": "OUTSIDE", "quantity": 2, "currency": "CNH"}])
    payload = performance(client)
    assert payload["account"] == []
    assert payload["account_alignment_date"] is None
    assert any("position was not valued" in warning for warning in payload["warnings"])


def test_strategy_history_skips_invalid_nav_and_deduplicates_dates(dashboard):
    client, _, root = dashboard
    strategy = root / "backtests" / "sota_current" / f"{current_sota_definition().key}.json"
    strategy.parent.mkdir(parents=True)
    strategy.write_text(json.dumps({"nav_series": [
        {"trade_date": "2026-07-14", "nav_cnh": value}
        for value in ["bad", "NaN", "Infinity", "100", "120"]]}))
    assert [p["nav_cnh"] for p in performance(client)["strategy"]] == ["120.00"]


def test_missing_sessions_and_partial_marks_are_disclosed_without_rewriting_artifact(dashboard):
    client, _, root = dashboard
    strategy = root / "backtests" / "sota_current" / f"{current_sota_definition().key}.json"
    strategy.parent.mkdir(parents=True)
    strategy.write_text(json.dumps({
        "nav_series": [{"trade_date": "2026-07-10", "nav_cnh": "200"}],
        "final_snapshot": {"as_of": "2026-07-10", "cash": [], "nav_cnh": "200",
            "gross_exposure_cnh": "200", "country_exposure_cnh": {}, "currency_exposure_cnh": {},
            "positions": [{"symbol": symbol, "quantity": 1, "average_cost": "100", "market_price": "100",
                "currency": "CNH", "country": "US"} for symbol in ["SPY", "TLT"]]}}))
    original = strategy.read_bytes()
    for symbol, day, price in [("SPY", "2026-07-13", "110"), ("SPY", "2026-07-15", "115"), ("TLT", "2026-07-15", "120")]:
        response = client.put(f"/api/v1/market-data/bars/{symbol}", json={"trade_date": day,
            "open": price, "high": price, "low": price, "close": price, "volume": 100})
        assert response.status_code == 200
    payload = performance(client)
    assert [p["nav_cnh"] for p in payload["strategy"]] == ["200.00", "210.00", "235.00"]
    assert any("missing 1 US session(s): 2026-07-14" in warning for warning in payload["warnings"])
    assert any("carried forward" in warning and "2026-07-13" in warning for warning in payload["warnings"])
    assert strategy.read_bytes() == original


def test_performance_javascript_behavior():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the operator JavaScript regression checks")
    script = _OPERATOR_HTML.split("<script>", 1)[1].split("</script>", 1)[0]
    result = subprocess.run([node, str(Path(__file__).with_name("operator_performance_checks.cjs"))],
        input=script, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
