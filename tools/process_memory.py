"""Muestreo de una familia propia de procesos Windows, sin modificarla."""
import ctypes
from ctypes import wintypes
import os
import statistics
import threading
import time


class ProcessEntry(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('pid', wintypes.DWORD),
               ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD),
               ('parent', wintypes.DWORD), ('priority', wintypes.LONG), ('flags', wintypes.DWORD),
               ('name', wintypes.WCHAR * 260)]


class MemoryCounters(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('peak_working', 'working', 'peak_paged', 'paged',
        'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]


def sample_tree(parent):
    if os.name != 'nt':
        raise RuntimeError('Este medidor usa las métricas nativas de Windows.')
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    api.Process32FirstW.argtypes = api.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    entries = []
    try:
        row = ProcessEntry(); row.size = ctypes.sizeof(row)
        success = api.Process32FirstW(snapshot, ctypes.byref(row))
        while success:
            entries.append((row.pid, row.parent, row.name, row.threads))
            success = api.Process32NextW(snapshot, ctypes.byref(row))
    finally:
        api.CloseHandle(snapshot)
    result = []
    family, checked = {}, set()
    while True:
        candidates = [row for row in entries if row[0] not in checked and
                      (row[0] == parent or row[1] in family)]
        if not candidates: break
        for pid, ppid, name, threads in candidates:
            checked.add(pid)
            handle = api.OpenProcess(0x410, False, pid)  # QUERY_INFORMATION | VM_READ
            if not handle: continue  # Un hijo puede acabar durante la instantánea.
            try:
                created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
                if not api.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                           ctypes.byref(kernel), ctypes.byref(user)): continue
                birth = (created.dwHighDateTime << 32) | created.dwLowDateTime
                # Windows reutiliza PID. Un huérfano antiguo puede apuntar al PID
                # de nuestro worker nuevo: no pertenece a su familia de pruebas.
                if pid != parent and birth < family[ppid]: continue
                family[pid] = birth
                memory = MemoryCounters(); memory.size = ctypes.sizeof(memory)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.size):
                    result.append(dict(pid=pid, name=name, threads=threads,
                                       resident_mib=round(memory.working / 2**20, 2),
                                       committed_mib=round(memory.private / 2**20, 2)))
            finally:
                api.CloseHandle(handle)
    return result


class Sampler:
    def __init__(self, pid, interval=.15):
        self.pid, self.interval = pid, interval
        self.samples, self.errors = [], []
        self.phase = 'loading'
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        started = time.perf_counter()
        while not self.stop.is_set():
            try:
                rows = sample_tree(self.pid)
                self.samples.append(dict(seconds=round(time.perf_counter()-started, 3),
                    phase=self.phase,
                    resident_mib=round(sum(r['resident_mib'] for r in rows), 2),
                    committed_mib=round(sum(r['committed_mib'] for r in rows), 2), processes=rows))
            except OSError as exc:
                self.errors.append(str(exc))
            self.stop.wait(self.interval)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set(); self.thread.join(5)

    def summary(self):
        active = [s for s in self.samples if s['phase']=='extracting']
        return dict(peak_resident_mib=max((s['resident_mib'] for s in self.samples), default=0),
                    peak_committed_mib=max((s['committed_mib'] for s in self.samples), default=0),
                    extraction_resident_mib=round(statistics.median(s['resident_mib'] for s in active),2) if active else None,
                    extraction_committed_mib=round(statistics.median(s['committed_mib'] for s in active),2) if active else None,
                    samples=len(self.samples), errors=self.errors)
