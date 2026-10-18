from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import json

import pytest

from systematic_trading.execution.benchmark_qualification import qualify, session_statistics, PublishedDaily
from systematic_trading.execution.twap_benchmark import session_window
from test_execution_history import store  # noqa: F401
from test_twap_benchmark import record


def evidence():
    start = datetime(2026, 10, 8, 13, 30, tzinfo=UTC)
    bars = [dict(at=(start + timedelta(minutes=i)).isoformat(), open="100", high="102", low="98",
                 close="100", volume="1", wap="99") for i in range(390)]
    bars[-1].update(volume="389", wap="101")
    candidate = dict(format_version=2, symbol="SPY", observed_at="2026-10-11T12:00:00+00:00",
        window_start=start.isoformat(), window_end=(start + timedelta(minutes=390)).isoformat(), bars=bars,
        contract=dict(con_id=123, symbol="SPY", currency="USD", security_type="STK", primary_exchange="ARCA"))
    row = dict(symbol="SPY", trade_date="2026-10-08", source_vintage="2026-10-09T12:00:00+00:00",
        raw_open=100, raw_high=102, raw_low=98, raw_close=100, split_multiplier=1,
        quality_flags=["historical_vintage_uncertified"])
    return candidate, dict(row=row, actions=[])


def test_vwap_uses_wap_not_closes_and_quantity_scale_cancels():
    candidate, daily = evidence()
    audit = qualify(candidate, daily)
    assert Decimal(audit["reference_prices"]["session_vwap"]) == 100
    assert audit["status"] == "qualified_with_limitations"
    assert audit["research_approved"] is False
    for bar in candidate["bars"]:
        bar["volume"] = str(Decimal(bar["volume"]) * 100)
    assert session_statistics(candidate)["vwap"] == 100


@pytest.mark.parametrize("mutation,match", [
    (lambda c, d: c["bars"].pop(42), "Incomplete"),
    (lambda c, d: c["bars"][1].update(volume="-1"), "negative"),
    (lambda c, d: c["bars"][1].update(wap="NaN"), "WAP"),
    (lambda c, d: c["bars"].append(dict(c["bars"][1], volume="2")), "Conflicting"),
    (lambda c, d: d["row"].update(raw_close=None), "ConversionSyntax"),
    (lambda c, d: d["row"].update(raw_close=200), "disagreement"),
    (lambda c, d: d["row"].update(split_multiplier=2), "split"),
    (lambda c, d: d["actions"].append(dict(kind="splits", date="2026-10-09", ratio=2)), "split"),
    (lambda c, d: c["contract"].update(currency="HKD"), "identity"),
    (lambda c, d: d["row"]["quality_flags"].append("raw_unresolved"), "raw basis"),
])
def test_bad_or_unsupported_evidence_is_withheld(mutation, match):
    candidate, daily = evidence()
    mutation(candidate, daily)
    with pytest.raises((ValueError, ArithmeticError), match=match):
        qualify(candidate, daily)


def test_zero_volume_has_no_invented_wap_and_all_zero_is_withheld():
    candidate, _ = evidence()
    candidate["bars"][0].update(volume="0", wap=None)
    assert session_statistics(candidate)["vwap"] > 100
    for bar in candidate["bars"]:
        bar.update(volume="0", wap=None)
    with pytest.raises(ValueError, match="positive session volume"):
        session_statistics(candidate)


def test_calendar_early_close_holiday_and_routed_date(store):
    row = record(store)
    row.order.intended_trade_date = date(2026, 11, 27)
    start, end = session_window(row)
    assert (end - start) == timedelta(minutes=210)
    assert end.hour == 18  # New York standard time
    row.order.slippage_trade_date = date(2026, 10, 8)
    row.order.slippage_start_time, row.order.slippage_end_time = "09:35", "10:05"
    assert (session_window(row)[1] - session_window(row)[0]) == timedelta(minutes=390)
    assert session_window(row, original_intent=False)[1] == end
    row.order.intended_trade_date = date(2026, 11, 26)
    with pytest.raises(ValueError, match="supported US session"):
        session_window(row, original_intent=False)


def test_daily_requires_published_storage_and_equal_hash_payload():
    # Exercise incremental-catalog routing: the current catalog and a symbol's
    # storage batch differ. A readable local row alone cannot authorize use.
    from types import SimpleNamespace
    from systematic_trading.market_data.analytics_store import digest, encode
    _, daily = evidence()
    row = daily["row"]
    payload = encode(row)
    publisher = SimpleNamespace(workspace="test", latest=lambda _: dict(version="parent"),
        governed_rows=lambda *args, **kwargs: [dict(payload=payload, payload_hash=digest(payload))])
    reader = object.__new__(PublishedDaily)
    reader.analytics, reader.batch = publisher, "catalog"
    reader.catalog, reader.cache = {"SPY": dict(storage_batch="parent")}, {"SPY": ({row["trade_date"]: row}, [])}
    reader.inputs = SimpleNamespace(used={})
    assert reader.get("SPY", row["trade_date"])["storage_batch"] == "parent"
    publisher.latest = lambda _: None
    with pytest.raises(ValueError, match="not published"):
        reader.get("SPY", row["trade_date"])
    publisher.latest = lambda _: dict(version="parent")
    changed = deepcopy(row)
    changed["raw_close"] = 101
    publisher.governed_rows = lambda *args, **kwargs: [dict(payload=json.dumps(changed), payload_hash=digest(json.dumps(changed)))]
    with pytest.raises(ValueError, match="mismatch"):
        reader.get("SPY", row["trade_date"])
