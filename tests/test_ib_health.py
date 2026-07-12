from datetime import UTC, datetime

from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.ib_health import IBTwsHealthProbeResult


def test_ib_tws_health_result_converts_to_service_snapshot() -> None:
    result = IBTwsHealthProbeResult(
        environment=OrderEnvironment.PAPER,
        host="127.0.0.1",
        port=7497,
        client_id=151,
        checked_at=datetime(2026, 7, 12, 1, 0, tzinfo=UTC),
        ok=True,
        message="IB TWS API responded to nextValidId.",
        next_valid_order_id=42,
        managed_accounts=["DU123"],
    )

    snapshot = result.to_service_snapshot()

    assert snapshot.running is True
    assert snapshot.last_error is None
    assert snapshot.details["next_valid_order_id"] == 42
    assert snapshot.details["managed_accounts"] == ["DU123"]
