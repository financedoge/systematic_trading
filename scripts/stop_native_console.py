"""Gracefully interrupt one isolated Windows console, never a shared console."""
import ctypes
from ctypes import wintypes
import os
import sys
import time


def main():
    target = int(sys.argv[1])
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.FreeConsole()
    if not kernel.AttachConsole(wintypes.DWORD(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        processes = (wintypes.DWORD * 32)()
        count = kernel.GetConsoleProcessList(processes, 32)
        if count < 1 or count > 32 or set(processes[:count]) != {target, os.getpid()}:
            raise RuntimeError('Refusing to signal a shared or unidentified console')
        if not kernel.SetConsoleCtrlHandler(None, True):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GenerateConsoleCtrlEvent(0, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(1)
    finally:
        kernel.FreeConsole()


if __name__ == '__main__':
    main()
