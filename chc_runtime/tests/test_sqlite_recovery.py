"""Cierres abruptos reales: rollback respaldado sin tocar éxitos ni reservas."""
from contextlib import closing
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chc_runtime.job_store import JobStore, RunLock
from chc_runtime.sqlite_recovery import recover_interrupted_database


class SQLiteRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'jobs.sqlite3'
        store = JobStore(self.path)
        store.import_values([f'001-2026-{n:06}' for n in range(1, 401)])
        store.begin_run()
        saved = store.claim(1)
        store.complete(saved, {'numero_del_dua': saved['dua'], 'texto': '000123'})
        store.claim(1)  # La carga del panel no debe devolver esta reserva.
        with store.transaction() as db:
            db.execute('CREATE TABLE daily_automatic_attempts(job_id TEXT PRIMARY KEY, used INTEGER)')
            db.execute('INSERT INTO daily_automatic_attempts VALUES (?,3)', (saved['id'],))
        store.close()
        self.expected = self.dump()

    def dump(self):
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)) as db:
            return list(db.iterdump())

    def crash(self):
        result = subprocess.run([sys.executable, '-c', '''
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute('PRAGMA journal_mode=DELETE')
db.execute('PRAGMA synchronous=FULL')
db.execute('PRAGMA cache_size=5')
db.execute('BEGIN IMMEDIATE')
db.execute("UPDATE jobs SET last_error=? WHERE status='pending'", ('x'*4096,))
os._exit(23)
''', str(self.path)], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 23, result.stderr)
        with self.assertRaises(sqlite3.OperationalError) as raised:
            self.dump()
        self.assertEqual(raised.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY_ROLLBACK)

    def test_crash_recovers_exact_committed_data_and_keeps_raw_backup(self):
        self.crash()
        original = self.path.read_bytes()
        journal = Path(str(self.path) + '-journal').read_bytes()
        backup = recover_interrupted_database(self.path)
        self.assertEqual((backup / self.path.name).read_bytes(), original)
        self.assertEqual((backup / (self.path.name + '-journal')).read_bytes(), journal)
        self.assertEqual(self.dump(), self.expected)
        self.assertIsNone(recover_interrupted_database(self.path))

    def test_normal_read_and_active_writer_do_not_create_backup_or_reset_claims(self):
        with RunLock(self.path):
            with closing(sqlite3.connect(self.path)) as writer:
                writer.execute('BEGIN IMMEDIATE')
                writer.execute("UPDATE jobs SET last_error='sin confirmar' WHERE status='running'")
                self.assertIsNone(recover_interrupted_database(self.path))
                writer.rollback()
        self.assertEqual(self.dump(), self.expected)
        self.assertFalse((self.path.parent / 'backups').exists())

    def test_busy_owner_prevents_recovery(self):
        self.crash()
        with RunLock(self.path):
            self.assertIsNone(recover_interrupted_database(self.path))
            self.assertTrue(Path(str(self.path) + '-journal').exists())
        self.assertIsNotNone(recover_interrupted_database(self.path))
        self.assertEqual(self.dump(), self.expected)

    def test_failed_backup_does_not_open_database_for_recovery(self):
        self.crash()
        original = self.path.read_bytes()
        with patch('chc_runtime.sqlite_recovery.shutil.copy2', side_effect=PermissionError('Respaldo no disponible')):
            with self.assertRaises(PermissionError):
                recover_interrupted_database(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(Path(str(self.path) + '-journal').exists())
        self.assertIsNotNone(recover_interrupted_database(self.path))

    def test_missing_database_is_not_created(self):
        missing = self.path.parent / 'missing.sqlite3'
        with self.assertRaises(sqlite3.OperationalError):
            recover_interrupted_database(missing)
        self.assertFalse(missing.exists())

    def test_details_worker_loads_interrupted_table_offline_without_resetting_jobs(self):
        from chc_runtime.catalog import TableCatalog
        root = self.path.parent / 'isolated'
        catalog = TableCatalog(root / 'data' / 'queues')
        target = catalog.folder / self.path.name
        self.path.replace(target)
        self.path = target
        with catalog.connection() as db:
            db.execute('''INSERT INTO saved_tables
                (id,name,name_key,filename,source_path,source_sheet,output_name)
                VALUES ('fixture','Prueba','prueba',?,'daily://2026-10','octubre26','octubre26')''', (target.name,))
        (root / 'config').mkdir()
        (root / 'config' / 'session.json').write_text(json.dumps({'active_table_id': 'fixture'}), encoding='utf-8')
        self.crash()
        worker = Path(__file__).resolve().parents[2] / 'bots' / 'detalles' / 'workbench_worker.py'
        result = subprocess.run([sys.executable, str(worker), '--storage-root', str(root), '--offline-fixture'],
            input='{"command":"refresh","requestId":1}\n{"command":"shutdown"}\n',
            capture_output=True, text=True, encoding='utf-8', timeout=30,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(result.returncode, 0, result.stderr)
        events = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertFalse([e for e in events if e['event'] in ('error', 'fatal')], events)
        loaded = next(e for e in events if e['event'] == 'result')
        self.assertEqual(loaded['snapshot']['summary']['succeeded'], 1)
        self.assertEqual(loaded['snapshot']['summary']['running'], 1)
        self.assertEqual(self.dump(), self.expected)
        self.assertEqual(len(list((target.parent / 'backups').glob('rollback-*'))), 1)


if __name__ == '__main__':
    unittest.main()
