from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256
from systematic_trading.runtime_io import atomic_json, exclusive_lock


def test_atomic_state_failure_retains_previous_document(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    atomic_json(path, {"complete": 1})
    monkeypatch.setattr(Path, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk unavailable")))
    with pytest.raises(OSError):
        atomic_json(path, {"complete": 2})
    assert json.loads(path.read_text()) == {"complete": 1}
    assert list(tmp_path.iterdir()) == [path]


def test_exclusive_worker_lock_rejects_overlap_and_releases(tmp_path):
    path = tmp_path / "worker.lock"
    with exclusive_lock(path):
        with pytest.raises(OSError):
            with exclusive_lock(path):
                pytest.fail("Concurrent worker acquired the same output")
    with exclusive_lock(path):
        pass


def test_trading_worker_survives_iteration_and_status_write_failure(tmp_path, monkeypatch):
    from systematic_trading.live.management_service import TradingManagementService
    service = TradingManagementService(settings=AppSettings(data_dir=tmp_path), store=object())
    waits, calls = [], []
    service._wake = SimpleNamespace(wait=waits.append, clear=lambda: None)
    def run():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("Postgres disconnected")
        assert service._status.worker_last_error == "Postgres disconnected"
        service._stop.set()
    monkeypatch.setattr(service, "run_once", run)
    monkeypatch.setattr(service, "_save_status_locked", lambda: (_ for _ in ()).throw(OSError("disk unavailable")))
    service._run()
    assert len(calls) == 2 and all(delay >= 5 for delay in waits)
    assert service._status.worker_last_error is None
    assert not service.status().running


def test_broker_monitor_retries_failed_recovery_callback(monkeypatch):
    from systematic_trading.services import broker_monitor as module
    calls = []
    monitor = module.BrokerHealthMonitor(AppSettings())
    monitor._stop = SimpleNamespace(is_set=lambda: len(calls) == 2, wait=lambda _: None)
    monkeypatch.setattr(module, "probe_ib_tws_health", lambda _: SimpleNamespace(ok=True))
    def callback(result):
        calls.append(result)
        if len(calls) == 1:
            raise OSError("temporary callback failure")
    monitor.on_available = callback
    monitor._run()
    assert len(calls) == 2 and monitor._error is None
    assert not monitor._notify_pending


@pytest.fixture
def run_fixture(tmp_path, monkeypatch):
    from systematic_trading.research import tracked_runtime as runtime
    bundle, output = tmp_path / "bundle", tmp_path / "run"
    bundle.mkdir()
    atomic_json(bundle / "manifest.json", {"fixture": True})
    monkeypatch.setattr(runtime, "verify_bundle", lambda _: {"verified": True})
    calls = []
    def calculate(*, output, **kw):
        output.mkdir(parents=True)
        calls.append(output)
        atomic_json(output / "economic.json", {"complete": True, "value": 123})
        atomic_json(output / "run.json", dict(status="succeeded", engine="python", run_id="fixture",
            manifest_sha256=sha256(bundle / "manifest.json"), artifacts={"economic.json": sha256(output / "economic.json")}))
    monkeypatch.setattr(runtime, "run_python_bundle", calculate)
    return runtime, bundle, output, calls


def test_interrupted_run_retries_separately_and_reuses_verified_success(run_fixture):
    runtime, bundle, output, calls = run_fixture
    output.mkdir()
    atomic_json(output / "run.json", dict(status="running", engine="python", manifest_sha256=sha256(bundle / "manifest.json")))
    before = (output / "run.json").read_bytes()
    result = runtime.verified_run(bundle, output, "unused", "python")
    assert result[0] == {"complete": True, "value": 123}
    assert calls[0] != output and (output / "run.json").read_bytes() == before
    assert runtime.verified_run(bundle, output, "unused", "python") == result
    assert len(calls) == 1
    (calls[0] / "economic.json").write_text("tampered")
    with pytest.raises(ValueError, match="artifact changed"):
        runtime.verified_run(bundle, output, "unused", "python")
    assert len(calls) == 1


def test_failed_timeout_obeys_backoff_then_recovers(run_fixture, monkeypatch):
    runtime, bundle, output, calls = run_fixture
    calculate = runtime.run_python_bundle
    def fail(**kw):
        target = kw["output"]; target.mkdir(parents=True)
        atomic_json(target / "run.json", dict(status="failed", retryable=True, error="TimeoutExpired: test",
            manifest_sha256=sha256(bundle / "manifest.json")))
        raise subprocess.TimeoutExpired("fixture", 1)
    monkeypatch.setattr(runtime, "run_python_bundle", fail)
    with pytest.raises(subprocess.TimeoutExpired):
        runtime.verified_run(bundle, output, "unused", "python")
    monkeypatch.setattr(runtime, "run_python_bundle", calculate)
    with pytest.raises(RuntimeError, match="deferred"):
        runtime.verified_run(bundle, output, "unused", "python")
    state = output.with_name("run.retry.json")
    receipt = json.loads(state.read_text()); receipt["next_retry_at"] = (datetime.now(UTC)-timedelta(seconds=1)).isoformat()
    atomic_json(state, receipt)
    runtime.verified_run(bundle, output, "unused", "python")
    assert len(calls) == 1 and calls[0] != output


def test_failed_parity_is_not_automatically_retried(run_fixture):
    runtime, bundle, output, calls = run_fixture
    output.mkdir()
    atomic_json(output / "run.json", dict(status="failed", retryable=False, error="ValueError: LEAN parity failed",
        manifest_sha256=sha256(bundle / "manifest.json")))
    with pytest.raises(ValueError, match="requires review"):
        runtime.verified_run(bundle, output, "unused", "python")
    assert not calls


def test_active_orphan_container_is_not_restarted(run_fixture, monkeypatch):
    from systematic_trading.research import run_recovery
    runtime, bundle, output, calls = run_fixture
    output.mkdir()
    atomic_json(output / "run.json", dict(status="running", run_id="st-lean-fixture",
        manifest_sha256=sha256(bundle / "manifest.json")))
    monkeypatch.setattr(run_recovery.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="active-id"))
    with pytest.raises(RuntimeError, match="still running"):
        runtime.verified_run(bundle, output, "unused", "lean")
    assert not calls


def test_interrupted_bundle_preparation_does_not_poison_final_path(tmp_path, monkeypatch):
    from systematic_trading.research import calculation_worker as worker
    bundle, request = tmp_path / "bundle", tmp_path / "request.json"
    atomic_json(request, dict(inputs={}, models=None, bundle=str(bundle), spec={}))
    monkeypatch.setattr(worker, "checked_input", lambda _: dict(bars={}, fx={}, provenance={}))
    calls = []
    def freeze(*, root, **kw):
        root.mkdir(); calls.append(root)
        if len(calls) == 1:
            (root / "partial").write_text("crash evidence")
            raise OSError("interrupted")
        (root / "complete").write_text("verified")
    monkeypatch.setattr(worker, "freeze_bundle", freeze)
    monkeypatch.setattr(worker, "verify_bundle", lambda root: (root / "complete").read_text())
    with pytest.raises(OSError):
        worker.prepare(request)
    assert not bundle.exists()
    worker.prepare(request)
    assert (calls[0] / "partial").read_text() == "crash evidence"
    assert (bundle / "complete").read_text() == "verified"


def test_slow_archive_cannot_block_strategy_refresh_or_account_worker(tmp_path, monkeypatch):
    from threading import Event, Thread
    from systematic_trading.research import analytics_service as module
    from test_analytics_projection import MemoryAnalytics
    analytics = MemoryAnalytics(); analytics.initialize = lambda: None
    entered, release, calculated, account = Event(), Event(), Event(), Event()
    def archive(*args):
        entered.set()
        assert release.wait(5)
    monkeypatch.setattr(module, "import_lean_histories", archive)
    monkeypatch.setattr(module, "refresh_tracked_strategies", lambda *args: calculated.set())
    monkeypatch.setattr(module, "publish_dashboard", lambda *args: account.set())
    for name in ("refresh_tracked_fx", "publish_strategies", "import_json_group", "import_account_histories",
                 "import_transactional_histories", "import_raw_market_data"):
        monkeypatch.setattr(module, name, lambda *args: False)
    service = module.AnalyticsService(AppSettings(data_dir=tmp_path), object(), analytics)
    thread = Thread(target=service.refresh, args=("archives",))
    thread.start()
    try:
        assert entered.wait(2)
        service.refresh("research")
        service.refresh("operations")
        assert calculated.is_set() and account.is_set() and thread.is_alive()
        assert service.status()["archives_job"] == "lean-history"
    finally:
        release.set(); thread.join(timeout=5)
