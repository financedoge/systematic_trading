"""Native research isolation: zero-capability AppContainer and a bounded Job.

The launcher never falls back to an unrestricted process if isolation fails.
Input/runtime ACLs grant only read/execute; output is the only writable grant.
"""
from __future__ import annotations

import ctypes as C
import csv
from contextlib import contextmanager
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


class Startup(C.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),
        *[(n,W.DWORD) for n in ('x','y','xs','ys','xc','yc','fill','flags')],
        ('show',W.WORD),('reserved_size',W.WORD),('reserved_bytes',C.c_void_p),
        ('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]


class StartupEx(C.Structure):
    _fields_=[('startup',Startup),('attributes',C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]


class Capabilities(C.Structure):
    _fields_=[('sid',C.c_void_p),('capabilities',C.c_void_p),('count',W.DWORD),('reserved',W.DWORD)]


class BasicLimits(C.Structure):
    _fields_=[('process_time',C.c_int64),('job_time',C.c_int64),('flags',W.DWORD),
        ('min_working',C.c_size_t),('max_working',C.c_size_t),('active',W.DWORD),
        ('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_=[('basic',BasicLimits),('io',C.c_uint64*6),('process_memory',C.c_size_t),
        ('job_memory',C.c_size_t),('peak_process',C.c_size_t),('peak_job',C.c_size_t)]


class CpuLimit(C.Structure):
    _fields_=[('flags',W.DWORD),('rate',W.DWORD)]


def api():
    if os.name!='nt': raise RuntimeError('Native research worker requires Windows')
    kernel=C.WinDLL('kernel32',use_last_error=True)
    for name,args,result in [
        ('CreateJobObjectW',[C.c_void_p,W.LPCWSTR],W.HANDLE),
        ('CreateMutexW',[C.c_void_p,W.BOOL,W.LPCWSTR],W.HANDLE),
        ('ReleaseMutex',[W.HANDLE],W.BOOL),
        ('SetInformationJobObject',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
        ('AssignProcessToJobObject',[W.HANDLE,W.HANDLE],W.BOOL),
        ('InitializeProcThreadAttributeList',[C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        ('UpdateProcThreadAttribute',[C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        ('DeleteProcThreadAttributeList',[C.c_void_p],None),
        ('CreateProcessW',[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.c_void_p,C.POINTER(ProcessInfo)],W.BOOL),
        ('ResumeThread',[W.HANDLE],W.DWORD),('WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD),
        ('GetExitCodeProcess',[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        ('QueryInformationJobObject',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
        ('TerminateProcess',[W.HANDLE,W.UINT],W.BOOL),
        ('TerminateJobObject',[W.HANDLE,W.UINT],W.BOOL),('CloseHandle',[W.HANDLE],W.BOOL),
        ('LocalFree',[C.c_void_p],C.c_void_p)]:
        fn=getattr(kernel,name);fn.argtypes=args;fn.restype=result
    return kernel


def checked(value):
    if not value: raise C.WinError(C.get_last_error())
    return value


def profile():
    userenv=C.WinDLL('userenv',use_last_error=True)
    create=userenv.CreateAppContainerProfile
    create.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)]
    create.restype=C.c_long
    derive=userenv.DeriveAppContainerSidFromAppContainerName
    derive.argtypes=[W.LPCWSTR,C.POINTER(C.c_void_p)];derive.restype=C.c_long
    sid=C.c_void_p();name='st.research.'+uuid4().hex
    result=create(name,name,'Offline frozen research calculation',None,0,C.byref(sid))
    if result<0:
        if result & 0xffffffff != 0x800700b7: raise OSError(f'AppContainer profile creation failed: {result & 0xffffffff:08x}')
        result=derive(name,C.byref(sid))
        if result<0: raise OSError('AppContainer SID lookup failed')
    advapi=C.WinDLL('advapi32',use_last_error=True)
    convert=advapi.ConvertSidToStringSidW
    convert.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)];convert.restype=W.BOOL
    text=W.LPWSTR();checked(convert(sid,C.byref(text)))
    value=text.value;api().LocalFree(text)
    return sid,value,name


def grant(path,sid,*,write=False):
    path=Path(path).resolve(strict=True)
    rights=('(OI)(CI)' if path.is_dir() else '')+('(M)' if write else '(RX)')
    result=subprocess.run(['icacls',str(path),'/grant',f'*{sid}:{rights}','/Q'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode: raise RuntimeError('Could not provision research ACL: '+str(path))
    if write:
        # A newly created directory can inherit Modify without WRITE_OWNER.
        # Its owner can grant itself that right to apply a lower integrity label.
        identity=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        owner_sid=next(csv.reader(identity.strip().splitlines()))[-1]
        result=subprocess.run(['icacls',str(path),'/grant',f'*{owner_sid}:(OI)(CI)(F)','/Q'],
            capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise RuntimeError('Could not grant output-owner labeling rights')
        result=subprocess.run(['icacls',str(path),'/setintegritylevel','(OI)(CI)L','/Q'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise RuntimeError('Could not provision low-integrity output: '+str(path))


@contextmanager
def worker_slot(timeout):
    """Serialize shared runtime ACL propagation across callers and processes.

    Concurrent icacls inheritance updates can lose another profile's grant on
    child files. A session-wide slot also bounds aggregate research memory.
    Windows releases an abandoned mutex when its owning process exits.
    """
    kernel = api()
    handle = checked(kernel.CreateMutexW(None, False, 'Local\\SystematicTrading.NativeResearchWorker'))
    acquired = False
    try:
        result = kernel.WaitForSingleObject(handle, int(timeout * 1000))
        if result == 258:
            raise TimeoutError('Timed out waiting for the native research worker slot')
        if result not in (0, 0x80):
            raise C.WinError(C.get_last_error())
        acquired = True
        yield
    finally:
        if acquired:
            checked(kernel.ReleaseMutex(handle))
        kernel.CloseHandle(handle)


def run(command,*,output,read_roots,write_roots=(),environment=None,memory_bytes=4*1024**3,cpus=2,timeout=900):
    with worker_slot(timeout):
        return _profile_run(command, output=output, read_roots=read_roots, write_roots=write_roots,
            environment=environment, memory_bytes=memory_bytes, cpus=cpus, timeout=timeout)


def _profile_run(command,*,output,read_roots,write_roots,environment,memory_bytes,cpus,timeout):
    sid,sid_text,name=profile()
    try:
        return _run(command,output=output,read_roots=read_roots,write_roots=write_roots,environment=environment,
            memory_bytes=memory_bytes,cpus=cpus,timeout=timeout,sid=sid,sid_text=sid_text)
    finally:
        for path in (*read_roots,*write_roots,output):
            subprocess.run(['icacls',str(Path(path).resolve()),'/remove:g','*'+sid_text,'/Q'],
                capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        userenv=C.WinDLL('userenv');userenv.DeleteAppContainerProfile.argtypes=[W.LPCWSTR]
        userenv.DeleteAppContainerProfile(name)
        advapi=C.WinDLL('advapi32');advapi.FreeSid.argtypes=[C.c_void_p];advapi.FreeSid(sid)


def _run(command,*,output,read_roots,write_roots,environment,memory_bytes,cpus,timeout,sid,sid_text):
    import msvcrt
    kernel=api()
    output=Path(output).resolve(strict=True)
    for root in read_roots:
        path=Path(root).resolve(strict=True)
        if path==Path(path.anchor) or path in output.parents:
            raise ValueError('Research read grant is too broad')
        grant(path,sid_text)
    grant(output,sid_text,write=True)
    for root in write_roots:
        path=Path(root).resolve(strict=True)
        if path==Path(path.anchor) or any(Path(r).resolve().is_relative_to(path) for r in read_roots):
            raise ValueError('Research writable grant overlaps immutable inputs')
        grant(path,sid_text,write=True)
    scratch=output/'scratch';scratch.mkdir(exist_ok=True)
    system=os.environ.get('SYSTEMROOT',r'C:\Windows')
    env=dict(SYSTEMROOT=system,WINDIR=system,TEMP=str(scratch),TMP=str(scratch),
        PATH=str(Path(system)/'System32'),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
        DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_NOLOGO='1',DOTNET_CLI_HOME=str(scratch))
    for key in ('SYSTEMDRIVE','USERPROFILE','LOCALAPPDATA','APPDATA','PROGRAMDATA','ALLUSERSPROFILE'):
        if key in os.environ:env[key]=os.environ[key]
    allowed={'PYTHONPATH','PYTHONHOME','PYTHONNET_PYDLL','DOTNET_ROOT','ST_LEAN_INPUT_ROOT','ST_LEAN_OUTPUT_ROOT'}
    if set(environment or {})-allowed: raise ValueError('Unapproved native worker environment key')
    env.update(environment or {})
    block=C.create_unicode_buffer('\0'.join(f'{k}={v}' for k,v in sorted(env.items()))+'\0\0')
    job=checked(kernel.CreateJobObjectW(None,None));info=ProcessInfo();attributes=None
    try:
        limits=ExtendedLimits();limits.basic.flags=0x2000|0x200|0x100|0x8
        limits.basic.active=32;limits.job_memory=memory_bytes;limits.process_memory=memory_bytes
        checked(kernel.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        cpu=CpuLimit(0x1|0x4,max(100,min(10000,int(cpus/max(1,os.cpu_count() or 1)*10000))))
        checked(kernel.SetInformationJobObject(job,15,C.byref(cpu),C.sizeof(cpu)))
        size=C.c_size_t();kernel.InitializeProcThreadAttributeList(None,1,0,C.byref(size))
        attributes=C.create_string_buffer(size.value)
        checked(kernel.InitializeProcThreadAttributeList(attributes,1,0,C.byref(size)))
        caps=Capabilities(sid,None,0,0)
        checked(kernel.UpdateProcThreadAttribute(attributes,0,0x20009,C.byref(caps),C.sizeof(caps),None,None))
        startup=StartupEx();startup.startup.cb=C.sizeof(startup);startup.startup.flags=0x100
        startup.attributes=C.cast(attributes,C.c_void_p)
        with open(os.devnull,'rb') as null, (output/'worker.log').open('wb') as log:
            handles=[msvcrt.get_osfhandle(null.fileno()),msvcrt.get_osfhandle(log.fileno())]
            for handle in handles:os.set_handle_inheritable(handle,True)
            startup.startup.stdin=handles[0];startup.startup.stdout=handles[1];startup.startup.stderr=handles[1]
            line=C.create_unicode_buffer(subprocess.list2cmdline(list(map(str,command))))
            checked(kernel.CreateProcessW(str(Path(command[0]).resolve()),line,None,None,True,0x8000000|0x80000|0x400|0x4,
                block,str(output),C.byref(startup),C.byref(info)))
            checked(kernel.AssignProcessToJobObject(job,info.process))
            if kernel.ResumeThread(info.thread)==0xffffffff:raise C.WinError(C.get_last_error())
            status=kernel.WaitForSingleObject(info.process,int(timeout*1000))
            if status==258:raise TimeoutError('Isolated research worker exceeded its deadline')
            if status!=0:raise C.WinError(C.get_last_error())
            code=W.DWORD();checked(kernel.GetExitCodeProcess(info.process,C.byref(code)))
        measured=ExtendedLimits()
        checked(kernel.QueryInformationJobObject(job,9,C.byref(measured),C.sizeof(measured),None))
        receipt=dict(appcontainer=sid_text,network_capabilities=[],memory_limit_bytes=memory_bytes,
            peak_process_commit_bytes=measured.peak_process,peak_job_commit_bytes=measured.peak_job,
            cpus=cpus,kill_descendants_on_close=True,exit_code=code.value)
        (output/'isolation.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        if code.value:raise subprocess.CalledProcessError(code.value,command)
        return receipt
    finally:
        kernel.TerminateJobObject(job,1)
        # Assignment can fail after CreateProcess created a suspended child.
        # That child is not yet covered by TerminateJobObject.
        if info.process:
            kernel.TerminateProcess(info.process,1)
            kernel.WaitForSingleObject(info.process,5000)
        for handle in (info.thread,info.process,job):
            if handle:kernel.CloseHandle(handle)
        if attributes is not None:kernel.DeleteProcThreadAttributeList(attributes)


if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
    run(**config)
