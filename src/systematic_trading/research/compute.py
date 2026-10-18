"""Serialize heavy calculations to preserve memory for storage and the operator."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import sys
from pathlib import Path

from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import encode


def resource_plan(jobs, *, host_cpus, engine, docker_cpus=None, docker_memory_bytes=None, available_memory_bytes=None):
    if jobs < 1 or engine not in {"lean", "python"}:
        raise ValueError("A supported engine and at least one calculation are required")
    cores = max(1, min(host_cpus, docker_cpus) if engine == "lean" else host_cpus)
    budget = min(2, cores)
    if available_memory_bytes is not None and available_memory_bytes < 10 * 1024**3:
        raise ValueError("Calculation deferred: need 4 GiB for one worker plus 6 GiB host memory headroom")
    memory_gib = (docker_memory_bytes or 0) / (1024**3)
    if engine == "lean":
        memory_workers = int(max(0, memory_gib-6)//4)
        if memory_workers < 1:
            raise ValueError("Calculations need 4 GiB per run plus 6 GiB service headroom")
        workers, per_run = 1, budget
    else:
        workers, per_run = 1, 1
    return dict(engine=engine, logical_cpus=host_cpus, usable_cpus=cores, cpu_budget=budget,
        workers=workers, cpus_per_run=per_run, memory_per_run_gib=4,
        docker_memory_gib=round(memory_gib,2) if engine == "lean" else None, jobs=jobs,
        model_fit_workers=budget, preparation_workers=1)


def host_available_memory():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total', 'page_available',
                                                      'virtual_total', 'virtual_available', 'extended')]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError('Could not measure host memory headroom')
        return status.available
    return os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')


def available_resources(jobs, engine):
    host = (getattr(os, "process_cpu_count", os.cpu_count)() or 1)
    if engine == "python":
        return resource_plan(jobs, host_cpus=host, engine=engine, available_memory_bytes=host_available_memory())
    from systematic_trading.config import AppSettings
    if AppSettings().lean_runtime_backend=='native':
        result=resource_plan(jobs,host_cpus=host,engine='python',available_memory_bytes=host_available_memory())
        result.update(engine='lean',runtime='windows-native',cpus_per_run=min(2,host),memory_per_run_gib=4,
                      model_fit_workers=1 if os.name=='nt' else result['model_fit_workers'])
        return result
    result = subprocess.run(["docker", "info", "--format", '{"cpus":{{.NCPU}},"memory":{{.MemTotal}}}'],
        capture_output=True, text=True, check=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    limits = json.loads(result.stdout)
    return resource_plan(jobs, host_cpus=host, engine=engine,
        docker_cpus=int(limits["cpus"]), docker_memory_bytes=int(limits["memory"]),
        available_memory_bytes=host_available_memory())


def parallel_results(jobs, calculate, workers):
    """The parent consumes results; stores/publication never run on pool threads."""
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tracked-backtest") as pool:
        futures = {pool.submit(calculate, key): key for key in jobs}
        try:
            for future in as_completed(futures):
                yield futures[future], future.result()
        finally:
            for future in futures:
                future.cancel()


def frozen_input(path, value):
    payload = encode(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf8") != payload:
            raise ValueError("Calculation preparation input changed: " + str(path))
    else:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf8")
        temporary.replace(path)
    return dict(path=str(path.resolve()), sha256=sha256(path))


def prepare_in_process(request_path):
    if os.name=='nt':
        from uuid import uuid4
        from systematic_trading.lean.windows_worker import run
        from systematic_trading.lean.contracts import verify_bundle
        from systematic_trading.runtime_io import exclusive_lock
        request=json.loads(request_path.read_text(encoding='utf8'))
        bundle=Path(request['bundle']).resolve()
        source=Path(__file__).resolve().parents[2]
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source.parent,text=True,
            creationflags=subprocess.CREATE_NO_WINDOW).strip()
        bundle.parent.mkdir(parents=True,exist_ok=True)
        with exclusive_lock(bundle.with_name(bundle.name+'.lock')):
            if bundle.exists():
                verify_bundle(bundle)
                return
            output=bundle.with_name(bundle.name+'.worker-'+uuid4().hex)
            output.mkdir()
            inputs=[Path(request_path).resolve()]+[Path(request[k]['path']).resolve()
                for k in ('inputs','models','usd_models') if request.get(k)]
            run([sys.executable,'-B','-m','systematic_trading.research.calculation_worker',
                 str(request_path.resolve()),str(output/'bundle'),commit],output=output,
                read_roots=[source,Path(sys.prefix),Path(sys.base_prefix),*inputs],
                environment={'PYTHONPATH':str(source)},memory_bytes=4*1024**3,cpus=2,timeout=900)
            verify_bundle(output/'bundle')
            (output/'bundle').rename(bundle)
        return
    # Keep app/database/broker credentials out of calculation subprocesses.
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "TEMP", "TMP", "LANG", "LC_ALL"}
    environment = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    source = Path(__file__).resolve().parents[2]
    environment.update(PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
        OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    with request_path.with_suffix(".log").open("a", encoding="utf8") as log:
        subprocess.run([sys.executable, "-B", "-m", "systematic_trading.research.calculation_worker", str(request_path.resolve())],
            cwd=source.parent, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=900, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
