from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from scripts.analyze_execution_references import analyze, key_for, POLICY, ROOT, SOURCES
from systematic_trading.execution.benchmark_archive import capture
from systematic_trading.execution.benchmark_qualification import qualify
from systematic_trading.execution.twap_benchmark import benchmark_window, session_window
from systematic_trading.market_data.analytics_store import digest, encode
from test_execution_timing_review import record, document


def snapshot(tmp_path, rows):
    row = rows[0]
    start, end = session_window(row)
    root = tmp_path / "evidence"
    provider = SimpleNamespace(fetch=lambda symbol, a, b: dict(
        bars=[dict(at=(a + timedelta(minutes=i)).isoformat(), open="100", high="102", low="98",
                   close="100", wap="99", volume="100") for i in range(int((b-a).total_seconds()/60))],
        contract=dict(con_id=123, symbol=symbol, currency="USD", security_type="STK", primary_exchange="ARCA")))
    def collect(a, b):
        key = key_for(row.order.symbol, a, b)
        return key, capture(provider, root=root, key=key, path=root/(key+".json"), symbol=row.order.symbol, start=a, end=b)
    key, session = collect(start, end)
    daily = dict(row=dict(symbol="SPY", trade_date=str(start.date()), source_vintage="2026-10-11T12:00:00+00:00",
        raw_open=100, raw_high=102, raw_low=98, raw_close=100, split_multiplier=1,
        quality_flags=["historical_vintage_uncertified"]), actions=[])
    audit = dict(qualify(session, daily), session_key=key)
    policy = dict(POLICY, qualifier_source_sha256=digest((ROOT / SOURCES[4]).read_bytes()))
    docs = [document(key, audit), document("policy", policy)]
    hashes = {d["point_key"]: digest(d["payload"]) for d in docs}
    references = dict(documents=docs, publication=dict(version=digest(encode(hashes)), document_count=2,
        provenance=encode(dict(document_hashes=hashes))))
    window_key, candidate = collect(*benchmark_window(row))
    provenance = dict(files={}, extractor="test")
    windows = dict(documents=[document(window_key, candidate)], publication=dict(document_count=1,
        version=digest(encode(provenance)), provenance=encode(provenance)))
    return dict(captured_at=(datetime.now(UTC)+timedelta(seconds=1)).isoformat(),
        orders=[r.model_dump(mode="json") for r in rows], **{
            "execution-reference-audits": references, "execution-benchmarks": windows})


def test_matched_cohort_signs_gross_aggregation_and_no_style_inference(tmp_path):
    data = snapshot(tmp_path, [record("a", quantity=1, price="101"), record("b", quantity=9, price="99", side="sell")])
    result = analyze(data, tmp_path)
    assert result["matched"]["orders"] == 2
    assert result["same_date"]["orders"] == 2
    assert result["delayed_date"]["orders"] == 0
    style = result["matched"]["styles"]["original_twap"]
    assert Decimal(style["gross_reference_notional_usd"]) == 1000
    assert Decimal(style["price_cost_usd"]) == 10
    assert Decimal(style["signed_bps"]) == 100
    assert "Do not rank" in result["conclusion"]
    assert result["leave_one_session_out"]["2026-10-01"]["orders"] == 0


@pytest.mark.parametrize("defect,reason", [("fill", "missing_execution_details"),
    ("duplicate", "missing_or_duplicate_execution_id"), ("date", "outside the routed session"),
    ("reference", "no published qualified reference"), ("capture", "raw capture changed")])
def test_matched_cohort_fails_closed(tmp_path, defect, reason):
    first, second = record("a"), record("b")
    if defect == "fill":
        first.execution_fills = []
    if defect == "duplicate":
        second.execution_fills[0].execution_id = first.execution_fills[0].execution_id
    if defect == "date":
        first.execution_fills[0].filled_at += timedelta(days=1)
    data = snapshot(tmp_path, [first, second])
    if defect == "reference":
        item = data["execution-reference-audits"]
        item["documents"] = [d for d in item["documents"] if d["point_key"] == "policy"]
        hashes = {d["point_key"]: digest(d["payload"]) for d in item["documents"]}
        item["publication"].update(document_count=1, version=digest(encode(hashes)), provenance=encode(dict(document_hashes=hashes)))
    if defect == "capture":
        for path in (tmp_path / "evidence").rglob("*.response.json"):
            path.write_text("{}", encoding="utf-8")
    result = analyze(data, tmp_path)
    assert result["matched"]["orders"] < 2
    assert any(reason in issue for issue in result["exclusions"])


def test_publication_hash_must_match_even_if_document_is_valid_json(tmp_path):
    data = snapshot(tmp_path, [record()])
    changed = deepcopy(data)
    doc = changed["execution-reference-audits"]["documents"][0]
    payload = json.loads(doc["payload"])
    payload["reference_prices"]["close"] = "200"
    doc["payload"] = encode(payload)
    doc["payload_sha256"] = digest(doc["payload"])
    with pytest.raises(ValueError, match="publication hash"):
        analyze(changed, tmp_path)
