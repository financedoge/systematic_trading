"""The LEAN runner's concurrent engine contract.

Both engines are independent — LEAN writes ``economic.json``, the oracle writes ``reference.json``,
and parity compares them only once both exist — so they are started together. These tests pin the
properties that make that safe: real overlap, each engine's own wall time, and a failing engine
terminating its partner rather than leaving it running.

Cleanup is part of that contract too. A failure *after* the engines were launched — a Docker engine
that cannot even spawn, an image inspection that fails, a timeout — must terminate and reap every
launched child before the failure is raised, so a synthetic sleeper never survives the call.
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from systematic_trading.lean import runner
from systematic_trading.lean.contracts import BacktestRunSpec, sha256, write_json

IMAGE = 'quantconnect/lean@sha256:' + 'a' * 64
SLEEPER = ('import pathlib, sys, time\n'
           'beat = pathlib.Path(sys.argv[1])\n'
           'for _ in range(2400):\n'
           '    beat.write_text(str(time.time()))\n'
           '    time.sleep(0.05)\n')


def _spawn(tmp_path, label, code):
    process, log = runner._spawn_logged([sys.executable, '-c', code], cwd=tmp_path, environment=None,
                                        log_path=tmp_path / f'{label}.log')
    return process, log


def _bundle(tmp_path):
    """A frozen bundle that verifies, plus the not-yet-existing output path run_bundle requires."""
    bundle, target = tmp_path / 'bundle', tmp_path / 'run'
    bundle.mkdir()
    spec = BacktestRunSpec(start_date='2025-01-02', end_date='2025-12-31', warmup_start='2023-01-01',
                           strategy_hash='fixture', source_hash='fixture', repository_commit='fixture')
    write_json(bundle / 'spec.json', spec.model_dump())
    write_json(bundle / 'manifest.json', {'schema_version': 1,
                                          'files': {'spec.json': sha256(bundle / 'spec.json')}})
    return bundle, target


def _docker_run(*, inspect_fails=False):
    """Stand in for ``subprocess.run``: fail the inspection, accept the container removal."""
    def run(command, **kwargs):
        if command[1] == 'image':
            if inspect_fails:
                raise subprocess.CalledProcessError(1, command, output='', stderr='Error: No such image')
            return SimpleNamespace(returncode=0, stdout=json.dumps([{'Id': 'sha256:fixture'}]), stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    return run


class _SyntheticEngines:
    """Real OS processes standing in for the two engines, beating a file until they are killed.

    ``runner.subprocess.Popen`` is redirected here, so the engine the runner believes it launched is
    a harmless sleeper. The heartbeat file is how the test proves the sleeper is really gone even
    when the runner has lost its only handle to it, and the handle itself proves it was reaped.
    """

    def __init__(self, tmp_path, monkeypatch, *, fail_docker_spawn=False):
        self.tmp_path, self.fail_docker_spawn = tmp_path, fail_docker_spawn
        self.processes, self.beats = {}, {}
        self._popen = subprocess.Popen                  # captured before the module attribute is patched
        monkeypatch.setattr(runner.subprocess, 'Popen', self.launch)

    def launch(self, command, **kwargs):
        if self.fail_docker_spawn and command[0] == 'docker':
            raise FileNotFoundError('[WinError 2] the docker client is not installed')
        label = 'lean' if command[0] == 'docker' else 'reference'
        beat = self.tmp_path / f'{label}.beat'
        self.beats[label] = beat
        self.processes[label] = self._popen([sys.executable, '-c', SLEEPER, str(beat)], **kwargs)
        # Do not return until the sleeper is demonstrably alive and beating, so a later failure is
        # always raised against a running child rather than a Python interpreter still starting up.
        deadline = time.perf_counter() + 15
        while not beat.exists() and self.processes[label].poll() is None and time.perf_counter() < deadline:
            time.sleep(0.02)
        assert beat.exists(), f'the synthetic {label} engine never started'
        return self.processes[label]

    def live(self):
        return [label for label, process in self.processes.items() if process.poll() is None]

    def assert_no_live_child(self):
        assert self.processes, 'no synthetic engine was launched, so cleanup was not exercised'
        assert not self.live(), f'engines still running after the failure: {self.live()}'
        for label, process in self.processes.items():
            assert process.returncode is not None, f'the {label} engine was never reaped'
        before = {label: beat.read_text() for label, beat in self.beats.items()}
        time.sleep(0.6)                                 # a live sleeper beats every 50ms, a dead one cannot
        assert {label: beat.read_text() for label, beat in self.beats.items()} == before, \
            'a synthetic engine is still running after the failure'

    def stop(self):
        """Teardown that cannot leak a sleeper even when an assertion above failed."""
        for process in self.processes.values():
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass


def test_two_engines_overlap_and_each_reports_its_own_wall_time(tmp_path):
    launched, logs = {}, []
    for label in ('a', 'b'):
        process, log = _spawn(tmp_path, label, 'import time; time.sleep(0.9)')
        logs.append(log)
        launched[label] = (process, time.perf_counter())
    started = time.perf_counter()
    wall = runner._await_processes(launched, timeout_seconds=30)
    elapsed = time.perf_counter() - started
    for log in logs:
        log.close()
    assert elapsed < 1.7, elapsed                       # overlapped, not 1.8s of serial sleeping
    assert 0.85 <= wall['a'] < 1.7 and 0.85 <= wall['b'] < 1.7
    assert set(wall) == {'a', 'b'}


def test_a_failing_engine_terminates_its_partner(tmp_path):
    slow, slow_log = _spawn(tmp_path, 'slow', 'import time; time.sleep(60)')
    fast, fast_log = _spawn(tmp_path, 'fast', 'raise SystemExit(3)')
    started = time.perf_counter()
    with pytest.raises(subprocess.CalledProcessError) as error:
        runner._await_processes({'slow': (slow, time.perf_counter()), 'fast': (fast, time.perf_counter())},
                                timeout_seconds=30)
    elapsed = time.perf_counter() - started
    slow_log.close()
    fast_log.close()
    assert error.value.returncode == 3
    assert elapsed < 15, elapsed                        # the partner was terminated, not awaited
    assert slow.poll() is not None


def test_a_timeout_terminates_every_engine(tmp_path):
    first, first_log = _spawn(tmp_path, 'first', 'import time; time.sleep(60)')
    second, second_log = _spawn(tmp_path, 'second', 'import time; time.sleep(60)')
    started = time.perf_counter()
    with pytest.raises(subprocess.TimeoutExpired):
        runner._await_processes({'first': (first, time.perf_counter()), 'second': (second, time.perf_counter())},
                                timeout_seconds=2)
    elapsed = time.perf_counter() - started
    first_log.close()
    second_log.close()
    assert elapsed < 15, elapsed
    assert first.poll() is not None and second.poll() is not None


# --- cleanup after a launch that never became a run ---------------------------

def test_a_failed_second_spawn_leaves_no_live_engine(tmp_path, monkeypatch):
    """The oracle is already running when the Docker engine cannot even be started."""
    engines = _SyntheticEngines(tmp_path, monkeypatch, fail_docker_spawn=True)
    monkeypatch.setattr(runner.subprocess, 'run', _docker_run())
    bundle, target = _bundle(tmp_path)
    try:
        with pytest.raises(subprocess.SubprocessError, match='Publication withheld'):
            runner.run_bundle(bundle=bundle, output=target, image=IMAGE, timeout_seconds=30, runtime='docker')
        assert engines.live() == []                     # the oracle was terminated and reaped
        engines.assert_no_live_child()
    finally:
        engines.stop()
    assert json.loads((target / 'run.json').read_text(encoding='utf8'))['status'] == 'failed'


def test_a_failed_image_inspection_reaps_both_engines_before_hashing(tmp_path, monkeypatch):
    """Both engines are up when the pinned image cannot be inspected."""
    engines = _SyntheticEngines(tmp_path, monkeypatch)
    monkeypatch.setattr(runner.subprocess, 'run', _docker_run(inspect_fails=True))
    bundle, target = _bundle(tmp_path)
    live_at_hash = []
    artifact_sha256 = runner.sha256

    def recording_sha256(path):
        if Path(path).parent == target and engines.live():
            live_at_hash.append(str(path))
        return artifact_sha256(path)

    monkeypatch.setattr(runner, 'sha256', recording_sha256)
    try:
        with pytest.raises(subprocess.SubprocessError, match='Publication withheld') as error:
            runner.run_bundle(bundle=bundle, output=target, image=IMAGE, timeout_seconds=30, runtime='docker')
        assert isinstance(error.value.__cause__, subprocess.CalledProcessError)
        engines.assert_no_live_child()
        assert live_at_hash == [], f'artifacts were hashed while engines ran: {live_at_hash}'
    finally:
        engines.stop()


def test_a_timeout_leaves_no_live_engine(tmp_path, monkeypatch):
    engines = _SyntheticEngines(tmp_path, monkeypatch)
    monkeypatch.setattr(runner.subprocess, 'run', _docker_run())
    bundle, target = _bundle(tmp_path)
    try:
        with pytest.raises(subprocess.SubprocessError, match='Publication withheld') as error:
            runner.run_bundle(bundle=bundle, output=target, image=IMAGE, timeout_seconds=1.5, runtime='docker')
        assert isinstance(error.value.__cause__, subprocess.TimeoutExpired)
        engines.assert_no_live_child()
    finally:
        engines.stop()


def test_cleanup_is_idempotent_for_exited_and_already_reaped_engines(tmp_path):
    exited, exited_log = _spawn(tmp_path, 'exited', 'raise SystemExit(0)')
    reaped, reaped_log = _spawn(tmp_path, 'reaped', 'raise SystemExit(0)')
    assert reaped.wait(timeout=30) == 0                 # already waited for, so already reaped
    live, live_log = _spawn(tmp_path, 'live', 'import time; time.sleep(60)')
    runner._terminate({'exited': exited, 'reaped': reaped, 'live': live})
    runner._terminate({'exited': exited, 'reaped': reaped, 'live': live})   # repeat: still no error
    for log in (exited_log, reaped_log, live_log):
        log.close()
    assert exited.poll() == 0 and reaped.poll() == 0
    assert live.poll() is not None, 'a live engine survived cleanup'
