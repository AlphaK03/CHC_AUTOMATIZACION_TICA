import csv
import html
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from conocimientos import (COLUMNS, FIELDS, IDENTITY, IncompleteTable,
                            KnowledgeStore, extract_table, parse_page)
from conocimientos_flow import ConocimientosFlow

MID = '4-0-26004445-P001-28/02/26'


def page(rows, offset=0, eof=True, manifest=MID):
    values = [[str(seq), bl, courier, '', 'HWB', '00123', 'Transportista',
               '188AJU', 'ALAJUELA\xa0', '', '840MIA', 'MIAMI', 'CER', '']
              for seq, bl, courier in rows]
    state = dict(zip(IDENTITY, manifest.split('-')))
    grid = {'Count': len(values)}
    if values:
        grid['0'] = {'Props': [[f + '_0001'] for f in FIELDS]}
    state.update({'Grid1ContainerData': json.dumps(grid), 'nRC_Grid1': str(len(values)),
                  'GRID1_nFirstRecordOnPage': str(offset), 'GRID1_nEOF': '1' if eof else '0'})
    return ''.join(f'<input name="{k}" value="{html.escape(v, quote=True)}">' for k, v in
                   [('GXState', json.dumps(state)), ('Grid1ContainerDataV', json.dumps(values))])


class PaginationTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_pages_sorted_filter_applied_after_reading_and_zeroes_preserved(self):
        pages = [page([(10, '0010', 'S'), (2, '0002', 'N')], eof=False),
                 page([(7, '0007', 'N')], offset=2)]
        request = AsyncMock()
        with patch('conocimientos.request_html', AsyncMock(side_effect=pages)) as fetch:
            rows, stats = await extract_table(request, 'https://example/hcgcons.aspx', MID, courier='N')
        self.assertEqual([r[1:4] for r in rows], [['2', '0002', 'N'], ['7', '0007', 'N']])
        self.assertEqual(stats, {'pages': 2, 'read': 3, 'kept': 2})
        form = fetch.call_args_list[1].args[3]
        self.assertEqual(form['GRID1PAGING'], 'NEXT')
        self.assertEqual(json.loads(form['GXState'])['_EventName'], 'EGRID1PAGING.')

    async def test_repeated_page_is_failure_not_partial_success(self):
        response = page([(1, 'BL1', 'N')], eof=False)
        with patch('conocimientos.request_html', AsyncMock(return_value=response)):
            with self.assertRaisesRegex(IncompleteTable, 'Página repetida'):
                await extract_table(AsyncMock(), 'url', MID)

    async def test_last_page_not_requested_again(self):
        with patch('conocimientos.request_html', AsyncMock(return_value=page([(1, 'BL1', 'N')]))) as fetch:
            rows, stats = await extract_table(AsyncMock(), 'url', MID)
        self.assertEqual(fetch.await_count, 1)
        self.assertEqual(stats['pages'], 1)

    async def test_timeout_discards_partial_table(self):
        with patch('conocimientos.request_html', AsyncMock(side_effect=[
                page([(1, 'BL1', 'N')], eof=False), TimeoutError('red')])):
            with self.assertRaises(TimeoutError):
                await extract_table(AsyncMock(), 'url', MID)

    async def test_duplicate_sequence_is_detected(self):
        with patch('conocimientos.request_html', AsyncMock(side_effect=[
                page([(1, 'BL1', 'N')], eof=False), page([(1, 'BL2', 'N')], offset=1)])):
            with self.assertRaisesRegex(IncompleteTable, 'Secuencia repetida'):
                await extract_table(AsyncMock(), 'url', MID)

    async def test_confirmed_empty_is_valid(self):
        with patch('conocimientos.request_html', AsyncMock(return_value=page([]))):
            rows, stats = await extract_table(AsyncMock(), 'url', MID)
        self.assertEqual(rows, [])
        self.assertEqual(stats['read'], 0)

    def test_wrong_manifest_and_invalid_html_rejected(self):
        with self.assertRaisesRegex(IncompleteTable, 'Manifiesto inesperado'):
            parse_page(page([(1, 'BL', 'N')]), MID.replace('26004445', '26004446'))
        with self.assertRaises(IncompleteTable):
            parse_page('<html>Error del servidor</html>', MID)

    def test_empty_without_eof_and_changed_schema_rejected(self):
        with self.assertRaises(IncompleteTable):
            parse_page(page([], eof=False), MID)
        with self.assertRaises(IncompleteTable):
            parse_page(page([(1, 'BL', 'N')]).replace('CGNROCON_', 'RENAMED_'), MID)


class StorageTests(unittest.TestCase):
    def test_resume_empty_order_dedup_retry_and_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'conocimientos.csv'
            failure_path = Path(folder) / 'fallidos.csv'
            store = KnowledgeStore(path, {'courier': 'N'})
            store.fail('b', 2, 'red')
            row_a = ['a', '1', '001', 'N'] + [''] * 11
            row_b = ['b', '2', '002', 'N'] + [''] * 11
            store.save('b', 2, [row_b], {})
            store.save('a', 1, [row_a], {})
            store.save('vacio', 3, [], {})
            store.close()
            store = KnowledgeStore(path, {'courier': 'N'})
            self.assertTrue(store.completed('vacio'))
            store.save('a', 1, [row_a], {})
            self.assertEqual(store.summary(), {'manifests': 3, 'rows': 2, 'failures': 0})
            store.export(failure_path)
            store.close()
            with path.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows, [COLUMNS, row_a, row_b])
            with self.assertRaisesRegex(ValueError, 'otros filtros'):
                KnowledgeStore(path, {'courier': None})

    def test_existing_untracked_csv_is_not_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'existing.csv'
            path.write_text('original', encoding='utf-8')
            with self.assertRaises(ValueError):
                KnowledgeStore(path, {})
            self.assertEqual(path.read_text(encoding='utf-8'), 'original')


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_compressed_manifest_links_selection_order_failure_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = ConocimientosFlow()
            flow.URL = 'https://example/Tica/hcicgmic.aspx'
            flow.config = {'output_manifest_conocimientos_folder': folder,
                           'conocimientos_concurrencia': 2}
            flow.init_conoc_output('aereo', 2, 2026)
            second = MID.replace('26004445', '26004446')
            flow.conoc_main_grid = {'Count': 2,
                '0': {'Props': [[k + '_0001', v] for k, v in zip(IDENTITY, MID.split('-'))]
                       + [['vVCONS_0001', 'hcgcons.aspx?uno']]},
                '1': {'Props': [['CGTPOTRANS_0002'], ['CGTPOMIC_0002'],
                       ['CGNROMIC_0002', '26004446'], ['RGDEPID_0002'],
                       ['CGFCHARR_0002'], ['vVCONS_0002', 'hcgcons.aspx?dos']]}}
            flow.conoc_main_values = [MID.split('-') + ['icon'], second.split('-') + ['icon']]
            row = [MID, '1', '001', 'N'] + [''] * 11
            flow._fetch_conoc_result = AsyncMock(side_effect=[
                (MID, [row], {'pages': 1}), TimeoutError('red')])
            await flow.process_conocimientos_links()
            self.assertEqual(flow.conoc_summary, {'manifests': 1, 'rows': 1, 'failures': 1})
            self.assertEqual(flow._fetch_conoc_result.call_args_list[1].args[2]['Fecha'], '28/02/26')
            flow._fetch_conoc_result = AsyncMock(return_value=(second, [], {'pages': 1}))
            await flow.process_conocimientos_links()
            self.assertEqual(flow._fetch_conoc_result.await_count, 1)
            self.assertEqual(flow.conoc_summary, {'manifests': 2, 'rows': 1, 'failures': 0})
            flow.write_conoc_failures()
            flow.conoc_store.close()


if __name__ == '__main__':
    unittest.main()
