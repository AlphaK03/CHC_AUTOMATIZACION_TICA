"""Vacíos confirmados, migración con respaldo y reconsulta sin perder resultados."""
import csv
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest

from chc_runtime.import_bots import MovementsJobStore, MOVEMENT_FIELDS
from chc_runtime.job_store import JobStore
from chc_runtime.movement_empty import empty_record, verified_empty_html
from chc_runtime.daily import DailyCoordinator, DailyJobStore
from chc_runtime.catalog import TableCatalog

DUA = '001-2026-000001'
OTHER = '001-2026-000002'


def html(dua=DUA):
    code, year, number = dua.split('-')
    return ''.join(f'<span id="span_{name}">{value}</span>' for name, value in
                   zip(('CODI_ADUAN', 'ANO_PRESE', 'NUME_CORRE'), (code, year, number))) + \
        '<table id="SubstkContainerTbl"><tr>' + '<th>Campo</th>' * 5 + '</tr></table>'


class MovementEmptyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_identity_errors_pagination_and_missing_headers_never_confirm_empty(self):
        self.assertTrue(verified_empty_html(html(), DUA))
        for source in (html(OTHER), html() + '<div id="ERROR">CAPTCHA inválido</div>',
                       html() + '<button name="SIGUIENTE">Más</button>',
                       html().replace('<th>Campo</th>', ''),
                       html().replace('</table>', '<tr><td>Incompleta</td></tr></table>')):
            self.assertFalse(verified_empty_html(source, DUA))

    def test_empty_is_durable_not_pending_not_csv_and_can_become_saved(self):
        p = self.root / 'queue.sqlite3'
        store = MovementsJobStore(p)
        try:
            store.import_values([DUA])
            store.begin_run()
            job = store.claim(1)
            store.complete(job, empty_record(DUA, html()))
            self.assertEqual((store.summary()['empty'], store.summary()['retry']), (1, 0))
            self.assertIsNone(store.claim(2))
            paths = {key: str(self.root / file) for key, file in
                     [('output_csv', 'rows.csv'), ('processed_log', 'saved.txt'),
                      ('failed_duas', 'pending.txt'), ('pending_json', 'pending.json'),
                      ('no_rows_duas', 'empty.txt')]}
            store.export(paths, MOVEMENT_FIELDS)
            with (self.root / 'rows.csv').open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(list(csv.DictReader(stream)), [])
            self.assertEqual((self.root / 'pending.txt').read_text(), '')
            self.assertEqual(json.loads((self.root / 'vacios.json').read_text())['empty'][0]['dua'], DUA)
            store.close()
            store = MovementsJobStore(p)
            store.begin_run()
            self.assertIsNone(store.claim(1))
            self.assertEqual(store.queue_empty([DUA]), [DUA])
            job = store.claim(1)
            row = dict(zip(MOVEMENT_FIELDS, ['0001', '2026', '000001', 'INGRESO', DUA, '3.0']))
            store.complete(job, {**row, 'rows': [row]})
            self.assertEqual((store.summary()['succeeded'], store.summary()['empty']), (1, 0))
            self.assertEqual(store.db.execute('SELECT outcome FROM attempts ORDER BY id').fetchall()[0][0], 'empty')
        finally:
            store.close()

    def test_recheck_failure_stays_real_error_and_history_keeps_original_empty(self):
        store = MovementsJobStore(self.root / 'queue.sqlite3')
        try:
            store.import_values([DUA]); store.begin_run()
            store.complete(store.claim(1), empty_record(DUA, html()))
            store.queue_empty()
            store.retry(store.claim(1), 'Timeout esperando TICA', 'TimeoutError')
            self.assertEqual((store.summary()['empty'], store.summary()['retry']), (0, 1))
            self.assertEqual(store.db.execute('SELECT count(*) FROM empty_observations').fetchone()[0], 1)
            self.assertEqual([r[0] for r in store.db.execute('SELECT outcome FROM attempts ORDER BY id')], ['empty', 'retry'])
        finally:
            store.close()

    def test_legacy_migration_requires_evidence_and_preserves_links_and_attempts(self):
        p = self.root / 'queue.sqlite3'
        old = JobStore(p)
        unknown = '001-2026-000003'
        old.import_values([DUA, OTHER, unknown]); old.begin_run()
        evidence = self.root / 'empty.html'; evidence.write_text(html(), encoding='utf-8')
        old.retry(old.claim(1), DUA, 'NoMovimientosError', str(evidence))
        old.retry(old.claim(1), 'Timeout', 'TimeoutError', str(evidence))
        old.retry(old.claim(1), unknown, 'NoMovimientosError')
        before = [tuple(r) for r in old.db.execute('SELECT * FROM attempts')]
        schema = old.db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
        old.close()
        # Reproducir la restricción exacta de una cola de la versión anterior.
        with closing(sqlite3.connect(p)) as db:
            db.execute('PRAGMA writable_schema=ON')
            db.execute("UPDATE sqlite_master SET sql=? WHERE name='jobs'", (schema.replace(",'empty'", ''),))
            db.execute('PRAGMA schema_version=99'); db.commit()
        store = MovementsJobStore(p)
        try:
            self.assertEqual([(r[0], r[1]) for r in store.db.execute('SELECT dua,status FROM jobs ORDER BY rowid')], [(DUA, 'empty'), (OTHER, 'retry'), (unknown, 'retry')])
            self.assertEqual([tuple(r) for r in store.db.execute('SELECT * FROM attempts')], before)
            self.assertFalse(store.db.execute('PRAGMA foreign_key_check').fetchall())
            self.assertEqual(store.db.execute('SELECT count(*) FROM source_rows').fetchone()[0], 3)
            self.assertEqual(len(list((self.root / 'backups').glob('*.sqlite3'))), 1)
            catalog = TableCatalog(self.root, store_factory=MovementsJobStore)
            with catalog.connection() as db:
                db.execute('''INSERT INTO saved_tables(id,name,name_key,filename,source_path,source_sheet,output_name)
                              VALUES ('test','Prueba','prueba','queue.sqlite3','source.xlsx','base','Prueba')''')
            self.assertEqual([r['dua'] for r in catalog.read_rows('test', 'retry')[1]], [OTHER])
            self.assertEqual([r['dua'] for r in catalog.read_rows('test', 'unverified_empty')[1]], [unknown])
            self.assertEqual(store.queue_empty(), [DUA, unknown])
        finally:
            store.close()

    def test_empty_completes_daily_scope_and_explicit_recheck_reopens_it(self):
        p = self.root / 'queue.sqlite3'
        store = MovementsJobStore(p)
        store.import_values([DUA, OTHER]); store.close()
        scoped = type('ScopedMovements', (DailyJobStore, MovementsJobStore), {})
        record = {'id': 'month'}
        def execute(command, request):
            store = scoped(p, request['daily_duas'])
            try:
                store.begin_run()
                store.complete(store.claim(1), empty_record(DUA, html()))
            finally:
                store.close()
        service = SimpleNamespace(root=self.root, profile={'id': 'xmovimientos'}, stop_event=Event(),
                                  read_database=lambda _: closing(sqlite3.connect(p)), execute=execute)
        daily = DailyCoordinator(service)
        daily.append_day = lambda day, duas: record
        daily.emit = lambda *args, **kwargs: None
        day = date(2026, 9, 1)
        daily.ledger.save_base(day, [DUA])
        daily.ledger.update(day, table_id='month')
        self.assertTrue(daily.cycle(day))
        status = daily.ledger.get(day)
        self.assertEqual((status['state'], status['succeeded'], status['empty']), ('completed', 0, 1))
        store = MovementsJobStore(p)
        try:
            self.assertEqual(store.summary()['pending'], 1)  # El DUA ajeno al día sigue intacto.
            store.queue_empty([DUA]); store.begin_run()
            daily.reopen([DUA])
            self.assertEqual(daily.ledger.get(day)['state'], 'pending')
            store.retry(store.claim(1), 'Timeout', 'TimeoutError')
        finally:
            store.close()
        daily.reconcile(record)
        self.assertEqual(daily.ledger.get(day)['state'], 'pending')
        self.assertEqual(daily.ledger.get(day)['empty'], 0)


if __name__ == '__main__':
    unittest.main()
