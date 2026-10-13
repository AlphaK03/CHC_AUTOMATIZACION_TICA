import asyncio
import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import AsyncMock

from conocimientos import PortalErrorPage, IncompleteTable, KnowledgeStore
from conocimientos_queue import QueueStore
from resultados import exclusion_csv_path, output_paths
from tablas_manifiesto import ManifestTableStore, parse_table, HEADERS
from test_duas_independientes import TrackedFlow, response
from test_conocimientos_queue import grid_for
from test_tablas_manifiesto import MID, table_html

ERROR_HTML = '<form action="./frmAmbiente?aspxerrorpath=%2fTica%2fhcgduama.aspx" id="form1"></form>'
ACTUAL_ERROR = Path(__file__).resolve().parents[1]/'src/pruebas_astracode/diagnostico_duas_20261010/tabla_grande/respuesta_error_200.html'


class ErrorPageTests(unittest.TestCase):
    def test_saved_response_and_encoded_form_variants_are_classified(self):
        sources = [ERROR_HTML,
                   '<form action="https://example/Reporting/FRMAMBIENTE.aspx?ASPXERRORPATH=/TICA/HCGDUAMA.ASPX&amp;x=1"></form>']
        if ACTUAL_ERROR.exists():
            sources.append(ACTUAL_ERROR.read_text(encoding='utf-8'))
        for source in sources:
            with self.subTest(source_size=len(source)), self.assertRaises(PortalErrorPage):
                parse_table(source, MID, 'duas')

    def test_unrelated_errors_and_valid_empty_tables_are_not_excluded(self):
        for source in ('<html>Error 200 sin formulario</html>',
                       '<form action="frmAmbiente?aspxerrorpath=/Tica/otro.aspx"></form>',
                       '<a href="frmAmbiente?aspxerrorpath=/Tica/hcgduama.aspx">Inicio</a>',
                       '<form action="frmAmbiente"></form>'):
            with self.subTest(source=source):
                with self.assertRaises(IncompleteTable) as error:
                    parse_table(source, MID, 'duas')
                self.assertNotIsInstance(error.exception, PortalErrorPage)
        source = table_html('duas', []) + ERROR_HTML
        self.assertEqual(parse_table(source, MID, 'duas').rows, [])
        with self.assertRaises(IncompleteTable) as error:
            parse_table(ERROR_HTML, MID, 'movimientos')
        self.assertNotIsInstance(error.exception, PortalErrorPage)

    def test_count_mismatch_remains_retryable(self):
        source = table_html('duas', [['']*len(HEADERS['duas'])])
        source = source.replace('&quot;nRC_Grid1&quot;: &quot;1&quot;', '&quot;nRC_Grid1&quot;: &quot;2&quot;')
        with self.assertRaises(IncompleteTable) as error:
            parse_table(source, MID, 'duas')
        self.assertNotIsInstance(error.exception, PortalErrorPage)


def create_old_database(folder):
    paths = output_paths({'output_manifest_duas_folder': folder}, 'duas', 'aereo', 9, 2026)
    store = ManifestTableStore(paths.csv, {'flow': 'duas'}, db_path=paths.database)
    second = MID.replace('20260376', '00000377')
    store.prepare_selection([(19, 'url', {}, MID), (20, 'url', {}, second)])
    store.start_run()
    store.claim(MID)
    row = ['000001', '0002'] + ['']*(len(HEADERS['duas'])-2) + [MID]
    store.save(MID, 1, [row, row], {'pages': 1, 'read': 2, 'kept': 2})
    store.claim(second)
    store.fail(second, 2, 'network')
    store.finish_run(2)
    store.export()
    store.close()
    db = sqlite3.connect(paths.database)
    schema = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
    schema = schema.replace("'Guardado','Excluido'", "'Guardado'").replace('CREATE TABLE jobs', 'CREATE TABLE jobs_old')
    with db:
        db.execute(schema)
        db.execute('INSERT INTO jobs_old SELECT * FROM jobs')
        db.execute('DROP TABLE jobs')
        db.execute('ALTER TABLE jobs_old RENAME TO jobs')
    db.close()
    return paths, second


class MigrationTests(unittest.TestCase):
    def test_old_database_preserves_data_history_and_supports_exclusion_on_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, second = create_old_database(folder)
            with closing(sqlite3.connect(paths.database)) as db:
                before = {name: db.execute(f'SELECT * FROM {name}').fetchall()
                          for name in ('jobs', 'rows', 'manifests', 'failures', 'attempts', 'runs')}
            store = KnowledgeStore.open_existing(paths.database)
            for name, records in before.items():
                self.assertEqual(store.db.execute(f'SELECT * FROM {name}').fetchall(), records)
            store.start_run()
            store.claim(second)
            store.exclude(second, 2, 'frmAmbiente')
            totals = store.finish_run(1)
            self.assertEqual((totals['saved'], totals['excluded'], totals['pending'], totals['accounted']), (1, 1, 0, 2))
            store.export()
            store.close()
            reopened = KnowledgeStore.open_existing(paths.database)
            self.assertEqual(reopened.job(second)['state'], 'Excluido')
            self.assertEqual(reopened.job(second)['attempts'], 2)
            reopened.close()
            with paths.csv.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(len(rows), 3)  # Dos duplicados originales, con sus ceros.
            self.assertEqual(rows[1][1:3], ['000001', '0002'])
            with exclusion_csv_path(paths.csv).open(encoding='utf-8-sig', newline='') as stream:
                excluded = list(csv.DictReader(stream))
            self.assertEqual(excluded[0]['IDManifiesto'], second)
            self.assertEqual(excluded[0]['Fila origen'], '20')
            self.assertEqual(excluded[0]['Motivo'], 'frmAmbiente')
            self.assertEqual(set(paths.csv.parent.rglob('*.csv')), {paths.csv, exclusion_csv_path(paths.csv)})

    def test_migration_failure_rolls_back_the_original_table(self):
        with tempfile.TemporaryDirectory() as folder:
            paths, _ = create_old_database(folder)
            db = sqlite3.connect(paths.database)
            before = db.execute('SELECT * FROM jobs').fetchall()
            class BrokenMigration:
                def execute(self, sql, *args):
                    if sql == 'DROP TABLE jobs':
                        raise sqlite3.OperationalError('simulated migration failure')
                    return db.execute(sql, *args)
                def commit(self):
                    db.commit()
                def rollback(self):
                    db.rollback()
            queue = QueueStore()
            queue.db = BrokenMigration()
            with self.assertRaises(sqlite3.OperationalError):
                queue._migrate_excluded_state()
            self.assertEqual(db.execute('SELECT * FROM jobs').fetchall(), before)
            self.assertNotIn('Excluido', db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0])
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='jobs_with_exclusions'").fetchone())
            db.close()


class ExclusionFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_error_page_is_terminal_regular_errors_retry_and_both_csvs_export(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = output_paths({'output_manifest_duas_folder': folder}, 'duas', 'aereo', 9, 2026)
            flow = TrackedFlow()
            flow.URL, flow.table_flow, flow.timeout, flow.table_user_agent = 'https://example/main', 'duas', 120, 'ua'
            flow.config = {'conocimientos_concurrencia': 2, 'conocimientos_refresco_segundos': 600}
            flow.conoc_failed_rows, flow.conoc_stats = [], []
            flow.conoc_store = ManifestTableStore(paths.csv, {'flow': 'duas'}, db_path=paths.database)
            grid = grid_for(4)
            for i in range(4):
                grid[str(i)]['Props'][-1][0] = f'vVDUAS_{i+1:04d}'
            flow.conoc_main_grid = grid
            flow.conoc_main_values = [[p[1] for p in grid[str(i)]['Props']] for i in range(4)]
            ids = ['-'.join(row[:5]) for row in flow.conoc_main_values]
            flow.context = SimpleNamespace(cookies=AsyncMock(return_value=[]))
            called = []
            async def new_context(**kwargs):
                async def get(url, **kwargs):
                    index = int(url.split('?')[-1])
                    called.append(index)
                    if index == 0:
                        return response(ERROR_HTML)
                    if index == 1:
                        return response('server failed', 503)
                    if index == 2:
                        return response('<html>Otro error 200 sin formulario</html>')
                    source = table_html('duas', [])
                    for before, after in zip(MID.split('-'), ids[index].split('-')):
                        source = source.replace(f'&quot;{before}&quot;', f'&quot;{after}&quot;')
                    return response(source)
                return SimpleNamespace(get=AsyncMock(side_effect=get), dispose=AsyncMock())
            flow.request_factory = SimpleNamespace(new_context=AsyncMock(side_effect=new_context))
            await flow.process_conocimientos_links(link_field='vVDUAS', fetch_result=flow._fetch_tracked_result)
            self.assertEqual(sorted(called), [0, 1, 2, 3])
            self.assertEqual([job['state'] for job in flow.conoc_store.jobs()],
                             ['Excluido', 'Pendiente', 'Pendiente', 'Guardado'])
            self.assertEqual(flow.conoc_progress['excluded'], 1)
            self.assertEqual(flow.conoc_progress['accounted'], 4)
            self.assertEqual(flow.conoc_store.db.execute('SELECT state FROM attempts WHERE manifest=?', (ids[0],)).fetchone()[0], 'Excluido')
            flow.conoc_store.export()
            flow.conoc_store.close()
            with exclusion_csv_path(paths.csv).open(encoding='utf-8-sig', newline='') as stream:
                excluded = list(csv.DictReader(stream))
            self.assertEqual([item['IDManifiesto'] for item in excluded], [ids[0]])
            called.clear()
            flow.conoc_store = KnowledgeStore.open_existing(paths.database)
            await flow.process_conocimientos_links(link_field='vVDUAS', fetch_result=flow._fetch_tracked_result)
            self.assertEqual(sorted(called), [1, 2])  # No vuelve a consultar frmAmbiente ni el vacío válido.
            self.assertEqual(flow.conoc_store.job(ids[0])['attempts'], 1)
            self.assertEqual(flow.conoc_progress['accounted'], 4)
            flow.conoc_store.export()
            flow.conoc_store.close()

    async def test_all_excluded_has_no_requests_on_resume_and_exports_header_only_results(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ManifestTableStore(Path(folder)/'duas_aereo_2026_09.csv', {'flow': 'duas'})
            store.prepare_selection([(20, 'url', {}, MID)])
            store.start_run()
            store.claim(MID)
            store.exclude(MID, 1, 'frmAmbiente')
            totals = store.finish_run(1)
            self.assertEqual(totals['accounted'], 1)
            self.assertEqual(store.db.execute('SELECT state FROM runs WHERE id=?', (store.run_id,)).fetchone()[0], 'Finalizada con exclusiones')
            store.start_run()
            totals = store.finish_run(0)
            self.assertEqual((totals['excluded'], totals['pending'], totals['processed_run']), (1, 0, 0))
            with self.assertRaises(RuntimeError):
                store.claim(MID)
            store.export()
            with store.csv_path.open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(len(list(csv.reader(stream))), 1)
            store.close()
