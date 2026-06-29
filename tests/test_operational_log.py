import json
from datetime import UTC, datetime
from decimal import Decimal

from systematic_trading.services import OperationalLogger, append_operational_log


def test_operational_log_writes_jsonl_and_redacts_secrets(tmp_path) -> None:
    path = tmp_path / "log" / "ops.jsonl"

    record = append_operational_log(
        path,
        service_id="service",
        level="info",
        event="started",
        message="service started",
        occurred_at=datetime(2026, 6, 27, 12, tzinfo=UTC),
        details={
            "count": 3,
            "price": Decimal("1.23"),
            "nested": {"api_token": "do-not-write", "safe": "ok"},
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert record.event == "started"
    assert payload["service_id"] == "service"
    assert payload["level"] == "info"
    assert payload["event"] == "started"
    assert payload["details"]["price"] == "1.23"
    assert payload["details"]["nested"]["api_token"] == "[redacted]"
    assert payload["details"]["nested"]["safe"] == "ok"


def test_operational_logger_helpers_append_records(tmp_path) -> None:
    path = tmp_path / "ops.jsonl"
    logger = OperationalLogger(path=path, service_id="worker")

    logger.info("heartbeat", message="ok", attempt=1)
    logger.error("failed", message="bad", password="secret")

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["heartbeat", "failed"]
    assert rows[1]["level"] == "error"
    assert rows[1]["details"]["password"] == "[redacted]"
