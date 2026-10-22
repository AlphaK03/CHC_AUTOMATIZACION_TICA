"""Nombres automáticos y recuperación de lotes, sin consultar ningún portal."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest

from chc_runtime.manifest_names import manifest_name, manifest_scope
from chc_runtime.manifest_service import BatchService


class ManifestNamesTests(unittest.TestCase):
    def service(self, root, flow='conocimientos'):
        service = BatchService(root, flow, lambda *args, **kwargs: None, Event())
        service.index['config'].update(year=2026, month=10)
        return service

    def test_month_names_and_distinct_selections(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(folder)
            config = service.index['config']
            self.assertEqual(manifest_name(manifest_scope(service.flow, config)), 'octubre26')
            config.update(year=2027, month=1)
            self.assertEqual(manifest_name(manifest_scope(service.flow, config)), 'enero27')
            config.update(year=2026, month=10)
            for changes in ({'courier':'N'}, {'limit':2}, {'manifestIds':'001-2026-000001'}):
                with self.subTest(changes=changes):
                    name = manifest_name(manifest_scope(service.flow, {**config, **changes}))
                    self.assertTrue(name.startswith('octubre26_'))
                    self.assertNotEqual(name, 'octubre26')
            for changes in ({'start':'2026-10-02'},{'modes':['aereo']},{'modes':['maritimo','aereo']}):
                self.assertEqual(manifest_name(manifest_scope(service.flow,{**config,**changes})),'octubre26')

    def test_resume_ignores_manual_name_and_mode_order(self):
        with tempfile.TemporaryDirectory() as folder:
            service = self.service(folder)
            service.index['config'].update(modes=['maritimo', 'aereo'], name='Primero')
            first = service.prepare()
            service.index['config'].update(modes=['aereo', 'maritimo'], name='Otro', workers=8)
            second = service.prepare()
            self.assertIs(second, first)
            self.assertEqual(len(service.index['history']), 1)
            self.assertEqual(service.index['active'], first['id'])
            service.index['config'].update(modes=['maritimo'],end='2026-10-17')
            self.assertIs(service.prepare(),first)
            service.index['config'].update(modes=['aereo'],end='2026-10-31')
            self.assertIs(service.prepare(),first)
            service.index['config'].update(month=11,end='')
            self.assertNotEqual(service.prepare()['id'], first['id'])

    def test_legacy_progress_and_paths_survive_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = self.service(root)
            record = service.prepare()
            old_id = 'lote-manual-original'
            record.update(id=old_id, name='Tabla anterior', output=str(root/'resultados/Tabla anterior'),
                          work=str(root/'data/jobs/conocimientos'/old_id))
            service.index['active'] = old_id
            database = root/'original.sqlite3'
            with closing(sqlite3.connect(database)) as db:
                db.executescript('''CREATE TABLE jobs (id TEXT, ordinal INTEGER, state TEXT,
                    attempts INTEGER, kept_count INTEGER, error TEXT);
                    CREATE TABLE rows (value TEXT);
                    INSERT INTO jobs VALUES ('000001', 1, 'Guardado', 1, 1, '');
                    INSERT INTO rows VALUES ('000000123');''')
                db.commit()
            record['databases'] = [str(database)]
            service.save()
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            resumed = self.service(root)
            resumed.index['config']['name'] = 'octubre26'
            found = resumed.prepare()
            self.assertEqual(found['id'], old_id)
            self.assertEqual(found['name'], 'Tabla anterior')
            self.assertEqual(found['output'], record['output'])
            self.assertEqual(found['work'], record['work'])
            self.assertEqual(found['summary']['succeeded'], 1)
            self.assertEqual(found['summary']['rows'], 1)
            self.assertEqual(len(resumed.index['history']), 1)
            self.assertEqual(resumed.index['active'], old_id)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
