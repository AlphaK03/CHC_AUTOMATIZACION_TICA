"""Dos consumidores de importación comparten descargas; esperar permite cancelar."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime.job_store import RunLock

ROOT = Path(__file__).resolve().parents[2]


class ImportCacheTest(unittest.TestCase):
    def producer(self, database):
        return subprocess.Popen([sys.executable, '-u', str(ROOT/'integrations/duas_source/worker.py'),
            '--day','2026-10-11','--database',str(database),'--driver','unused.exe',
            '--selection','importacion','--offline-fixture'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')

    def finish(self, child):
        try:
            events = [json.loads(line) for line in child.stdout]
            child.wait(timeout=10)
            errors = child.stderr.read()
            self.assertEqual(child.returncode,0,errors)
            return next(event for event in reversed(events) if event['event']=='result')
        finally:
            for stream in [child.stdin,child.stdout,child.stderr]:stream.close()
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    def test_two_consumers_download_each_regime_once(self):
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'compartida.sqlite3'
            first=self.producer(database)
            second=self.producer(database)
            a,b=self.finish(first),self.finish(second)
            self.assertTrue(a['complete'])
            self.assertTrue(b['complete'])
            self.assertEqual(a['duas'],b['duas'])
            self.assertEqual(len(a['duas']),4)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('select count(*),sum(attempts) from queries').fetchone(),(4,4))

    def test_waiting_consumer_can_stop_without_querying(self):
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'compartida.sqlite3'
            with RunLock(str(database)+'.proveedor'):
                child=self.producer(database)
                event=json.loads(child.stdout.readline())
                self.assertIn('Esperando',event['message'])
                child.stdin.write('stop\n')
                child.stdin.flush()
                result=self.finish(child)
                self.assertTrue(result['stopped'])
                self.assertFalse(database.exists())


if __name__=='__main__':
    unittest.main()
