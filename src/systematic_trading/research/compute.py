"""Bound independent calculations by CPU capacity and the Docker memory budget."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import sys
from pathlib import Path

from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import encode


def resource_plan(jobs, *, host_cpus, engine, docker_cpus=None, docker_memory_bytes=None):
    if jobs < 1 or engine not in {"lean", "python"}:
        raise ValueError("A supported engine and at least one calculation are required")
    cores = max(1, min(host_cpus, docker_cpus) if engine == "lean" else host_cpus)
    budget = max(1, cores-1)  # Keep operations/UI capacity outside the research pool.
    memory_gib = (docker_memory_bytes or 0) / (1024**3)
    if engine == "lean":
        memory_workers = int(max(0, memory_gib-2)//4)
        if memory_workers < 1:
            raise ValueError("Native calculations need 4 GiB per run plus 2 GiB Docker service headroom")
        workers = min(jobs, max(1, budget//2), memory_workers)
        per_run = max(1, budget//workers)
    else:
        workers, per_run = min(jobs, budget), 1
    return dict(engine=engine, logical_cpus=host_cpus, usable_cpus=cores, cpu_budget=budget,
        workers=workers, cpus_per_run=per_run, memory_per_run_gib=4 if engine == "lean" else None,
        docker_memory_gib=round(memory_gib,2) if engine == "lean" else None, jobs=jobs,
        model_fit_workers=host_cpus, preparation_workers=min(jobs,budget))


def available_resources(jobs, engine):
    host = (getattr(os, "process_cpu_count", os.cpu_count)() or 1)
    if engine == "python":
        return resource_plan(jobs, host_cpus=host, engine=engine)
    result = subprocess.run(["docker", "info", "--format", '{"cpus":{{.NCPU}},"memory":{{.MemTotal}}}'],
        capture_output=True, text=True, check=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    limits = json.loads(result.stdout)
    return resource_plan(jobs, host_cpus=host, engine=engine,
        docker_cpus=int(limits["cpus"]), docker_memory_bytes=int(limits["memory"]))


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
