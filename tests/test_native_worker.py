"""Real Windows restrictions; no Docker or mocked process creation."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from systematic_trading.lean.windows_worker import run


pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows AppContainer integration')


def worker(tmp_path,source,**kwargs):
    inputs=tmp_path/'inputs';inputs.mkdir()
    script=inputs/'probe.py';script.write_text(source,encoding='utf8')
    output=tmp_path/'output';output.mkdir()
    result=run([sys.executable,'-B',str(script)],output=output,
        read_roots=[Path(sys.prefix),Path(sys.base_prefix),inputs],**kwargs)
    return output,result


def test_restricts_network_credentials_inputs_and_sibling_outputs(tmp_path,monkeypatch):
    private=tmp_path/'private.txt';private.write_text('private fixture')
    monkeypatch.setenv('ST_SECRET_FIXTURE','must not escape')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen()
        port=listener.getsockname()[1]
        with socket.create_connection(('127.0.0.1',port),timeout=2):pass
        source=f'''
import json,os,socket
from pathlib import Path
result={{'secret_absent':'ST_SECRET_FIXTURE' not in os.environ}}
for name,path,mode in [('input_write',__file__,'a'),('private_read',{str(private)!r},'r')]:
    try:
        with open(path,mode):pass
        result[name]=False
    except PermissionError:result[name]=True
with socket.socket() as s:
    s.settimeout(2)
    result['network_denied']=s.connect_ex(('127.0.0.1',{port}))!=0
Path('result.json').write_text(json.dumps(result))
'''
        output,receipt=worker(tmp_path,source,timeout=15)
    assert all(json.loads((output/'result.json').read_text()).values())
    assert receipt['peak_job_commit_bytes']>0
    assert receipt['memory_limit_bytes'] is None
    assert receipt['memory_policy']=='windows_managed'
    assert receipt['job_limit_flags'] & (0x100|0x200)==0
    assert receipt['job_limit_flags'] & 0x2000


def test_commit_limit_rejects_large_allocation(tmp_path):
    output,receipt=worker(tmp_path,"""
from pathlib import Path
try: data=bytearray(512*1024**2)
except MemoryError:Path('bounded.txt').write_text('yes')
""",memory_bytes=128*1024**2,timeout=20)
    assert (output/'bounded.txt').read_text()=='yes'
    assert receipt['peak_job_commit_bytes']<=128*1024**2
    assert receipt['memory_policy']=='explicit_limit'
    assert receipt['job_limit_flags'] & (0x100|0x200)==0x300


def test_default_worker_can_commit_more_than_old_four_gib_cap(tmp_path):
    # Commit, but do not touch, the pages: this exercises the Windows quota
    # without filling physical RAM or writing gigabytes of test artifacts.
    output,receipt=worker(tmp_path,"""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
k=C.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,W.DWORD,W.DWORD]
k.VirtualAlloc.restype=C.c_void_p
k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,W.DWORD]
k.VirtualFree.restype=W.BOOL
size=4*1024**3+64*1024**2
p=k.VirtualAlloc(None,size,0x3000,0x04)
if not p:raise C.WinError(C.get_last_error())
try:Path('committed.txt').write_text(str(size))
finally:
    if not k.VirtualFree(p,0,0x8000):raise C.WinError(C.get_last_error())
""",timeout=30)
    assert int((output/'committed.txt').read_text())>4*1024**3
    assert receipt['memory_limit_bytes'] is None
    assert receipt['peak_job_commit_bytes']>4*1024**3


@pytest.mark.parametrize('limit',[0,-1,True,'4g'])
def test_invalid_explicit_limit_rejected_before_launch(tmp_path,limit):
    with pytest.raises(ValueError,match='positive byte count'):
        worker(tmp_path,'pass',memory_bytes=limit)


def test_concurrent_callers_can_import_shared_python_runtime(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ready = Barrier(2)
    source = """
import subprocess,sys
for _ in range(8):
    subprocess.run([sys.executable,'-B','-c',
        'from pydantic import BaseModel; import pydantic.annotated_handlers'],check=True)
"""
    def attempt(index):
        root = tmp_path / str(index)
        root.mkdir()
        ready.wait()
        return worker(root, source, timeout=90)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert all(receipt['exit_code'] == 0 for _, receipt in outcomes)


def test_timeout_kills_descendant(tmp_path):
    source="""
import subprocess,sys,time
from pathlib import Path
p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(90)'])
Path('child.pid').write_text(str(p.pid))
time.sleep(90)
"""
    with pytest.raises(TimeoutError):worker(tmp_path,source,timeout=5)
    pid=int((tmp_path/'output/child.pid').read_text())
    import ctypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    handle=kernel.OpenProcess(0x100000,False,pid)
    if handle:
        try:
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
            assert kernel.WaitForSingleObject(handle,5000)==0
        finally:
            kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
