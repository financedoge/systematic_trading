from threading import Barrier, Lock

import pytest

from systematic_trading.research.compute import resource_plan, parallel_results


def test_native_workers_use_cpu_budget_without_overcommitting_docker_memory():
    plan=resource_plan(5,host_cpus=16,engine="lean",docker_cpus=16,docker_memory_bytes=16527273984)
    assert plan["workers"]==1 and plan["cpus_per_run"]==2
    assert plan["preparation_workers"]==1 and plan["model_fit_workers"]==2
    assert plan["cpu_budget"]==2
    assert plan["workers"]*plan["memory_per_run_gib"]+6 <= plan["docker_memory_gib"]
    limited=resource_plan(5,host_cpus=16,engine="lean",docker_cpus=4,docker_memory_bytes=10*1024**3)
    assert limited["workers"]==1 and limited["cpus_per_run"]==2
    with pytest.raises(ValueError,match="headroom"):
        resource_plan(5,host_cpus=16,engine="lean",docker_cpus=16,docker_memory_bytes=4*1024**3)


def test_python_pool_respects_available_cpu_count_and_job_count():
    assert resource_plan(5,host_cpus=16,engine="python")["workers"]==1
    assert resource_plan(5,host_cpus=2,engine="python")["workers"]==1
    assert resource_plan(5,host_cpus=1,engine="python")["workers"]==1


def test_low_memory_defers_work_even_when_cpu_and_vm_capacity_are_large():
    with pytest.raises(ValueError, match='deferred'):
        resource_plan(5,host_cpus=32,engine='python',available_memory_bytes=5*1024**3)
    with pytest.raises(ValueError, match='headroom'):
        resource_plan(1,host_cpus=32,engine='python',available_memory_bytes=9*1024**3)
    assert resource_plan(1,host_cpus=2,engine='python',available_memory_bytes=10*1024**3)['workers']==1


def test_calculations_really_overlap_and_results_remain_keyed():
    barrier, lock = Barrier(3), Lock()
    active, peak = 0, 0
    def calculate(key):
        nonlocal active,peak
        with lock:
            active+=1
            peak=max(peak,active)
        barrier.wait(timeout=5)
        with lock:
            active-=1
        return key*key
    assert dict(parallel_results(range(3),calculate,3))=={0:0,1:1,2:4}
    assert peak==3


def test_failed_worker_cannot_be_returned_as_a_success():
    def failed(key):
        raise ValueError("parity failed")
    with pytest.raises(ValueError,match="parity failed"):
        list(parallel_results(["strategy"],failed,2))


def test_preparation_is_frozen_and_subprocess_credentials_are_stripped(tmp_path, monkeypatch):
    from systematic_trading.research import compute
    from systematic_trading.research.calculation_worker import checked_input
    reference=compute.frozen_input(tmp_path/"input.json",{"bars":[]})
    assert checked_input(reference)=={"bars":[]}
    with pytest.raises(ValueError,match="changed"):
        compute.frozen_input(tmp_path/"input.json",{"bars":[1]})
    monkeypatch.setenv("ST_POSTGRES_PASSWORD","must-not-reach-worker")
    # Exercise the portable subprocess environment; Windows restrictions have
    # separate real AppContainer integration tests below and in native_worker.
    from types import SimpleNamespace
    monkeypatch.setattr(compute,'os',SimpleNamespace(name='posix',environ=compute.os.environ))
    captured={}
    monkeypatch.setattr(compute.subprocess,"run",lambda args,**kwargs:captured.update(kwargs))
    compute.prepare_in_process(tmp_path/"request.json")
    assert "ST_POSTGRES_PASSWORD" not in captured["env"]
    assert captured["env"]["OMP_NUM_THREADS"]=="1"


def test_isolated_preparation_reproduces_fixture_decisions(tmp_path):
    import json
    from systematic_trading.lean.fixtures import make_fixture_bundle
    from systematic_trading.lean.contracts import verify_bundle
    from systematic_trading.research.compute import frozen_input, prepare_in_process
    original=tmp_path/"original"
    make_fixture_bundle(original,mode="shared")
    spec=json.loads((original/"spec.json").read_text())
    for key in ("source_hash","strategy_hash","repository_commit"):
        spec.pop(key)
    inputs=frozen_input(tmp_path/"inputs.json",dict(
        bars=json.loads((original/"bars.json").read_text()),
        fx=json.loads((original/"fx.json").read_text()),provenance={"source":"fixture"}))
    target=tmp_path/"prepared"
    request=tmp_path/"request.json"
    frozen_input(request,dict(inputs=inputs,models=None,bundle=str(target),spec=spec))
    prepare_in_process(request)
    verify_bundle(target)
    assert json.loads((target/"decisions.json").read_text())==json.loads((original/"decisions.json").read_text())
