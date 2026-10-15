from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.benchmark_archive import digest, retained_state
from systematic_trading.execution.benchmark_collection import ExecutionBenchmarkCollector
from systematic_trading.execution.twap_benchmark import IBMinuteBars, TwapBenchmarkService
from systematic_trading.research.analytics_projection import import_json_group
from test_analytics_projection import MemoryAnalytics
from test_execution_history import store  # noqa: F401
from test_twap_benchmark import record, START


NOW = datetime(2026, 10, 11, 15, tzinfo=UTC)


class Provider:
    def __init__(self):
        self.calls = []

    def fetch(self, symbol, start, end):
        self.calls.append((symbol, start, end))
        return [dict(at=(start + timedelta(minutes=i)).isoformat(), close="100", volume="7", wap="99")
                for i in range(int((end - start).total_seconds() / 60))]


def setup(tmp_path, records, provider=None, **settings):
    settings = AppSettings(data_dir=tmp_path, execution_benchmark_collection_enabled=True, **settings)
    provider = provider or Provider()
    service = TwapBenchmarkService(settings, provider)
    analytics = MemoryAnalytics()
    collector = ExecutionBenchmarkCollector(settings, SimpleNamespace(list_broker_order_records=lambda: list(records)),
                                            service, analytics)
    return service, collector, analytics, provider


def test_collection_without_blotter_deduplicates_and_publishes_audited_observations(store, tmp_path):
    row = record(store)
    other = row.model_copy(update={"local_order_id": "second"})
    service, collector, analytics, provider = setup(tmp_path, [row, other])
    collector.refresh(now=NOW)
    service.pool.shutdown(wait=True)
    report = collector.refresh(now=NOW)
    assert len(provider.calls) == 2  # one shared order window and one shared regular session
    assert report["window_status_counts"] == {"ready": 1}
    assert report["paper_order_count"] == 2
    files = list((tmp_path / "execution_benchmarks").glob("*.json"))
    assert len(files) == 2
    assert report["session_status_counts"] == {"ready": 1}
    candidate = json.loads(files[0].read_text())
    assert candidate["audit"]["coverage"] == "100%"
    assert candidate["bars"][0]["volume"] == "7"
    assert candidate["research_approved"] is False
    import_json_group(analytics, "execution-benchmarks", files, "execution_benchmark")
    assert len(analytics.docs["execution-benchmarks"]) == 2
    writes = analytics.writes
    collector.refresh(now=NOW + timedelta(seconds=30))
    assert analytics.writes == writes  # unchanged coverage is not a new publication
    assert (tmp_path / "run" / "execution_benchmark_collection.json").exists()
    assert len(list((tmp_path / "execution_benchmark_attempts").rglob("*.request.json"))) == 2
    restarted = TwapBenchmarkService(service.settings, Provider())
    assert restarted.get(row, now=NOW)["status"] == "ready"
    assert not restarted.provider.calls
    restarted.close()


def test_original_and_routed_windows_are_distinct(store, tmp_path):
    row = record(store)
    row.order.slippage_trade_date = START.date()
    row.order.slippage_start_time = "09:35"
    row.order.slippage_end_time = "10:05"
    row.order.intended_trade_date += timedelta(days=3)
    service, collector, _, provider = setup(tmp_path, [row])
    collector.refresh(now=NOW)
    service.pool.shutdown(wait=True)
    report = collector.refresh(now=NOW)
    assert len(provider.calls) == 4
    assert report["unique_window_count"] == report["unique_session_count"] == 2
    assert report["orders"][0]["original"]["window_start"] != report["orders"][0]["routed"]["window_start"]


def test_failure_retry_is_durable_and_partial_response_retained(store, tmp_path):
    class Broken(Provider):
        def fetch(self, *args):
            self.calls.append(args)
            error = ValueError("Historical permission unavailable")
            error.evidence = {"bars": [{"close": "123"}]}
            raise error

    row = record(store)
    service, collector, _, provider = setup(tmp_path, [row], Broken())
    collector.refresh()  # real time matches persisted cooldown
    service.pool.shutdown(wait=True)
    restarted = TwapBenchmarkService(service.settings, provider)
    result = restarted.get(row)
    assert result["status"] == "unavailable" and result["next_retry_at"]
    assert len(provider.calls) == 2
    raw = next((tmp_path / "execution_benchmark_attempts").rglob("*.response.json"))
    assert json.loads(raw.read_text())["response"]["bars"] == [{"close": "123"}]
    state = retained_state(tmp_path, result["benchmark_key"])
    assert state["attempt_count"] == 1
    assert state["status"] == "unavailable"
    assert not list((tmp_path / "execution_benchmarks").glob("*.json"))
    restarted.close()


def test_completed_evidence_tampering_withholds_read_and_publication(store, tmp_path):
    row = record(store)
    service, collector, analytics, provider = setup(tmp_path, [row])
    collector.refresh(now=NOW)
    service.pool.shutdown(wait=True)
    key = service.get(row, now=NOW)["benchmark_key"]
    path = tmp_path / "execution_benchmarks" / (key + ".json")
    saved = json.loads(path.read_text())
    saved["bars"][0]["close"] = "101"
    saved["audit"]["bars_sha256"] = digest(saved["bars"])
    # A forged/recomputed summary cannot replace the immutable source response.
    saved["audit"]["twap_price"] = str((Decimal(2900) + 101) / 30)
    path.write_text(json.dumps(saved))
    restarted = TwapBenchmarkService(service.settings, provider)
    assert restarted.get(row, now=NOW)["status"] == "unavailable"
    with pytest.raises(ValueError, match="original capture"):
        import_json_group(analytics, "execution-benchmarks", [path], "execution_benchmark")
    assert "execution-benchmarks" not in analytics.versions
    assert len(provider.calls) == 2
    restarted.close()


def test_pending_queue_is_bounded_and_closing_does_not_schedule(store, tmp_path):
    release = Event()

    class Waiting(Provider):
        def fetch(self, *args):
            assert release.wait(5)
            return super().fetch(*args)

    row = record(store)
    other = row.model_copy(deep=True)
    other.order.intended_trade_date += timedelta(days=3)
    service, _, _, provider = setup(tmp_path, [row], Waiting(), execution_benchmark_max_pending=1)
    try:
        assert service.get(row, now=NOW)["status"] == "loading"
        assert service.get(other, now=NOW)["status"] == "unavailable"
        assert len(service.pending) == 1
    finally:
        release.set()
        service.pool.shutdown(wait=True)
        service.close()
    assert service.get(other, now=NOW)["status"] == "unavailable"
    assert len(provider.calls) == 1


def test_collection_excludes_live_and_unfilled_and_reconciliation_issues(store, tmp_path):
    live = record(store).model_copy(update={"environment": OrderEnvironment.LIVE})
    unfilled = record(store).model_copy(update={"local_order_id": "no-fill", "filled_quantity": 0})
    issue = record(store).model_copy(update={"local_order_id": "conflict", "execution_sync_issue": "conflict"})
    service, collector, _, provider = setup(tmp_path, [live, unfilled, issue])
    result = collector.refresh(now=NOW)
    assert result["paper_order_count"] == 2
    assert result["order_status_counts"] == {"execution_review_required": 1, "not_filled": 1}
    assert not provider.calls
    service.close()


def test_application_owns_collector_and_exposes_read_only_coverage(tmp_path, monkeypatch):
    lifecycle = []
    monkeypatch.setattr(ExecutionBenchmarkCollector, "start", lambda self: lifecycle.append("start"))
    monkeypatch.setattr(ExecutionBenchmarkCollector, "close", lambda self: lifecycle.append("close"))
    with TestClient(create_app(AppSettings(data_dir=tmp_path))) as client:
        response = client.get("/api/v1/execution/interactive-brokers/benchmark-coverage")
        assert response.status_code == 200
        assert response.json()["coverage"] is None
        assert lifecycle == ["start"]
    assert lifecycle == ["start", "close"]


def test_started_worker_collects_without_an_http_request(store, tmp_path):
    called = Event()

    class Observed(Provider):
        def fetch(self, *args):
            called.set()
            return super().fetch(*args)

    service, collector, _, _ = setup(tmp_path, [record(store)], Observed())
    try:
        collector.start()
        assert called.wait(5)
        assert collector.status()["running"]
    finally:
        collector.close()
        service.pool.shutdown(wait=True)
        service.close()
    assert not collector.status()["running"]


@pytest.mark.parametrize("ambiguous", [False, True])
@pytest.mark.parametrize("error_code,recent", [(2188, False), (2188, True), (162, False)])
def test_ib_fetch_qualifies_identity_and_retains_volume_wap(monkeypatch, ambiguous, error_code, recent):
    import ibapi.client
    import ibapi.wrapper

    requested = []

    class Client:
        def __init__(self, wrapper):
            pass

        def connect(self, *args):
            self.nextValidId(1)

        def run(self):
            pass

        def disconnect(self):
            pass

        def reqContractDetails(self, req_id, contract):
            contract.conId = 123
            contract.localSymbol = "SPY"
            self.contractDetails(req_id, SimpleNamespace(contract=contract))
            if ambiguous:
                self.contractDetails(req_id, SimpleNamespace(contract=contract))
            self.contractDetailsEnd(req_id)

        def reqHistoricalData(self, *args):
            requested.append(args)
            self.error(args[0], error_code, "Historical data permission message")
            self.historicalData(args[0], SimpleNamespace(date=int(START.timestamp()), open=100, high=102,
                low=99, close=101, volume=7, wap=100.5, barCount=2))
            self.historicalDataEnd(args[0], "", "")

    monkeypatch.setattr(ibapi.client, "EClient", Client)
    monkeypatch.setattr(ibapi.wrapper, "EWrapper", type("Wrapper", (), {}))
    provider = IBMinuteBars(AppSettings())
    end = datetime.now(UTC) if recent else START + timedelta(minutes=30)
    if ambiguous:
        with pytest.raises(ValueError, match="ambiguous"):
            provider.fetch("SPY", end - timedelta(minutes=30), end)
        assert not requested
    elif recent or error_code != 2188:
        with pytest.raises(ValueError, match=f"IB {error_code}"):
            provider.fetch("SPY", end - timedelta(minutes=30), end)
    else:
        result = provider.fetch("SPY", START, end)
        assert result["contract"]["con_id"] == 123
        assert result["bars"][0]["volume"] == "7"
        assert result["bars"][0]["wap"] == "100.5"
        assert any(":2188:" in message for message in result["messages"])
        assert requested[0][5:8] == ("TRADES", 1, 2)
