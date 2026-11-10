from pathlib import Path
import shutil
import sys
import threading
import time

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.storage.nas_sync import file_hash, read_json, write_json
from systematic_trading.storage.system_backup import BackupStopped, SystemBackup, snapshot_nats
from systematic_trading.runtime_io import exclusive_lock


@pytest.fixture
def backup(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "source").mkdir(parents=True)
    (workspace / "source/data.txt").write_text("durable market evidence\n")
    (workspace / "source/.env").write_text("secret-must-not-be-copied")
    (workspace / "source/.env.production").write_text("another-secret")
    repository = tmp_path / "nas/repo"
    repository.parent.mkdir()
    binary = Path("var/dependencies/restic/restic.exe").resolve()
    config = dict(enabled=True, repository=str(repository), staging_root=str(tmp_path / "staging"),
        password_file="var/private/recovery.txt", restic_binary=str(binary), required_paths=["source"],
        exclude=["**/.env", "**/.env.*", "**/private/**"], command_timeout_seconds=30)
    return SystemBackup(workspace, config, AppSettings(_env_file=None))


def fake_capture(backup):
    capture = backup.stage / "capture"
    capture.mkdir(parents=True, exist_ok=True)
    (capture / "postgres.dump").write_bytes(b"fake-test-dump")
    write_json(capture / "manifest.json", {"scope": backup.config.get('scope', 'full-system'),
        "market_data_store_backend": backup.settings.market_data_store_backend,
        "files": {"postgres.dump": {"sha256": file_hash(capture/"postgres.dump")}}})
    pending = dict(capture=str(capture), manifest_sha256=file_hash(capture/"manifest.json"),
                   captured_at="2026-10-07T02:00:00+00:00", sources=[str(backup.workspace/"source")])
    write_json(backup.local / "pending.json", pending)
    return pending


def test_offline_is_deferred_before_capture_and_recovers_pending_generation(backup, monkeypatch):
    original = backup.repository
    backup.repository = original / "offline/child"
    monkeypatch.setattr(backup, "capture", lambda: pytest.fail("Must not capture when disconnected"))
    assert backup.once() is None
    assert backup.state["status"] == "deferred"
    assert not (backup.local / "pending.json").exists()
    backup.repository = original
    pending = fake_capture(backup)
    monkeypatch.setattr(backup, "initialize_repository", lambda: None)
    monkeypatch.setattr(backup, "publish", lambda item: "resumed" if item == pending else pytest.fail("Lost pending capture"))
    assert backup.once() == "resumed"


def test_incomplete_snapshot_does_not_replace_last_complete_and_retries(backup, monkeypatch):
    fake_capture(backup)
    backup.state.update(snapshot="prior-complete", status="complete")
    monkeypatch.setattr(backup, "initialize_repository", lambda: None)
    calls = []
    def incomplete(*args):
        calls.append(args)
        if args[0] == "backup":
            raise RuntimeError("restic exit 3: unreadable source")
        return ""
    monkeypatch.setattr(backup, "restic", incomplete)
    assert backup.once() is None
    assert backup.state["snapshot"] == "prior-complete"
    assert backup.state["status"] == "deferred"
    assert (backup.local / "pending.json").exists()
    assert not any(c[0] == "tag" for c in calls)


def test_existing_repository_without_key_cannot_be_reinitialized(backup):
    backup.repository.mkdir()
    (backup.repository / "config").write_text("existing encrypted repository")
    backup.binary = backup.workspace / "binary"
    backup.binary.touch()
    with pytest.raises(RuntimeError, match="recovery key"):
        backup.initialize_repository()
    assert not backup.password.exists()


def test_one_shot_backup_is_not_blocked_by_the_calculation_lock(backup, monkeypatch):
    monkeypatch.setattr(backup, "initialize_repository", lambda: None)
    monkeypatch.setattr(backup, "capture", lambda: fake_capture(backup))

    def publish(pending):
        # The capture lock is held for the whole upload so retention/maintenance
        # cannot delete files that restic is reading; the calculation lock is not
        # taken, so an upload can never block strategy recalculation.
        with pytest.raises(OSError):
            with exclusive_lock(backup.local / "capture.lock"):
                pytest.fail("capture lock must stay held during the upload")
        return "ran"

    monkeypatch.setattr(backup, "publish", publish)
    with exclusive_lock(backup.workspace / "var/run/research-retention.lock"):
        assert backup.once() == "ran"
    assert backup.state["status"] != "deferred"


def test_command_without_output_stalls_instead_of_holding_locks(backup):
    backup.config["stall_timeout_seconds"] = 1
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="no output"):
        backup.command([sys.executable, "-c", "import time; time.sleep(30)"])
    assert time.monotonic() - started < 15


def test_command_output_prevents_the_stall_guard(backup):
    script = "import time\nfor index in range(6):\n    print(index, flush=True)\n    time.sleep(.2)"
    output = backup.command([sys.executable, "-c", script], stall_timeout=1)
    assert output.strip().splitlines()[-1] == "5"


def test_worker_resume_reports_fresh_recovery_without_recapturing(backup, monkeypatch):
    import importlib.util
    from datetime import UTC, datetime
    script = Path(__file__).resolve().parents[1]/'scripts/system_backup.py'
    spec = importlib.util.spec_from_file_location('recovery_worker_resume_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = backup.workspace/'config/system-backup.json'
    write_json(config, backup.config)
    backup.config.update(interval_seconds=3600, retry_seconds=2)
    backup.state.update(status='paused', snapshot='a'*64, captured_at=datetime.now(UTC).isoformat(),
                        completed_at=datetime.now(UTC).isoformat())
    observed = []
    monkeypatch.setattr(backup, 'heartbeat', lambda: observed.append(backup.state['status']))
    monkeypatch.setattr(backup, 'once', lambda: pytest.fail('Fresh recovery must wait for its normal interval'))
    monkeypatch.setattr(module, 'ROOT', backup.workspace)
    monkeypatch.setattr(module, 'SystemBackup', lambda *args: backup)
    monkeypatch.setattr(module.time, 'sleep', lambda _: backup.stop_path.touch())
    monkeypatch.setattr(sys, 'argv', ['system_backup.py', 'worker', '--config', str(config)])
    monkeypatch.chdir(backup.workspace)
    assert module.main() == 0
    assert observed[:2] == ['complete', 'complete']
    assert observed[-1] == 'paused'


def test_pending_manifest_tampering_fails_before_upload(backup):
    pending = fake_capture(backup)
    (backup.stage / "capture/manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="identity changed"):
        backup.publish(pending)


def test_scope_change_cannot_resume_a_broad_pending_capture(backup):
    pending = fake_capture(backup)
    backup.config['scope'] = 'recovery-v1'
    with pytest.raises(ValueError, match='scope differs'):
        backup.publish(pending)


def test_recovery_scope_keeps_declared_payload_but_omits_runtime_and_old_research(backup, tmp_path):
    backup.config.update(scope='recovery-v1', input_manifests=['frozen.json'])
    frozen = backup.workspace/'experiment'
    frozen.mkdir()
    payload = frozen/'needed.npz'
    payload.write_bytes(b'frozen required input')
    (frozen/'discardable.log').write_text('exploratory replay')
    write_json(backup.workspace/'frozen.json', dict(files={'experiment/needed.npz':file_hash(payload)}))
    hot = tmp_path/'hot'
    hot.mkdir()
    policy = backup.workspace/'policy.json'
    write_json(policy, dict(hot_spool_root=str(hot)))
    backup.settings = backup.settings.model_copy(update=dict(market_data_storage_policy_path=policy,
                                                            lean_runtime_backend='docker'))
    sources, dependencies = backup.source_paths(dict(files={}, governed_roots=[]))
    assert payload in sources and frozen not in sources
    assert frozen/'discardable.log' not in sources
    assert dependencies['files'][str(payload)] == file_hash(payload)


def test_pruning_requires_restore_acceptance_and_keeps_current_capture(backup, monkeypatch):
    import json
    from systematic_trading.storage.recovery_checks import recovery_policy_hash
    backup.config.update(scope='recovery-v1')
    backup.state.update(status='complete', snapshot='a'*64)
    proof = backup.local/'restore-acceptance.json'
    write_json(proof, dict(passed=False, repository=str(backup.repository), scope='recovery-v1'))
    with pytest.raises(ValueError, match='passed restore'):
        backup.prune()
    write_json(proof, dict(passed=True, repository=str(backup.repository), scope='recovery-v1',
                          policy_sha256=recovery_policy_hash(backup.config)))
    monkeypatch.setattr(backup, 'restic', lambda *args: json.dumps([
        dict(id='a'*64, tags=['system-complete','recovery-v1','capture-current'])]))
    calls = []
    monkeypatch.setattr(backup, 'command', lambda args, **kwargs: calls.append(args))
    backup.prune(dry_run=True)
    assert '--dry-run' in calls[0] and '--prune' not in calls[0]
    assert calls[0][calls[0].index('--group-by')+1] == 'host'
    assert calls[0][calls[0].index('--keep-tag')+1] == 'capture-current'
    backup.state['status'] = 'deferred'
    with pytest.raises(ValueError, match='current complete'):
        backup.prune()
    backup.state['status'] = 'paused'
    backup.config['exclude'].append('**/newly-excluded/**')
    with pytest.raises(ValueError, match='coverage changed'):
        backup.prune()


def test_pruning_cannot_forget_before_replacement_locator_is_published(backup, monkeypatch):
    import json
    from contextlib import nullcontext
    from types import SimpleNamespace
    from systematic_trading.storage.recovery_checks import recovery_policy_hash
    backup.config['scope'] = 'recovery-v1'
    backup.state.update(status='complete', snapshot='a'*64)
    write_json(backup.local/'restore-acceptance.json', dict(passed=True, repository=str(backup.repository),
        scope='recovery-v1', policy_sha256=recovery_policy_hash(backup.config), snapshot='a'*64))
    write_json(backup.workspace/'config/database-sync.json', dict(recovery_only=True, postgres=False, sqlite_paths=[]))
    monkeypatch.setattr(backup, 'restic', lambda *args: json.dumps([
        dict(tags=['system-complete','recovery-v1','capture-current'])]))
    def unavailable():
        raise OSError('NAS locator is busy')
    sync = SimpleNamespace(local_lock=nullcontext, lock=unavailable)
    monkeypatch.setattr('systematic_trading.storage.optional_sync.OptionalNasSync', lambda *args: sync)
    monkeypatch.setattr(backup, 'command', lambda *args, **kwargs: pytest.fail('Must publish replacement before forgetting'))
    with pytest.raises(OSError, match='locator is busy'):
        backup.prune()


def test_recycle_cleanup_requires_a_successful_live_repository_check(backup, monkeypatch):
    import json
    from systematic_trading.storage.recovery_checks import recovery_policy_hash
    import systematic_trading.storage.recovery_retention as retention
    backup.config.update(scope='recovery-v1', recycle_root='configured-bin')
    backup.state.update(status='complete', snapshot='a'*64)
    write_json(backup.local/'restore-acceptance.json', dict(passed=True, repository=str(backup.repository),
        scope='recovery-v1', policy_sha256=recovery_policy_hash(backup.config), snapshot='a'*64))
    calls = []
    def restic(*args):
        if args[0] == 'snapshots':
            return json.dumps([dict(id='a'*64, tags=['system-complete','recovery-v1','capture-current'])])
        calls.append(args[0])
        raise RuntimeError('missing live repository pack')
    monkeypatch.setattr(backup, 'restic', restic)
    monkeypatch.setattr(backup, 'command', lambda args, **kwargs: calls.append(args[1]))
    monkeypatch.setattr(retention, 'validate_recycle_mapping', lambda *args: None)
    monkeypatch.setattr(retention, 'purge_recycled_backups', lambda *args, **kwargs: pytest.fail('Must retain trash for recovery'))
    with pytest.raises(RuntimeError, match='missing live'):
        backup.prune()
    assert calls == ['forget', 'prune', 'check']


def test_legacy_pending_capture_cannot_be_published_as_native(backup, monkeypatch):
    backup.settings = backup.settings.model_copy(update={"market_data_store_backend": "parquet"})
    pending = fake_capture(backup)
    manifest_path = backup.stage / "capture/manifest.json"
    manifest = read_json(manifest_path)
    manifest.pop("market_data_store_backend")
    manifest["clickhouse"] = {"databases": ["legacy"]}
    write_json(manifest_path, manifest)
    pending["manifest_sha256"] = file_hash(manifest_path)
    monkeypatch.setattr(backup, "restic", lambda *a: pytest.fail("Must not upload mismatched state"))
    with pytest.raises(ValueError, match="different analytics backend"):
        backup.publish(pending)
    assert manifest_path.exists()


def test_reachable_but_hung_smb_metadata_is_bounded_and_deferred(backup, monkeypatch):
    backup.binary = backup.workspace / "binary"
    backup.binary.touch()
    calls = []
    def hung(args, **kwargs):
        calls.append(kwargs)
        raise TimeoutError("SMB metadata hung")
    monkeypatch.setattr(backup, "command", hung)
    assert backup.once() is None
    assert calls == [{"timeout":30}]
    assert backup.state["status"] == "deferred"
    assert not (backup.local / "pending.json").exists()


def test_nonempty_damaged_repository_is_not_reinitialized(backup):
    backup.binary = backup.workspace / "binary"
    backup.binary.touch()
    backup.repository.mkdir()
    (backup.repository/"irreplaceable-data").write_bytes(b"preserve")
    with pytest.raises(RuntimeError, match="contains data"):
        backup.initialize_repository()
    assert not backup.password.exists()


def test_restore_cannot_overwrite_sources_or_accept_abbreviated_id(backup):
    with pytest.raises(ValueError, match="exact complete"):
        backup.restore_files("12345678", backup.workspace / "source")
    with pytest.raises(ValueError, match="empty target"):
        backup.restore_files("a"*64, backup.workspace / "source")
    with pytest.raises(ValueError, match="overlaps"):
        backup.restore_files("a"*64, backup.workspace / "source/new-child")


def test_restore_groups_only_committed_native_fragments(backup,tmp_path,monkeypatch):
    import json
    lake=tmp_path/'native-lake'
    backup.settings=backup.settings.model_copy(update={'native_analytics_root':lake})
    parquet=lake/'parquet'
    calls=[]
    def restic(*args):
        calls.append(args)
        if args[0]=='snapshots':
            return json.dumps([dict(tags=['system-complete'],paths=[str(parquet/'a.parquet'),str(parquet/'b.parquet')])])
        if args[0]=='ls':return json.dumps(dict(path=args[-1],type='dir'))
        return ''
    monkeypatch.setattr(backup,'restic',restic)
    target=tmp_path/'restore'
    backup.restore_files('a'*64,target)
    assert len([c for c in calls if c[0]=='restore'])==1
    assert read_json(target/'restore-map.json')[0]['original']==str(parquet)
    with pytest.raises(ValueError,match='overlaps'):
        backup.restore_files('a'*64,lake/'empty-child')


def test_recovery_restore_batches_selected_data_drive_in_one_verified_read(backup, tmp_path, monkeypatch):
    import json
    backup.workspace = Path('D:/test-recovery-workspace')
    calls = []
    def restic(*args):
        calls.append(args)
        if args[0] == 'snapshots':
            return json.dumps([dict(tags=['system-complete','recovery-v1'],
                                    paths=['D:/test-recovery-workspace/config','D:/lake/parquet/a.parquet'])])
        return ''
    monkeypatch.setattr(backup, 'restic', restic)
    target = tmp_path/'batched-restore'
    backup.restore_files('a'*64, target)
    restores = [c for c in calls if c[0] == 'restore']
    assert len(restores) == 1 and restores[0][1] == 'a'*64+':/D'
    assert '--verify' in restores[0]
    assert read_json(target/'restore-map.json')[0]['original'] == 'D:\\'
    assert read_json(target/'restore-source.json') == dict(snapshot='a'*64, repository=str(backup.repository))


def test_staging_cannot_contain_source_or_be_inside_source(backup):
    for target in [backup.workspace, backup.workspace/"source/nested"]:
        config = dict(backup.config, staging_root=str(target))
        with pytest.raises(ValueError, match="staging"):
            SystemBackup(backup.workspace, config, backup.settings)


def test_shutdown_cancels_slow_network_child(backup):
    timer = threading.Timer(.5, backup.stop_path.touch)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(BackupStopped):
            backup.command([sys.executable, "-c", "import time; time.sleep(60)"])
    finally:
        timer.join()
    assert time.monotonic()-started < 5


def test_source_inventory_updates_heartbeat_and_honors_stop(backup, monkeypatch):
    beats = []
    monkeypatch.setattr(backup, 'heartbeat', lambda: beats.append(True))
    backup.inventory_progress()
    assert beats == [True]
    backup.stop_path.touch()
    backup._inventory_heartbeat_at = 0
    with pytest.raises(BackupStopped, match='inventory paused'):
        backup.inventory_progress()


def test_explicit_worker_pause_is_honored_by_automatic_supervision(backup, monkeypatch):
    import runpy
    module = runpy.run_path("scripts/system_backup.py")
    config = backup.workspace / "backup-config.json"
    write_json(config, backup.config)
    module["stop_worker"](backup.workspace, explicit=True)
    assert (backup.run_dir/"system_backup.paused").exists()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: pytest.fail("Explicit pause must suppress automatic start"))
    module["start_worker"](backup.workspace, config)


def test_real_restic_backup_readback_restore_and_incremental_catchup(backup, monkeypatch, tmp_path):
    if not backup.binary.exists():
        pytest.skip("Pinned restic binary not provisioned")
    backup.config["exclude"] = read_json(Path("config/system-backup.json"))["exclude"]
    rollback = backup.workspace / "source/var/database-sync/before-restore-test/rollback.txt"
    rollback.parent.mkdir(parents=True)
    rollback.write_text("retain divergent historical state")
    checkpoint = backup.workspace / "source/var/database-sync/checkpoints/old/redundant.txt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("routine checkpoint")
    write_json(backup.workspace / "source/var/database-sync/state.json", {"node":"old-machine-identity"})
    monkeypatch.setattr(backup, "capture", lambda: fake_capture(backup))
    first = backup.once()
    assert first, backup.state
    assert backup.state["status"] == "complete"
    assert not (backup.local / "pending.json").exists()
    target = tmp_path / "restored"
    backup.restore_files(first, target)
    assert [p.read_text() for p in target.rglob("data.txt")] == ["durable market evidence\n"]
    assert not list(target.rglob(".env*"))
    assert not list(target.rglob("recovery.txt"))
    assert len(list(target.rglob("rollback.txt"))) == 1
    assert not list(target.rglob("redundant.txt"))
    assert not list(target.rglob("state.json"))
    settings_file = next(target.rglob("runtime-settings.json"))
    saved_settings = read_json(settings_file)
    assert "postgres_port" in saved_settings["settings"]
    assert "clickhouse_password" not in saved_settings["settings"]
    assert "postgres_app_password" in saved_settings["reprovision_fields"]
    with pytest.raises(ValueError, match='same recorded snapshot'):
        backup.restore_files('f'*64, target, resume=True)
    next(target.rglob('data.txt')).write_text('interrupted partial restore')
    backup.restore_files(first, target, resume=True)
    assert [p.read_text() for p in target.rglob('data.txt')] == ['durable market evidence\n']
    (backup.workspace / "source/data.txt").write_text("offline-change\n")
    original = backup.repository
    backup.repository = original / "offline/child"
    assert backup.once() is None
    backup.repository = original
    # A newly committed fragment changes the root list. Retain incremental
    # comparison against the verified parent instead of rescanning all sources.
    fragment = tmp_path / 'committed-fragment.parquet'
    fragment.write_bytes(b'new immutable test fragment')
    def changed_source_capture():
        pending = fake_capture(backup)
        pending['sources'].append(str(fragment))
        write_json(backup.local / 'pending.json', pending)
        return pending
    monkeypatch.setattr(backup, 'capture', changed_source_capture)
    second = backup.once()
    assert second and second != first, backup.state
    backup.restore_files(second, tmp_path / "restored-second")
    assert [p.read_text() for p in (tmp_path/"restored-second").rglob("data.txt")] == ["offline-change\n"]
    assert backup.state['summary']['files_unmodified'] > 0
    backup.restic("check", "--read-data")


def test_real_retention_removes_old_complete_and_failed_candidates_but_keeps_manual(backup, monkeypatch):
    import json
    import socket
    from systematic_trading.storage.recovery_checks import recovery_policy_hash
    if not backup.binary.exists():
        pytest.skip('Pinned restic binary not provisioned')
    monkeypatch.setattr(backup, 'capture', lambda: fake_capture(backup))
    assert backup.once(), backup.state
    backup.restic('backup', '--host', socket.gethostname(), '--tag', 'system-candidate', str(backup.workspace/'source'))
    backup.restic('backup', '--host', socket.gethostname(), '--tag', 'manual', str(backup.workspace/'source'))
    backup.config['scope'] = 'recovery-v1'
    current = backup.once()
    assert current, backup.state
    write_json(backup.local/'restore-acceptance.json', dict(passed=True, scope='recovery-v1',
        repository=str(backup.repository), snapshot=current, policy_sha256=recovery_policy_hash(backup.config)))
    backup.prune(dry_run=True)
    assert len(json.loads(backup.restic('snapshots'))) == 4
    command = backup.command
    def interrupted_repack(args, **kwargs):
        if args[1] == 'prune':
            assert kwargs['env']['RESTIC_PROGRESS_FPS'] == '0.1'
            raise TimeoutError('Interrupted after forgetting references')
        return command(args, **kwargs)
    monkeypatch.setattr(backup, 'command', interrupted_repack)
    with pytest.raises(TimeoutError, match='Interrupted after forgetting'):
        backup.prune()
    monkeypatch.setattr(backup, 'command', command)
    assert len(json.loads(backup.restic('snapshots'))) == 2
    backup.prune()
    remaining = json.loads(backup.restic('snapshots'))
    assert len(remaining) == 2
    assert {row['id'] for row in remaining if 'system-complete' in row['tags']} == {current}
    assert any('manual' in row['tags'] for row in remaining)
    backup.restic('check', '--read-data')


def test_queue_native_snapshot_includes_consumers_and_acks_chunks(tmp_path, monkeypatch):
    import asyncio
    import json
    from types import SimpleNamespace
    ack = []
    requests = []
    class Message:
        def __init__(self, data, reply="ack"):
            self.data, self.reply = data, reply
        async def respond(self, data):
            ack.append(data)
    class Subscription:
        messages = iter([Message(b"part1"), Message(b"part2"), Message(b"", "")])
        async def next_msg(self, **kwargs):
            return next(self.messages)
        async def unsubscribe(self):
            pass
    class Connection:
        async def request(self, subject, data, **kwargs):
            requests.append((subject, json.loads(data)))
            payload = dict(streams=["ST_EVENTS"], total=1) if subject.endswith("NAMES") else dict(config={"name":"ST_EVENTS"}, state={"messages":2})
            return SimpleNamespace(data=json.dumps(payload).encode())
        def new_inbox(self):
            return "_INBOX.test"
        async def subscribe(self, *args, **kwargs):
            return Subscription()
        async def close(self):
            pass
    async def connect(**kwargs):
        return Connection()
    monkeypatch.setattr("nats.connect", connect)
    result = asyncio.run(snapshot_nats("nats://localhost:4222", tmp_path))
    assert (tmp_path/"ST_EVENTS.snapshot").read_bytes() == b"part1part2"
    assert requests[1][1]["no_consumers"] is False
    assert requests[1][1]["jsck"] is True and ack == [b"", b""]
    assert result["ST_EVENTS"]["state"]["messages"] == 2
