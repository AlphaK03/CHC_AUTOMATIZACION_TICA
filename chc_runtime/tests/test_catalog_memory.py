"""Consultar meses BLs no requiere importar el motor matemático ni el navegador."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class CatalogMemory(unittest.TestCase):
    def test_catalog_is_available_without_numerical_or_browser_dependencies(self):
        code = '''
import importlib.abc, sys, tempfile
from pathlib import Path
from threading import Event
class NoEngine(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'numpy','pandas','openpyxl','playwright'}:
   raise ImportError('El catálogo no debe necesitar el motor: '+fullname)
sys.meta_path.insert(0,NoEngine())
from chc_runtime.knowledge_source import KnowledgeSource
with tempfile.TemporaryDirectory() as folder:
 result=KnowledgeSource(Path(folder),Event(),lambda *a,**k:None).catalog()
 assert result['periods']==[]
 assert not list(Path(folder).rglob('*')), 'El catálogo escribió en los datos'
'''
        environment=os.environ.copy()
        environment['PYTHONPATH']=str(Path(__file__).resolve().parents[2])
        result=subprocess.run([sys.executable,'-c',code],env=environment,
            capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__': unittest.main()
