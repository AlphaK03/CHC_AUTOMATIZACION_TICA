"""Otra apertura activa la ventana existente y un cierre libera el bloqueo."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until
from single_instance import SingleInstance


class Window:
    def __init__(self): self.activations=0
    def showNormal(self): pass
    def raise_(self): pass
    def requestActivate(self): self.activations+=1
    def winId(self): return 0


class SingleInstanceTests(unittest.TestCase):
    def test_other_process_activates_first_and_lock_is_released(self):
        name='CHC.Workbench.test.'+str(os.getpid())
        first=SingleInstance(name)
        self.assertTrue(first.acquire(check_legacy=False))
        first.window=Window()
        code=("import sys; sys.path.insert(0,'workbench'); from PySide6.QtCore import QCoreApplication; "
              "from single_instance import SingleInstance; app=QCoreApplication([]); "
              f"gate=SingleInstance({name!r}); print(gate.acquire(check_legacy=False))")
        process=subprocess.Popen([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[2],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            wait_until(lambda:process.poll() is not None,timeout=10000)
            stdout,stderr=process.communicate()
            self.assertEqual(process.returncode,0,stderr)
            self.assertEqual(stdout.strip(),'False')
            wait_until(lambda:first.window.activations==1)
        finally:
            first.close()
            if process.poll() is None:
                process.kill(); process.wait()
        next_instance=SingleInstance(name)
        self.assertTrue(next_instance.acquire(check_legacy=False))
        next_instance.close()


if __name__=='__main__': unittest.main()
