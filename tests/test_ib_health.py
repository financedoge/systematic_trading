from datetime import UTC, datetime

from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.ib_health import IBTwsHealthProbeResult
from systematic_trading.execution.ib_health import gateway_connection_issue


def test_gateway_server_disconnect_is_not_a_healthy_local_handshake():
    assert gateway_connection_issue(["-1:2110:Server disconnected", "-1:2105:Historical farm disconnected"])
    assert gateway_connection_issue(["-1:1100:Disconnected", "-1:1102:Restored"]) is None
    assert gateway_connection_issue(["-1:1101:Restored", "-1:2110:Disconnected"])
    assert gateway_connection_issue(["-1:2107:Historical farm idle", "-1:2108:Market farm idle"]) is None


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
