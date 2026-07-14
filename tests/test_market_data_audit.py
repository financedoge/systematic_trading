import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.recorders import (
    CapturedMarketDataBar,
    IBMarketDataMode,
    MarketDataRecorder,
    RawDataCatalog,
    RawMarketDataWriter,
)
from systematic_trading.web import market_data_audit as audit_module


class _FakeClickHouseMarketDataClient:
    last_query: dict[str, object] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def query_daily_bar_symbols(self) -> list[dict[str, object]]:
        return [
            {
                "symbol": "QQQ",
                "row_count": 3400,
                "first_trade_date": "2012-01-03",
                "last_trade_date": "2026-07-10",
            },
            {
                "symbol": "SPY",
                "row_count": 3510,
                "first_trade_date": "2012-01-03",
                "last_trade_date": "2026-07-10",
            },
        ]

    def query_daily_bars(
        self,
        *,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, object]]:
        self.__class__.last_query = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        return [
            {
                "symbol": "SPY",
                "trade_date": "2026-07-09",
                "open": 620.0,
                "high": 623.0,
                "low": 619.5,
                "close": 622.0,
                "volume": 1000000,
                "source_name": "sqlite_price_bars",
                "source_priority": 100,
                "adjustment": "provider_default",
                "available_at": "2026-07-10T00:00:00.000Z",
                "ingested_at": "2026-07-11T00:00:00.000Z",
                "quality_flags": ["from_sqlite"],
                "payload_hash": "sha256:test-a",
            },
            {
                "symbol": "SPY",
                "trade_date": "2026-07-10",
                "open": 622.0,
                "high": 625.0,
                "low": 621.0,
                "close": 624.0,
                "volume": 1100000,
                "source_name": "sqlite_price_bars",
                "source_priority": 100,
                "adjustment": "provider_default",
                "available_at": "2026-07-11T00:00:00.000Z",
                "ingested_at": "2026-07-11T00:00:00.000Z",
                "quality_flags": [],
                "payload_hash": "sha256:test-b",
            },
        ]


def test_golden_daily_symbols_endpoint_lists_clickhouse_symbols(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "ClickHouseMarketDataClient", _FakeClickHouseMarketDataClient)
    settings = AppSettings(database_path=tmp_path / "platform.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/market-data/daily-symbols")

    assert response.status_code == 200
    payload = response.json()
    assert [item["symbol"] for item in payload["symbols"]] == ["QQQ", "SPY"]
    assert payload["symbols"][1]["row_count"] == 3510
    assert payload["symbols"][1]["last_trade_date"] == "2026-07-10"


def test_golden_daily_bars_endpoint_returns_chart_ready_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "ClickHouseMarketDataClient", _FakeClickHouseMarketDataClient)
    settings = AppSettings(database_path=tmp_path / "platform.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/market-data/daily-bars",
            params={
                "symbol": "spy",
                "start_date": "2026-07-01",
                "end_date": "2026-07-10",
                "limit": 100,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert _FakeClickHouseMarketDataClient.last_query == {
        "symbol": "SPY",
        "start_date": "2026-07-01",
        "end_date": "2026-07-10",
        "limit": 100,
    }
    assert payload["summary"]["symbol"] == "SPY"
    assert payload["summary"]["rows_returned"] == 2
    assert payload["summary"]["first_trade_date"] == "2026-07-09"
    assert payload["summary"]["last_trade_date"] == "2026-07-10"
    assert payload["summary"]["source_names"] == ["sqlite_price_bars"]
    assert payload["summary"]["quality_flag_counts"] == {"from_sqlite": 1}
    assert payload["bars"][1]["close"] == 624.0


def test_market_data_audit_endpoint_returns_chart_and_table_rows(tmp_path) -> None:
    hot_root = tmp_path / "hot"
    policy_path = _write_storage_policy(tmp_path, hot_root)
    recorder = MarketDataRecorder(
        writer=RawMarketDataWriter(hot_root, part_id="audit", fsync=False),
        catalog=RawDataCatalog(hot_root, fsync=False),
        state_path=tmp_path / "run" / "market_data_recorder.state.json",
        started_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
    )
    recorder.record_bar(_bar(datetime(2026, 7, 10, 19, 30, 0, tzinfo=UTC), "512.34"))
    recorder.record_bar(_bar(datetime(2026, 7, 10, 19, 30, 5, tzinfo=UTC), "512.56"))

    settings = AppSettings(
        database_path=tmp_path / "platform.db",
        data_dir=tmp_path,
        market_data_storage_policy_path=policy_path,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/market-data/audit",
            params={
                "symbol": "SPY",
                "recorder_date": "2026-07-11",
                "bar_size_seconds": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["rows_returned"] == 2
    assert payload["summary"]["payload_hash_mismatches"] == 0
    assert payload["summary"]["duplicate_raw_event_ids"] == 0
    assert len(payload["bars"]) == 2
    assert payload["bars"][0]["close"] == "512.34"
    assert payload["rows"][0]["hash_ok"] is True
    assert payload["rows"][0]["payload"]["market_data_mode"] == "delayed"
    assert payload["rows"][0]["raw_ref"].endswith("#offset=0")


def test_market_data_audit_symbols_endpoint_lists_recorded_symbols(tmp_path) -> None:
    hot_root = tmp_path / "hot"
    policy_path = _write_storage_policy(tmp_path, hot_root)
    recorder = MarketDataRecorder(
        writer=RawMarketDataWriter(hot_root, part_id="audit-symbols", fsync=False),
        catalog=RawDataCatalog(hot_root, fsync=False),
        state_path=tmp_path / "run" / "market_data_recorder.state.json",
        started_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
    )
    recorder.record_bar(_bar(datetime(2026, 7, 10, 19, 30, 0, tzinfo=UTC), "512.34"))
    recorder.record_bar(_bar(datetime(2026, 7, 10, 19, 30, 5, tzinfo=UTC), "512.56", symbol="QQQ"))

    settings = AppSettings(
        database_path=tmp_path / "platform.db",
        data_dir=tmp_path,
        market_data_storage_policy_path=policy_path,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get(
            "/api/v1/market-data/audit/symbols",
            params={"recorder_date": "2026-07-11"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbols"] == ["QQQ", "SPY"]
    assert payload["recorder_dates"] == ["2026-07-11"]
    assert payload["latest_recorder_date"] == "2026-07-11"
    assert payload["records_invalid"] == 0


def test_market_data_audit_supports_inclusive_recorder_session_ranges(tmp_path) -> None:
    hot_root = tmp_path / "hot"
    policy_path = _write_storage_policy(tmp_path, hot_root)
    recorder = MarketDataRecorder(
        writer=RawMarketDataWriter(hot_root, part_id="audit-range", fsync=False),
        catalog=RawDataCatalog(hot_root, fsync=False),
        state_path=tmp_path / "run" / "market_data_recorder.state.json",
        started_at=datetime(2026, 7, 11, 3, 30, tzinfo=UTC),
    )
    recorder.record_bar(
        _bar(
            datetime(2026, 7, 10, 19, 30, 0, tzinfo=UTC),
            "512.34",
            received_at=datetime(2026, 7, 11, 3, 30, 5, tzinfo=UTC),
        )
    )
    recorder.record_bar(
        _bar(
            datetime(2026, 7, 12, 19, 30, 0, tzinfo=UTC),
            "516.78",
            symbol="QQQ",
            received_at=datetime(2026, 7, 13, 3, 30, 5, tzinfo=UTC),
        )
    )

    settings = AppSettings(
        database_path=tmp_path / "platform.db",
        data_dir=tmp_path,
        market_data_storage_policy_path=policy_path,
    )
    with TestClient(create_app(settings)) as client:
        symbols_response = client.get(
            "/api/v1/market-data/audit/symbols",
            params={"recorder_start_date": "2026-07-11", "recorder_end_date": "2026-07-13"},
        )
        range_response = client.get(
            "/api/v1/market-data/audit",
            params={"recorder_start_date": "2026-07-11", "recorder_end_date": "2026-07-13"},
        )
        latest_response = client.get(
            "/api/v1/market-data/audit",
            params={"recorder_start_date": "2026-07-11", "recorder_end_date": "2026-07-13", "limit": 1},
        )
        invalid_response = client.get(
            "/api/v1/market-data/audit",
            params={"recorder_start_date": "2026-07-13", "recorder_end_date": "2026-07-11"},
        )

    assert symbols_response.status_code == 200
    assert symbols_response.json()["symbols"] == ["QQQ", "SPY"]
    assert symbols_response.json()["recorder_dates"] == ["2026-07-11", "2026-07-13"]
    assert range_response.status_code == 200
    payload = range_response.json()
    assert payload["summary"]["recorder_start_date"] == "2026-07-11"
    assert payload["summary"]["recorder_end_date"] == "2026-07-13"
    assert [row["recorder_date"] for row in payload["rows"]] == ["2026-07-11", "2026-07-13"]
    assert latest_response.json()["rows"][0]["recorder_date"] == "2026-07-13"
    assert invalid_response.status_code == 400


def _write_storage_policy(tmp_path, hot_root):
    policy_path = tmp_path / "market-data-storage.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile": "test",
                "hot_spool_root": hot_root.as_posix(),
                "local_archive_root": (tmp_path / "archive").as_posix(),
                "backup_archive_root": None,
                "policy": {},
                "retention": {},
                "watermarks": {},
            }
        ),
        encoding="utf-8",
    )
    return policy_path


def _bar(
    exchange_timestamp: datetime,
    close: str,
    *,
    symbol: str = "SPY",
    received_at: datetime | None = None,
) -> CapturedMarketDataBar:
    return CapturedMarketDataBar(
        environment=OrderEnvironment.PAPER,
        symbol=symbol,
        request_id=94001,
        exchange_timestamp=exchange_timestamp,
        received_at=received_at or datetime(2026, 7, 11, 3, 30, 5, tzinfo=UTC),
        capture_mode="historical_backfill",
        market_data_mode=IBMarketDataMode.DELAYED,
        source_sequence=f"{symbol}:{exchange_timestamp.isoformat()}",
        open=Decimal("512.10"),
        high=Decimal("513.00"),
        low=Decimal("511.80"),
        close=Decimal(close),
        volume=1000,
        wap=Decimal("512.50"),
        count=42,
        bar_size_seconds=5,
    )
