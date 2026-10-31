import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from systematic_trading.research.file_pool import file_process_map, worker_count


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    (tmp_path/'calculation_pool_fixture.py').write_text('''
import os,time
from pathlib import Path
def work(item):
    start=time.time()
    time.sleep(0.4)
    return dict(value=item*item,pid=os.getpid(),start=start,end=time.time())
def fail(item):
    if item==0:
        time.sleep(0.5)
        raise ValueError('fixture calculation failure')
    time.sleep(30)
def wait(item):
    time.sleep(30)
''')
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv('PYTHONPATH',str(tmp_path)+os.pathsep+str(Path('src').resolve()))
    sys.modules.pop('calculation_pool_fixture',None)
    return importlib.import_module('calculation_pool_fixture')


def test_pool_overlaps_preserves_order_and_removes_transport_copies(tmp_path,jobs):
    result=file_process_map(jobs.work,[3,2,1,0],directory=tmp_path/'pool',workers=2)
    assert [r['value'] for r in result]==[9,4,1,0]
    assert len({r['pid'] for r in result})==2
    assert max(result[0]['start'],result[1]['start'])<min(result[0]['end'],result[1]['end'])
    assert {p.name for p in (tmp_path/'pool').glob('*.json')}=={'pool.json'}


@pytest.mark.parametrize('failure', ['exit','timeout'])
def test_failure_reaps_all_children(tmp_path,jobs,monkeypatch,failure):
    from systematic_trading.research import file_pool
    processes=[]
    original=file_pool.subprocess.Popen
    def launch(*args,**kwargs):
        child=original(*args,**kwargs)
        processes.append(child)
        return child
    monkeypatch.setattr(file_pool.subprocess,'Popen',launch)
    error=subprocess.CalledProcessError if failure=='exit' else subprocess.TimeoutExpired
    with pytest.raises(error):
        file_process_map(jobs.fail if failure=='exit' else jobs.wait,[0,1],
            directory=tmp_path/'pool',workers=2,timeout=2)
    assert len(processes)==2 and all(p.poll() is not None for p in processes)


def test_worker_budget_accounts_for_cpus_jobs_and_duplicated_inputs(monkeypatch):
    from systematic_trading.research import file_pool
    monkeypatch.setattr(file_pool.os,'cpu_count',lambda:16)
    monkeypatch.setattr(file_pool.os,'process_cpu_count',lambda:16,raising=False)
    assert worker_count(1,available_memory_bytes=4*1024**3)==1
    assert worker_count(100,max_workers=3,available_memory_bytes=32*1024**3)==3
    assert worker_count(100,input_bytes=100*1024**2,available_memory_bytes=4*1024**3)<worker_count(
        100,input_bytes=1024,available_memory_bytes=4*1024**3)
    assert worker_count(100,input_bytes=1024**3,available_memory_bytes=4*1024**3)==1
    assert worker_count(100,input_bytes=67*1024**2,available_memory_bytes=32*1024**3)==16
    assert worker_count(100,available_memory_bytes=0)==1


@pytest.mark.skipif(os.name!='nt',reason='Real AppContainer child process isolation')
@pytest.mark.parametrize('workers',[2,16])
def test_parallel_children_inherit_windows_job_and_restrictions(tmp_path,monkeypatch,workers):
    from systematic_trading.lean.windows_worker import run
    inputs=tmp_path/'inputs';inputs.mkdir()
    output=tmp_path/'output';output.mkdir()
    private=tmp_path/'private.txt';private.write_text('private')
    monkeypatch.setenv('ST_SECRET_FIXTURE','must not escape')
    (inputs/'restricted_pool_fixture.py').write_text(f'''
import json,os,time,socket
from pathlib import Path
def work(item):
    start=time.time()
    denied=False
    try:Path({str(private)!r}).read_text()
    except PermissionError:denied=True
    Path('ready-'+str(item)).write_text('ready')
    deadline=time.time()+20
    while len(list(Path('.').glob('ready-*')))<{workers}:
        if time.time()>deadline:raise TimeoutError('Parallel children did not start')
        time.sleep(.05)
    time.sleep(.2)
    return dict(pid=os.getpid(),start=start,end=time.time(),denied=denied,
        threads=os.environ['OMP_NUM_THREADS'],secret='ST_SECRET_FIXTURE' in os.environ)
''')
    script=inputs/'main.py'
    script.write_text(f'''
import json
from pathlib import Path
from systematic_trading.research.file_pool import file_process_map
from restricted_pool_fixture import work
Path('result.json').write_text(json.dumps(file_process_map(work,list(range({workers})),directory=Path('pool'),workers={workers})))
''')
    source=Path('src').resolve()
    receipt=run([sys.executable,'-B',str(script)],output=output,
        read_roots=[source,inputs,Path(sys.prefix),Path(sys.base_prefix)],
        environment={'PYTHONPATH':str(source)+os.pathsep+str(inputs)},cpus=16,timeout=45)
    result=json.loads((output/'result.json').read_text())
    assert len({r['pid'] for r in result})==workers
    assert max(r['start'] for r in result)<min(r['end'] for r in result)
    assert all(r['denied'] and r['threads']=='1' and not r['secret'] for r in result)
    assert receipt['memory_limit_bytes'] is None
    assert receipt['peak_job_commit_bytes']>0
    assert receipt['job_limit_flags'] & (0x100|0x200)==0
