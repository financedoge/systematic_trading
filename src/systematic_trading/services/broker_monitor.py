"""Application-owned read-only transport probe; no order operations."""
from threading import Event, Lock, Thread
from datetime import UTC, datetime
import logging

from systematic_trading.execution.ib_health import probe_ib_tws_health


class BrokerHealthMonitor:
    def __init__(self, settings, *, on_available=None):
        self.settings = settings
        self.on_available = on_available
        self._stop, self._lock = Event(), Lock()
        self._result = None
        self._error = None
        self._notify_pending = False
        self._thread = Thread(target=self._run, name="broker-health", daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=12)

    def snapshot(self):
        with self._lock:
            if self._error:
                from systematic_trading.services.health import ServiceRuntimeSnapshot
                return ServiceRuntimeSnapshot(running=False, heartbeat_at=datetime.now(UTC), last_error=self._error,
                                              message="Broker health worker will retry.")
            return self._result.to_service_snapshot() if self._result else None

    def _run(self):
        while not self._stop.is_set():
            try:
                self.probe_once()
            except Exception as exc:
                with self._lock:
                    self._error = str(exc)
                logging.getLogger(__name__).exception("Broker health iteration failed; retrying")
            self._stop.wait(60)

    def probe_once(self):
        result = probe_ib_tws_health(self.settings)
        with self._lock:
            recovered = result.ok and (self._result is None or not self._result.ok or self._notify_pending or self._error)
            self._result = result
            self._error = None
            self._notify_pending = bool(recovered)
        if recovered and self.on_available is not None:
            self.on_available(result)
        with self._lock:
            self._notify_pending = False
        return result
