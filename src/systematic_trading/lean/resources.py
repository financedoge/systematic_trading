"""Process resource observations for repeatable, explicitly scoped benchmarks."""
import os
import platform
import time


def process_resources() -> dict:
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                    'PagefileUsage', 'PeakPagefileUsage')]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not query(process(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        peak_bytes = counters.PeakWorkingSetSize
    else:
        import resource
        peak_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return {'cpu_seconds': time.process_time(), 'peak_rss_bytes': peak_bytes,
            'python_version': platform.python_version(), 'platform': platform.system(),
            'scope': 'entire engine process, including imports/startup; excludes Docker daemon'}
