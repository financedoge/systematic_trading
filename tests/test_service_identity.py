"""Windows PID reuse must not make stale service PID files look alive."""
import os
from pathlib import Path
import runpy
import sys

import pytest

from systematic_trading.services import health, recovery
from systematic_trading.services.health import (
    _pid_executable_name,
    _pid_matches_executable,
    _pid_matches_platform_python,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows process image names")
def test_current_process_is_this_platform_python():
    assert _pid_executable_name(os.getpid()) is not None
    assert _pid_matches_platform_python(os.getpid()) is True
    assert _pid_matches_executable(os.getpid(), {os.path.basename(sys.executable)}) is True


@pytest.mark.skipif(os.name != "nt", reason="Windows System process")
def test_foreign_system_process_is_not_platform_python():
    # PID 4 is always the Windows System process; a recycled PID like this must
    # never be reported as one of the platform's Python services.
    assert _pid_matches_platform_python(4) is False


def test_unreadable_image_name_stays_conservative(monkeypatch):
    monkeypatch.setattr(health, "_pid_executable_name", lambda pid: None)
    assert _pid_matches_platform_python(1234) is None


def test_recovery_ignores_recycled_pid(tmp_path, monkeypatch):
    pid_path = tmp_path / "market_data_recorder.pid"
    pid_path.write_text(str(os.getpid()), encoding="ascii")
    monkeypatch.setattr(recovery, "_pid_is_running", lambda pid: True)
    monkeypatch.setattr(recovery, "_pid_matches_platform_python", lambda pid: False)
    assert recovery.process_present(pid_path) is False
    monkeypatch.setattr(recovery, "_pid_matches_platform_python", lambda pid: None)
    assert recovery.process_present(pid_path) is True
    monkeypatch.setattr(recovery, "_pid_matches_platform_python", lambda pid: True)
    assert recovery.process_present(pid_path) is True
    monkeypatch.setattr(recovery, "_pid_is_running", lambda pid: False)
    assert recovery.process_present(pid_path) is False


def test_database_sync_guard_ignores_recycled_pid(tmp_path):
    module = runpy.run_path("scripts/sync_databases.py")
    guard = module["assert_services_stopped"]
    # runpy returns a copy of the globals; the function closes over the live dict.
    globals_ = guard.__globals__
    run = tmp_path / "var" / "run"
    run.mkdir(parents=True)
    (run / "market_data_recorder.pid").write_text(str(os.getpid()), encoding="ascii")
    globals_["ROOT"] = tmp_path
    globals_["process_exists"] = lambda pid: True

    globals_["process_is_platform_python"] = lambda pid: False
    guard()  # A recycled PID is ignored, not fatal.

    globals_["process_is_platform_python"] = lambda pid: True
    with pytest.raises(module["SyncConflict"], match="Stop local services first"):
        guard()

    globals_["process_is_platform_python"] = lambda pid: None
    with pytest.raises(module["SyncConflict"], match="Stop local services first"):
        guard()
