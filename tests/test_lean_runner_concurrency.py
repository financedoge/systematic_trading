"""The LEAN runner's concurrent engine contract.

Both engines are independent — LEAN writes ``economic.json``, the oracle writes ``reference.json``,
and parity compares them only once both exist — so they are started together. These tests pin the
properties that make that safe: real overlap, each engine's own wall time, and a failing engine
terminating its partner rather than leaving it running.
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest

from systematic_trading.lean import runner


def _spawn(tmp_path, label, code):
    process, log = runner._spawn_logged([sys.executable, '-c', code], cwd=tmp_path, environment=None,
                                        log_path=tmp_path / f'{label}.log')
    return process, log


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
