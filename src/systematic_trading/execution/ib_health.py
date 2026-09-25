from __future__ import annotations

from systematic_trading.execution.ib_compat import compatible_ib_errors

from datetime import UTC, datetime
from threading import Event, Thread

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.services.health import ServiceRuntimeSnapshot


class IBTwsHealthProbeResult(BaseModel):
    environment: OrderEnvironment
    host: str
    port: int
    client_id: int
    checked_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    ok: bool
    message: str
    next_valid_order_id: int | None = None
    managed_accounts: list[str] = Field(default_factory=list)
    server_time: datetime | None = None
    errors: list[str] = Field(default_factory=list)

    def to_service_snapshot(self) -> ServiceRuntimeSnapshot:
        return ServiceRuntimeSnapshot(
            running=self.ok,
            heartbeat_at=self.checked_at,
            last_error=None if self.ok else self.message,
            message=self.message,
            details=self.model_dump(mode="json"),
        )


def probe_ib_tws_health(
    settings: AppSettings,
    *,
    environment: OrderEnvironment = OrderEnvironment.PAPER,
    client_id: int | None = None,
    timeout_seconds: float = 8.0,
) -> IBTwsHealthProbeResult:
    profile = InteractiveBrokersAdapter(settings).profile_for(environment).model_copy(
        update={"client_id": client_id or settings.ib_health_client_id or settings.ib_client_id + 50}
    )
    checked_at = datetime.now(tz=UTC)
    try:
        return _probe_profile(profile, checked_at=checked_at, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return IBTwsHealthProbeResult(
            environment=profile.environment,
            host=profile.host,
            port=profile.port,
            client_id=profile.client_id,
            checked_at=checked_at,
            ok=False,
            message=f"IB TWS API health check failed: {type(exc).__name__}: {exc}",
        )


def _probe_profile(
    profile,
    *,
    checked_at: datetime,
    timeout_seconds: float,
) -> IBTwsHealthProbeResult:
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
    except ImportError as exc:
        raise RuntimeError("IB TWS health probe requires the ibapi package. Install the optional IB dependency.") from exc

    class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.ready = Event()
            self.server_time_seen = Event()
            self.next_valid_order_id: int | None = None
            self.managed_accounts: list[str] = []
            self.server_time: datetime | None = None
            self.errors: list[str] = []

        def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
            self.next_valid_order_id = orderId
            self.ready.set()

        def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
            self.managed_accounts = [account for account in accountsList.split(",") if account]

        def currentTime(self, time: int) -> None:  # noqa: N802
            self.server_time = datetime.fromtimestamp(time, tz=UTC)
            self.server_time_seen.set()

        @compatible_ib_errors
        def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
            self.errors.append(f"{reqId}:{errorCode}:{errorString}")

    app = _App()
    app.connect(profile.host, profile.port, profile.client_id)
    thread = Thread(target=app.run, daemon=True)
    thread.start()
    try:
        if not app.ready.wait(timeout_seconds):
            recent_errors = f" Recent IB messages: {'; '.join(app.errors[-5:])}" if app.errors else ""
            raise TimeoutError(
                f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.{recent_errors}"
            )
        app.reqCurrentTime()
        app.server_time_seen.wait(min(timeout_seconds, 2.0))
        return IBTwsHealthProbeResult(
            environment=profile.environment,
            host=profile.host,
            port=profile.port,
            client_id=profile.client_id,
            checked_at=checked_at,
            ok=True,
            message="IB TWS API responded to nextValidId.",
            next_valid_order_id=app.next_valid_order_id,
            managed_accounts=app.managed_accounts,
            server_time=app.server_time,
            errors=app.errors[-10:],
        )
    finally:
        app.disconnect()
        thread.join(timeout=2)
