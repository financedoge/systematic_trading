from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from scripts.analyze_execution_timing import analyze, encoded, file_hash, run
from systematic_trading.domain.execution import BrokerOrderRecord, OrderRequest, BrokerExecutionFill
from systematic_trading.execution.twap_benchmark import benchmark_window


START = datetime(2026, 10, 1, 13, 30, tzinfo=UTC)


def record(identity="a", *, price="101", quantity=10, side="buy", symbol="SPY"):
    order = OrderRequest(symbol=symbol, side=side, order_type="twap", quantity=quantity,
                         reference_price="100", currency="USD", notional_cnh="7000", rationale="test",
                         intended_trade_date=START.date(), execution_start_time="09:30", execution_end_time="10:00")
    fill = BrokerExecutionFill(execution_id=identity, symbol=symbol, side=side, quantity=quantity,
                               average_price=price, filled_at=START, currency="USD", order_ref=identity,
                               broker_order_id=1, account="DU-TEST")
    return BrokerOrderRecord(local_order_id=identity, proposal_id=identity, order_index=0, order=order,
                             order_ref=identity, broker_order_id=1, status="filled", filled_quantity=quantity,
                             average_fill_price=price, execution_fills=[fill])


def benchmark(row, *, price="100"):
    start, end = benchmark_window(row, original_intent=True)
    key = sha256(f"v1:{row.order.symbol}:{start.isoformat()}:{end.isoformat()}".encode()).hexdigest()
    payload = dict(status="ready", symbol=row.order.symbol, window_start=start.isoformat(),
                   window_end=end.isoformat(), observed_at=end.isoformat(),
                   bars=[dict(at=(start + timedelta(minutes=i)).isoformat(), close=price) for i in range(30)])
    return document(key, payload)


def document(key, payload):
    value = json.dumps(payload)
    return dict(point_key=key, payload=value, payload_sha256=sha256(value.encode()).hexdigest())


def snapshot(records, documents=()):
    return dict(captured_at=(START + timedelta(days=10)).isoformat(),
                orders=[row.model_dump(mode="json") for row in records],
                benchmark_publication=dict(document_count=len(documents)), benchmark_documents=list(documents))


def test_empty_publication_reports_coverage_not_zero_cost():
    row = record()
    row.execution_fills = []
    result = analyze(snapshot([row]))
    assert result["status"] == "blocked_no_matched_style_evidence"
    assert result["evidence_issue_counts"] == {"missing_execution_details": 1}
    assert result["per_currency"][0]["slippage_bps"] is None
    assert result["twap_status_counts"] == {"no_published_benchmark": 1}


@pytest.mark.parametrize("side, expected", [("buy", "100"), ("sell", "-100")])
def test_signed_slippage_from_actual_execution_details(side, expected):
    row = record(side=side)
    result = analyze(snapshot([row], [benchmark(row)]))
    aggregate = result["per_currency"][0]
    assert Decimal(aggregate["slippage_bps"]) == Decimal(expected)
    assert aggregate["benchmark_ready_orders"] == 1
    assert aggregate["close_ready_orders"] == aggregate["vwap_ready_orders"] == 0


def test_aggregation_uses_gross_notional_and_original_intent():
    first = record("a", price="101", quantity=1)
    second = record("b", price="99", quantity=9)
    second.order.intended_trade_date += timedelta(days=1)
    second.order.slippage_trade_date = START.date()
    second.order.slippage_start_time = "09:30"
    second.order.slippage_end_time = "10:00"
    result = analyze(snapshot([first, second], [benchmark(first)]))
    assert Decimal(result["per_currency"][0]["slippage_bps"]) == Decimal("-80")
    assert result["orders"][1]["original_window"] != result["orders"][1]["routed_window"]


@pytest.mark.parametrize("defect", ["missing_bar", "wrong_symbol", "future_observation", "naive_observation"])
def test_invalid_benchmark_withholds_cost(defect):
    row = record()
    doc = benchmark(row)
    payload = json.loads(doc["payload"])
    if defect == "missing_bar":
        payload["bars"].pop(4)
    elif defect == "wrong_symbol":
        payload["symbol"] = "IWM"
    elif defect == "future_observation":
        payload["observed_at"] = (START + timedelta(days=20)).isoformat()
    else:
        payload["observed_at"] = "2026-10-01T14:00:00"
    result = analyze(snapshot([row], [document(doc["point_key"], payload)]))
    assert result["twap_status_counts"] == {"invalid_published_benchmark": 1}
    assert result["per_currency"][0]["slippage_bps"] is None


@pytest.mark.parametrize("defect", ["quantity", "average", "duplicate_id", "identity"])
def test_inconsistent_execution_evidence_withholds_cost(defect):
    row = record()
    if defect == "quantity":
        row.filled_quantity = 11
    elif defect == "average":
        row.average_fill_price = Decimal("999")
    elif defect == "identity":
        row.execution_fills[0].symbol = "IWM"
    else:
        row.execution_fills.append(deepcopy(row.execution_fills[0]))
    result = analyze(snapshot([row], [benchmark(row)]))
    assert result["twap_status_counts"] == {"withheld_execution_evidence": 1}
    assert result["per_currency"][0]["slippage_bps"] is None


def test_published_payload_hash_checked_before_analysis():
    row = record()
    doc = benchmark(row)
    doc["payload"] += " "
    with pytest.raises(ValueError, match="payload hash"):
        analyze(snapshot([row], [doc]))


def test_verification_is_read_only_and_rejects_tampering(tmp_path):
    frozen = tmp_path / "inputs.json"
    frozen.write_text(encoded(snapshot([record()])), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(encoded(dict(
        files={"inputs.json": file_hash(frozen)}, current_sources={})), encoding="utf-8")
    run(tmp_path)
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir()}
    run(tmp_path, verify=True)
    assert {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in tmp_path.iterdir()} == before
    with pytest.raises(FileExistsError):
        run(tmp_path)
    frozen.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        run(tmp_path, verify=True)
