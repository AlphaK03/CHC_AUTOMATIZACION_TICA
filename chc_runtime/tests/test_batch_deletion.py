"""Borrado aislado: bloqueos, alcance, reversión y recuperación tras cierre."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from chc_runtime.batch_deletion import delete_batch
from chc_runtime.job_store import RunLock
from chc_runtime.manifest_service import BatchService


class BatchDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def service(self, flow='conocimientos'):
        service = BatchService(self.root, flow, lambda *a, **k: None, threading.Event())
        work = self.root / 'data/jobs' / flow / '123'
        database = work / 'SQLite' / 'results.sqlite3'
        database.parent.mkdir(parents=True)
        with closing(sqlite3.connect(database)) as db:
            db.execute('CREATE TABLE results(value TEXT)')
            db.execute("INSERT INTO results VALUES ('000123')")
            db.commit()
        checkpoint = database.with_name('bls_pages.sqlite3')
        checkpoint.write_bytes(database.read_bytes())
        (work / 'progress.json').write_text('historial', encoding='utf-8')
        source = self.root / 'original.sqlite3'
        source.write_bytes(database.read_bytes())
        csv = self.root / 'resultados' / 'guardado.CSV'
        csv.parent.mkdir(exist_ok=True)
        csv.write_text('000123', encoding='utf-8')
        record = dict(id='123', name='octubre26', work=str(work), databases=[str(database)],
                      spec={'input': str(source)}, config={}, period='2026-10')
        service.index.update(history=[record], active='123')
        service.save()
        return service, work, database

    def request(self):
        return dict(confirmTableId='123', confirmTableName='octubre26', confirmation='BORRAR')

    def test_each_flow_archives_only_its_own_files_and_survives_reopen(self):
        for flow in ('tabla', 'conocimientos', 'duas', 'movimientos', 'contenedores', 'bls'):
            with self.subTest(flow=flow):
                service, work, database = self.service(flow)
                before = {p.relative_to(work).as_posix(): p.read_bytes() for p in work.rglob('*') if p.is_file()}
                result = service.execute('delete', self.request())
                archive = Path(result['backup'])
                self.assertFalse(list(work.rglob('*.sqlite3')))
                self.assertFalse(service.snapshot()['activeId'])
                self.assertFalse(service.snapshot()['history'])
                for relative, content in before.items():
                    self.assertEqual((archive / 'files' / relative).read_bytes(), content)
                self.assertEqual((self.root/'resultados/guardado.CSV').read_text(), '000123')
                self.assertEqual((self.root/'original.sqlite3').read_bytes(), before['SQLite/results.sqlite3'])
                reopened = BatchService(self.root, flow, lambda *a, **k: None, threading.Event())
                self.assertFalse(reopened.index['history'])
                self.assertFalse(database.exists())

    def test_confirmation_identity_name_and_busy_block_without_modifying(self):
        service, work, database = self.service()
        content = database.read_bytes()
        for changes in ({'confirmation': None}, {'confirmation': 'borrar'}, {'confirmation': 'BORRAR '},
                        {'confirmTableId': 'other'}, {'confirmTableName': 'other'}):
            request = self.request()
            request.update(changes)
            with self.assertRaises(ValueError):
                delete_batch(service, request)
            self.assertEqual(database.read_bytes(), content)
        service.processing = True
        with self.assertRaises(ValueError):
            delete_batch(service, self.request())
        self.assertFalse((self.root/'data/deleted').exists())

    def test_engine_lock_blocks_archive_including_checkpoints(self):
        service, work, database = self.service('bls')
        for path in (database, database.with_name('bls_pages.sqlite3')):
            with RunLock(path):
                with self.assertRaises(RuntimeError):
                    delete_batch(service, self.request())
            self.assertTrue(database.exists())
            self.assertTrue(service.active())
        self.assertFalse((self.root/'data/deleted').exists())

    def test_external_paths_inputs_and_shared_work_are_rejected(self):
        service, work, database = self.service()
        record = service.active()
        record['databases'].append(str(self.root/'original.sqlite3'))
        with self.assertRaises(ValueError):
            delete_batch(service, self.request())
        record['databases'].pop()
        record['spec']['input'] = str(database)
        with self.assertRaises(ValueError):
            delete_batch(service, self.request())
        record['spec'] = {}
        service.index['history'].append({**record, 'id': 'other'})
        with self.assertRaises(ValueError):
            delete_batch(service, self.request())
        service.index['history'].pop()
        record['work'] = str(self.root)
        with self.assertRaises(ValueError):
            delete_batch(service, self.request())
        self.assertTrue(database.exists())

    def test_failed_catalog_save_or_file_move_restores_every_file(self):
        service, work, database = self.service()
        before = {p: p.read_bytes() for p in work.rglob('*') if p.is_file()}
        with patch.object(service, 'save', side_effect=OSError('sin espacio')):
            with self.assertRaises(OSError):
                delete_batch(service, self.request())
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        replace = os.replace
        def fail_second_file(source, target):
            if Path(source) == database:
                raise PermissionError('archivo abierto')
            return replace(source, target)
        with patch('chc_runtime.batch_deletion.os.replace', side_effect=fail_second_file):
            with self.assertRaises(PermissionError):
                delete_batch(service, self.request())
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertTrue(service.active())

    def test_crash_during_move_restores_before_loading_service(self):
        service, work, database = self.service()
        content = database.read_bytes()
        replace = os.replace
        def crash(source, target):
            result = replace(source, target)
            if Path(source) == database:
                raise SystemExit('simular cierre inesperado')
            return result
        with patch('chc_runtime.batch_deletion.os.replace', side_effect=crash):
            with self.assertRaises(SystemExit):
                delete_batch(service, self.request())
        self.assertFalse(database.exists())
        reopened = BatchService(self.root, service.flow, lambda *a, **k: None, threading.Event())
        self.assertTrue(reopened.active())
        self.assertEqual(database.read_bytes(), content)
        journal = next((self.root/'data/deleted').rglob('deletion.json'))
        self.assertEqual(json.loads(journal.read_text())['state'], 'restored')

    def test_crash_after_catalog_commit_keeps_archive_deleted(self):
        service, work, database = self.service()
        from chc_runtime.batch_deletion import write_json
        def crash_on_deleted(path, data):
            if data['state'] == 'deleted':
                raise SystemExit('simular cierre tras confirmar')
            write_json(path, data)
        with patch('chc_runtime.batch_deletion.write_json', side_effect=crash_on_deleted):
            with self.assertRaises(SystemExit):
                delete_batch(service, self.request())
        reopened = BatchService(self.root, service.flow, lambda *a, **k: None, threading.Event())
        self.assertFalse(reopened.index['history'])
        self.assertFalse(database.exists())
        journal = next((self.root/'data/deleted').rglob('deletion.json'))
        self.assertEqual(json.loads(journal.read_text())['state'], 'deleted')

    def test_recreated_identity_does_not_restore_an_already_committed_delete(self):
        service, work, database = self.service()
        original = dict(service.active())
        from chc_runtime.batch_deletion import write_json
        def fail_final_notice(path, data):
            if data['state'] == 'deleted':
                raise OSError('aviso pendiente')
            write_json(path, data)
        with patch('chc_runtime.batch_deletion.write_json', side_effect=fail_final_notice):
            delete_batch(service, self.request())
        # Simula iniciar de nuevo antes de cerrar la app; la identidad es la misma.
        service.index['history'] = [original]
        service.index['active'] = original['id']
        database.write_bytes(b'nueva base')
        service.save()
        BatchService(self.root, service.flow, lambda *a, **k: None, threading.Event())
        self.assertEqual(database.read_bytes(), b'nueva base')
        journal = next((self.root/'data/deleted').rglob('deletion.json'))
        self.assertEqual(json.loads(journal.read_text())['state'], 'deleted')


if __name__ == '__main__':
    unittest.main()
