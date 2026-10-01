import json
import os
import subprocess
import sys

import pytest

from systematic_trading.runtime_io import atomic_json
from systematic_trading.services.recovery import LocalRecovery, control


def fixture_recovery(tmp_path, enabled=None):
    run = tmp_path / "var/run"
    atomic_json(run / "local_recovery.profile.json", dict(enabled=enabled or {"operator": True}))
    return LocalRecovery(tmp_path)


def test_recovery_honors_disabled_services_explicit_pause_and_backoff(tmp_path, monkeypatch):
    service = fixture_recovery(tmp_path)
    calls = []
    monkeypatch.setattr(service, "probe", lambda *a: ("missing", "test"))
    def fail(name):
        calls.append(name)
        raise OSError("dependency unavailable")
    monkeypatch.setattr(service, "repair", fail)
    service.cycle(now=1000)
    service.cycle(now=1010)
    assert calls == ["operator"]
    # Restarting the supervisor retains the cooldown.
    restored = LocalRecovery(tmp_path)
    assert restored.retries["operator"]["next_retry_at"] == 1030
    control(tmp_path, "pause", "operator")
    service.cycle(now=2000)
    assert calls == ["operator"] and service.details["operator"]["status"] == "disabled"
    control(tmp_path, "resume", "operator")
    service.cycle(now=2001)
    assert calls == ["operator", "operator"]
    assert service.retries["operator"]["next_retry_at"] == 2061


def test_recovery_restarts_only_a_dead_isolated_process(tmp_path, monkeypatch):
    service = fixture_recovery(tmp_path)
    children = []
    def repair(_):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        children.append(child)
        for name in ("operator_dashboard.pid", "event_outbox_dispatcher.pid"):
            (service.run / name).write_text(str(child.pid))
    monkeypatch.setattr(service, "repair", repair)
    try:
        service.cycle(now=1000)
        service.cycle(now=1001)
        assert len(children) == 1
        children[0].terminate(); children[0].wait(timeout=5)
        service.cycle(now=1031)
        assert len(children) == 2
        assert service.details["operator"]["status"] == "running"
        control(tmp_path, "pause", "operator")
        children[-1].terminate(); children[-1].wait(timeout=5)
        service.cycle(now=1100)
        assert len(children) == 2
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate(); child.wait(timeout=5)


def test_existing_recorder_child_and_explicit_backup_stop_prevent_restart(tmp_path, monkeypatch):
    service = fixture_recovery(tmp_path, {"recorder": True, "backup": True})
    (service.run / "market_data_recorder.child.pid").write_text(str(os.getpid()))
    (service.run / "database_sync.stop").touch()
    monkeypatch.setattr(service, "repair", lambda _: pytest.fail("Duplicate child or ignored stop"))
    service.cycle()
    assert service.details["recorder"]["status"] == "waiting"
    assert service.details["backup"]["status"] == "disabled"


def test_full_platform_stop_prevents_repairs(tmp_path, monkeypatch):
    service = fixture_recovery(tmp_path)
    control(tmp_path, "stop")
    monkeypatch.setattr(service, "repair", lambda _: pytest.fail("Restart after stop"))
    service.cycle()
    assert not service.details
    state = json.loads((service.run / "local_recovery.state.json").read_text())
    assert state["last_error"] is None
