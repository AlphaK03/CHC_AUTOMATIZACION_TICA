"""El cierre de la GUI debe eliminar tanto el worker como sus descendientes."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from process_guard import ProcessTreeGuard


@unittest.skipUnless(os.name == 'nt', 'Protección de procesos de Windows')
class ProcessGuardTest(unittest.TestCase):
    def test_closing_guard_terminates_worker_and_child(self):
        source = "import sys,subprocess,time; sys.stdin.readline(); " \
                 "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); " \
                 "print(child.pid,flush=True); time.sleep(60)"
        worker = subprocess.Popen([sys.executable, '-u', '-c', source],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        guard = ProcessTreeGuard()
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        child = None
        try:
            guard.attach(worker.pid)
            worker.stdin.write('start\n')
            worker.stdin.flush()
            child_pid = int(worker.stdout.readline())
            child = api.OpenProcess(0x100000, False, child_pid)
            self.assertTrue(child)
            guard.close()
            worker.wait(timeout=5)
            self.assertEqual(api.WaitForSingleObject(child, 5000), 0)
        finally:
            guard.close()
            if child:
                api.CloseHandle(child)
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=5)
            worker.stdin.close()
            worker.stdout.close()


if __name__ == '__main__':
    unittest.main()
