"""Windows elimina la familia del worker cuando termina su GUI, incluso por crash."""
import ctypes
from ctypes import wintypes
import os


class ProcessTreeGuard:
    def __init__(self):
        self.handle = None

    def attach(self, process_id):
        if os.name != 'nt':
            return
        size_t = ctypes.c_size_t
        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', wintypes.DWORD), ('min_working_set', size_t),
                        ('max_working_set', size_t), ('active_processes', wintypes.DWORD),
                        ('affinity', size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]
        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', IOCounters),
                        ('process_memory', size_t), ('job_memory', size_t),
                        ('peak_process_memory', size_t), ('peak_job_memory', size_t)]
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        api.CreateJobObjectW.restype = wintypes.HANDLE
        api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        api.SetInformationJobObject.restype = wintypes.BOOL
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        api.AssignProcessToJobObject.restype = wintypes.BOOL
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        self.close()
        handle = api.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not api.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            process = api.OpenProcess(0x0101, False, process_id)  # SET_QUOTA | TERMINATE
            if not process:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not api.AssignProcessToJobObject(handle, process):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                api.CloseHandle(process)
        except Exception:
            api.CloseHandle(handle)
            raise
        self.handle = handle
        self._api = api

    def close(self):
        if self.handle:
            self._api.CloseHandle(self.handle)
            self.handle = None
