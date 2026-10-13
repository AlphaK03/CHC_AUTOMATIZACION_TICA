import asyncio
import csv
import html
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_conocimientos_queue import grid_for
from conocimientos import KnowledgeStore, IncompleteTable
from conocimientos_flow import ConocimientosFlow
from conocimientos_queue import OutputLock
from organizar_resultados import organize_results, checksum
from resultados import output_paths, resolve_path, exclusion_csv_path
from tablas_manifiesto import HEADERS, FIELDS, LINK_FIELDS, ManifestTableStore, parse_table

MID = '1-0-20260376-P027-06/08/26'


def table_html(flow, values):
    grid = {'Count': len(values), 'Columns': [{} for _ in HEADERS[flow]]}
    if values:
        grid['0'] = {'Props': [[field + '_0001'] for field in FIELDS[flow]]}
    state = dict(zip(['CGTPOTRANS', 'CGTPOMIC', 'CGNROMIC', 'RGDEPID', 'CGFCHARR'], MID.split('-')))
    state.update(Grid1ContainerData=json.dumps(grid), nRC_Grid1=str(len(values)))
    return ''.join(f'<input name="{key}" value="{html.escape(json.dumps(data), quote=True)}">'
                   for key, data in [('GXState', state), ('Grid1ContainerDataV', values)])


class TableParserTests(unittest.TestCase):
    def test_original_values_zeroes_empty_column_and_valid_empty(self):
        for flow in HEADERS:
            row = ['0001', '002'] + [''] * (len(HEADERS[flow]) - 2)
            parsed = parse_table(table_html(flow, [row]), MID, flow)
            self.assertEqual(parsed.rows, [[*row, MID]])
            self.assertTrue(parsed.eof)
            self.assertEqual(parse_table(table_html(flow, []), MID, flow).rows, [])

    def test_count_identity_width_and_changed_schema_are_rejected(self):
        row = [''] * len(HEADERS['duas'])
        source = table_html('duas', [row])
        for bad, mid in [(source, MID.replace('20260376', '20260000')),
                         (table_html('duas', [row[:-1]]), MID),
                         (source.replace('CGNROLIN_', 'OTHER_'), MID),
                         (source.replace('&quot;nRC_Grid1&quot;: &quot;1&quot;', '&quot;nRC_Grid1&quot;: &quot;2&quot;'), MID)]:
            with self.assertRaises(IncompleteTable):
                parse_table(bad, mid, 'duas')

    def test_movements_combo_property_field_is_checked(self):
        source = table_html('movimientos', [[''] * len(HEADERS['movimientos'])])
        source = source.replace('[&quot;CGMOVTPO_0001&quot;]', '[{&quot;s&quot;: &quot;ENT&quot;}, &quot;CGMOVTPO_0001&quot;]')
        self.assertEqual(len(parse_table(source, MID, 'movimientos').rows), 1)


class TableStoreTests(unittest.TestCase):
    def test_legacy_import_preserves_rows_and_offline_export_factory(self):
        for flow in HEADERS:
            with self.subTest(flow=flow), tempfile.TemporaryDirectory() as folder:
                paths = output_paths({f'output_manifest_{flow}_folder': folder}, flow, 'maritimo', 8, 2026)
                original = ['0001', '0002'] + [''] * (len(HEADERS[flow]) - 2) + [MID]
                with paths.csv.open('w', encoding='utf-8-sig', newline='') as stream:
                    csv.writer(stream).writerows([[f'index_flujo_{flow}', *HEADERS[flow], 'manifiesto'], [1, *original]])
                before = checksum(paths.csv)
                store = ManifestTableStore(paths.csv, {'flow': flow}, db_path=paths.database)
                archive = paths.database.parent / 'historicos' / paths.csv.name
                self.assertEqual(checksum(archive), before)
                self.assertFalse(archive.is_relative_to(Path(folder)/'resultados'))
                self.assertTrue(store.completed(MID))
                store.prepare_selection([(1, 'url', {}, MID)])
                store.start_run()
                self.assertEqual(store.finish_run(0)['saved'], 1)
                store.export(paths.failures)
                self.assertEqual(checksum(paths.csv), before)
                self.assertFalse(paths.failures.exists())
                expected_csvs = {paths.csv, exclusion_csv_path(paths.csv)} if flow == 'duas' else {paths.csv}
                self.assertEqual(set(paths.csv.parent.rglob('*.csv')), expected_csvs)
                store.close()
                reopened = KnowledgeStore.open_existing(paths.database)
                self.assertIsInstance(reopened, ManifestTableStore)
                self.assertEqual(reopened.csv_path, paths.csv)
                reopened.export()
                self.assertEqual(checksum(paths.csv), before)
                reopened.close()

    def test_finish_retains_duplicates_and_original_order(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = output_paths({'output_manifest_duas_folder': folder}, 'duas', 'maritimo', 8, 2026)
            store = ManifestTableStore(paths.csv, {'flow': 'duas'}, db_path=paths.database)
            row = ['0001'] + [''] * (len(HEADERS['duas']) - 1) + [MID]
            store.prepare_selection([(1, 'url', {}, MID)])
            store.start_run(); store.claim(MID)
            store.save(MID, 1, [row, row], {'pages': 1, 'read': 2, 'kept': 2})
            store.finish_run(1); store.export()
            with paths.csv.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream))[1:]
            self.assertEqual(rows, [['1', *row], ['2', *row]])
            store.close()


class TrackedQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_flows_357_rows_concurrent_and_only_pending_retried(self):
        for flow_name in HEADERS:
            with self.subTest(flow=flow_name), tempfile.TemporaryDirectory() as folder:
                paths = output_paths({f'output_manifest_{flow_name}_folder': folder}, flow_name, 'maritimo', 8, 2026)
                flow = ConocimientosFlow()
                flow.URL = 'https://example/hcicgmic.aspx'
                flow.config = {'conocimientos_concurrencia': 8}
                flow.conoc_failed_rows, flow.conoc_stats = [], []
                flow.conoc_store = ManifestTableStore(paths.csv, {'flow': flow_name}, db_path=paths.database)
                flow.conoc_main_grid = grid_for(357)
                for index in range(357):
                    flow.conoc_main_grid[str(index)]['Props'][-1][0] = LINK_FIELDS[flow_name] + f'_{index+1:04d}'
                flow.conoc_main_values = [[p[1] for p in flow.conoc_main_grid[str(i)]['Props']] for i in range(357)]
                active, maximum, called = 0, 0, []
                async def fetch(href, ordinal, info):
                    nonlocal active, maximum
                    active += 1; maximum = max(maximum, active); called.append(ordinal)
                    try:
                        await asyncio.sleep(0)
                        if ordinal % 13 == 0:
                            raise TimeoutError('network')
                        mid = '-'.join(info.values())
                        row = ['0001'] + [''] * (len(HEADERS[flow_name]) - 1) + [mid]
                        return mid, [row], {'pages': 1, 'read': 1, 'kept': 1}
                    finally:
                        active -= 1
                await flow.process_conocimientos_links(link_field=LINK_FIELDS[flow_name], fetch_result=fetch)
                self.assertEqual(maximum, 8)
                self.assertEqual(sorted(called), list(range(1, 358)))
                self.assertEqual((flow.conoc_progress['saved'], flow.conoc_progress['pending']), (330, 27))
                called = []
                async def retry(href, ordinal, info):
                    called.append(ordinal)
                    mid = '-'.join(info.values())
                    return mid, [['0001'] + [''] * (len(HEADERS[flow_name])-1) + [mid]], {'pages': 1, 'read': 1, 'kept': 1}
                await flow.process_conocimientos_links(link_field=LINK_FIELDS[flow_name], fetch_result=retry)
                self.assertEqual(called, list(range(13, 358, 13)))
                self.assertEqual(flow.conoc_progress['saved'], 357)
                flow.conoc_store.export()
                with paths.csv.open(encoding='utf-8-sig', newline='') as stream:
                    rows = list(csv.reader(stream))[1:]
                self.assertEqual([int(row[0]) for row in rows], list(range(1, 358)))
                flow.conoc_store.close()


class OutputPathsTests(unittest.TestCase):
    def test_relative_paths_are_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            self.assertEqual(resolve_path('resultados'), Path(folder) / 'resultados')
            paths = output_paths({}, 'duas', 'aereo', 2, 2026)
            self.assertEqual(paths.csv, Path(folder)/'resultados/duas/2026/aereo/duas_aereo_febrero26.csv')
            self.assertEqual(paths.database, Path(folder)/'datos_app/SQLite/duas/2026/aereo/duas_aereo_2026_02.sqlite3')

    def test_organization_preserves_database_and_data_and_separates_control(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = {'output_manifest_conocimientos_folder': folder}
            old = root/'conocimientos_maritimo_2026_08.csv'
            store = KnowledgeStore(old, {})
            store.save(MID, 1, [[MID, '1', '00001', 'N'] + ['']*11], {'pages':1})
            store.export(); store.close()
            state = root/'conocimientos_maritimo_2026_08_estado.csv'; state.write_text('state')
            before_db, before_csv = checksum(old.with_suffix('.sqlite3')), checksum(old)
            records = organize_results(config, only=('conocimientos','maritimo',8,2026))
            paths = output_paths(config,'conocimientos','maritimo',8,2026)
            self.assertEqual(checksum(paths.database), before_db)
            self.assertEqual(checksum(paths.csv), before_csv)
            self.assertTrue((paths.period/'conocimientos_estado_maritimo_agosto26.csv').exists())
            self.assertEqual(len(records), 3)
            self.assertEqual(organize_results(config, only=('conocimientos','maritimo',8,2026)), [])

    def test_active_database_is_not_moved(self):
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder)/'conocimientos_maritimo_2026_08.csv'
            store = KnowledgeStore(old, {})
            records = organize_results({'output_manifest_conocimientos_folder':folder}, only=('conocimientos','maritimo',8,2026))
            self.assertTrue(old.with_suffix('.sqlite3').exists())
            self.assertEqual(records[0]['state'], 'Pospuesto')
            store.close()
