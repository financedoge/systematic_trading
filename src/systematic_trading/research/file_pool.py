"""Parallel CPU jobs inside one AppContainer/Job, using files instead of named pipes.

Children inherit the parent's restricted token, environment and lifetime Job.
Only independent decisions/fits are distributed; a replay stays ordered.
"""
from contextlib import ExitStack
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def worker_count(jobs, *, input_bytes=0, max_workers=None, available_memory_bytes=None):
    """Use available RAM to size concurrency, without a per-job memory ceiling.

    Each child has an estimated 256 MiB runtime plus four times serialized input.
    Memory pressure reduces fan-out to one; it never rejects the whole stage.
    Windows controls commit/paging and permits a running job to grow beyond this
    launch-time estimate. An explicit worker request still bounds concurrency.
    """
    if jobs < 0 or input_bytes < 0 or (max_workers is not None and max_workers < 1):
        raise ValueError('Invalid calculation pool capacity')
    cpus = getattr(os, 'process_cpu_count', os.cpu_count)() or 1
    if available_memory_bytes is None:
        from systematic_trading.research.compute import host_available_memory
        available_memory_bytes = host_available_memory()
    decoded = input_bytes * 4
    capacity = max(1, available_memory_bytes // (256 * 1024**2 + decoded))
    return max(1, min(max(1, jobs), cpus, capacity, max_workers or cpus))


def _reference(function):
    if function is None:
        return None
    module = function.__module__
    if module == '__main__':
        module = function.__globals__['__spec__'].name
    return [module, function.__name__]


def _resolve(reference):
    return getattr(importlib.import_module(reference[0]), reference[1])


def file_process_map(function, items, *, directory, workers, initializer=None, initargs=(), timeout=900):
    """Return ordered results or fail the complete stage and reap every child."""
    items = list(items)
    if workers < 1:
        raise ValueError('Calculation workers must be positive')
    if not items:
        return []
    workers = min(workers, len(items))
    if workers == 1:
        if initializer:
            initializer(*initargs)
        return [function(item) for item in items]
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    processes, paths = [], []
    started = time.monotonic()
    with ExitStack() as stack:
        try:
            for lane in range(workers):
                request = directory / f'{lane}.request.json'
                result = directory / f'{lane}.result.json'
                payload = dict(function=_reference(function), initializer=_reference(initializer),
                    initargs=initargs, items=list(enumerate(items))[lane::workers])
                request.write_text(json.dumps(payload), encoding='utf8')
                log = stack.enter_context((directory / f'{lane}.log').open('wb'))
                command = [sys.executable, '-B', '-m', __name__, str(request), str(result)]
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, close_fds=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                processes.append(process)
                paths.append((request, result))
            pending = set(processes)
            while pending:
                for process in list(pending):
                    code = process.poll()
                    if code is not None:
                        pending.remove(process)
                        if code:
                            raise subprocess.CalledProcessError(code, process.args)
                if pending:
                    if time.monotonic() - started >= timeout:
                        raise subprocess.TimeoutExpired('calculation file pool', timeout)
                    time.sleep(0.05)
            rows = [row for _, result in paths for row in json.loads(result.read_text(encoding='utf8'))]
            if sorted(row[0] for row in rows) != list(range(len(items))):
                raise ValueError('Incomplete calculation pool output')
            results = [value for _, value in sorted(rows)]
            metrics = [json.loads(result.with_suffix('.metrics.json').read_text(encoding='utf8')) for _, result in paths]
            (directory/'pool.json').write_text(json.dumps(dict(workers=workers,jobs=len(items),
                elapsed_seconds=time.monotonic()-started,children=metrics)),encoding='utf8')
            # Disposable transport copies; durable final artifacts are owned by
            # the caller. Keep child logs for diagnosis without duplicating fits.
            for request, result in paths:
                request.unlink()
                result.unlink()
                result.with_suffix('.metrics.json').unlink()
            return results
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
            for process in processes:
                process.wait()


def child(request, result):
    started, cpu = time.monotonic(), time.process_time()
    payload = json.loads(request.read_text(encoding='utf8'))
    if payload['initializer']:
        _resolve(payload['initializer'])(*payload['initargs'])
    function = _resolve(payload['function'])
    rows = [(index, function(item)) for index, item in payload['items']]
    temporary = result.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows), encoding='utf8')
    temporary.replace(result)
    result.with_suffix('.metrics.json').write_text(json.dumps(dict(pid=os.getpid(),jobs=len(rows),
        elapsed_seconds=time.monotonic()-started,cpu_seconds=time.process_time()-cpu)),encoding='utf8')


if __name__ == '__main__':
    child(Path(sys.argv[1]), Path(sys.argv[2]))
