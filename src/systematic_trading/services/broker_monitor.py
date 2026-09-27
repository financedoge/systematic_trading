"""Application-owned read-only transport probe; no order operations."""
from threading import Event, Lock, Thread

from systematic_trading.execution.ib_health import probe_ib_tws_health


class BrokerHealthMonitor:
    def __init__(self, settings):
        self.settings = settings
        self._stop, self._lock = Event(), Lock()
        self._result = None
        self._thread = Thread(target=self._run, name="broker-health", daemon=True)

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=12)

    def snapshot(self):
        with self._lock:
            return self._result.to_service_snapshot() if self._result else None

    def _run(self):
        while not self._stop.is_set():
            result = probe_ib_tws_health(self.settings)
            with self._lock:
                self._result = result
            self._stop.wait(60)
