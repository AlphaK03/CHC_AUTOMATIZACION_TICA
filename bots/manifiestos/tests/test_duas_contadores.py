import csv
import tempfile
import json
from html import escape
import unittest
from pathlib import Path

from conocimientos import IncompleteTable, PortalErrorPage, KnowledgeStore, FormInputs
from tablas_manifiesto import ManifestTableStore, HEADERS, parse_table
from resultados import exclusion_csv_path
from test_tablas_manifiesto import MID, table_html

REASON = "Respuesta de duas inválida: invalid literal for int() with base 10: '****'"


def change_grid_count(source, count):
    form = FormInputs(source).values
    state = json.loads(form['GXState'])
    grid = json.loads(state['Grid1ContainerData'])
    grid['Count'] = count
    state['Grid1ContainerData'] = json.dumps(grid)
    form['GXState'] = json.dumps(state)
    return ''.join(f'<input name="{name}" value="{escape(value, quote=True)}">' for name, value in form.items())


class GridCounterTests(unittest.TestCase):
    def test_61356_rows_with_negative_nrc_are_saved_and_exported_in_full(self):
        row = ['00001', '00002'] + ['']*(len(HEADERS['duas'])-2)
        source = table_html('duas', [row]*61356)
        source = source.replace('&quot;nRC_Grid1&quot;: &quot;61356&quot;', '&quot;nRC_Grid1&quot;: &quot;-4180&quot;')
        parsed = parse_table(source, MID, 'duas')
        self.assertEqual(len(parsed.rows), 61356)
        self.assertTrue(parsed.eof)
        with tempfile.TemporaryDirectory() as folder:
            store = ManifestTableStore(Path(folder)/'duas_aereo_2026_09.csv', {'flow': 'duas'})
            self.addCleanup(store.close)
            store.prepare_selection([(20, 'url', {}, MID)])
            store.start_run()
            store.claim(MID)
            store.save(MID, 1, parsed.rows, {'pages': 1, 'read': 61356, 'kept': 61356})
            self.assertEqual(store.finish_run(1)['saved'], 1)
            self.assertEqual(store.summary()['rows'], 61356)
            store.export()
            with store.csv_path.open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.reader(stream)
                next(reader)
                first = next(reader)
                last = first
                count = 1
                for last in reader:
                    count += 1
            self.assertEqual(count, 61356)
            self.assertEqual(first[1:3], ['00001', '00002'])
            self.assertEqual(last[1:3], ['00001', '00002'])
            self.assertEqual((first[0], last[0]), ('1', '61356'))
            store.close()

    def test_signed_16_counter_boundaries_and_multiple_wraps(self):
        row = ['00001'] + ['']*(len(HEADERS['duas'])-1)
        for total in (32768, 65536, 65537, 100000):
            signed = (total + 32768) % 65536 - 32768
            source = table_html('duas', [row]*total).replace(f'&quot;nRC_Grid1&quot;: &quot;{total}&quot;',
                                                          f'&quot;nRC_Grid1&quot;: &quot;{signed}&quot;')
            with self.subTest(total=total):
                self.assertEqual(len(parse_table(source, MID, 'duas').rows), total)

    def test_negative_counter_with_wrong_count_or_wrong_schema_stays_retryable(self):
        row = ['00001'] + ['']*(len(HEADERS['duas'])-1)
        source = table_html('duas', [row]*32768).replace('&quot;nRC_Grid1&quot;: &quot;32768&quot;',
                                                      '&quot;nRC_Grid1&quot;: &quot;-32768&quot;')
        for invalid in (source.replace('&quot;-32768&quot;', '&quot;-32767&quot;'),
                        change_grid_count(source, 32769),
                        source.replace('CGNROLIN_', 'OTHER_')):
            with self.assertRaises(IncompleteTable) as error:
                parse_table(invalid, MID, 'duas')
            self.assertNotIsInstance(error.exception, PortalErrorPage)
        small = table_html('duas', [row]).replace('&quot;nRC_Grid1&quot;: &quot;1&quot;',
                                               '&quot;nRC_Grid1&quot;: &quot;-65535&quot;')
        with self.assertRaises(IncompleteTable):
            parse_table(small, MID, 'duas')

    def test_overflow_counter_uses_numeric_grid_count_and_preserves_every_row_and_zero(self):
        row = ['00001', '00002'] + ['']*(len(HEADERS['duas'])-2)
        source = table_html('duas', [row]*10000)
        source = source.replace('&quot;nRC_Grid1&quot;: &quot;10000&quot;', '&quot;nRC_Grid1&quot;: &quot;****&quot;')
        parsed = parse_table(source, MID, 'duas')
        self.assertEqual(len(parsed.rows), 10000)
        self.assertEqual(parsed.rows[0], [*row, MID])
        self.assertEqual(parsed.rows[-1], [*row, MID])
        self.assertTrue(parsed.eof)

    def test_grid_count_overflow_is_checked_against_numeric_nrc(self):
        row = ['00001'] + ['']*(len(HEADERS['duas'])-1)
        source = change_grid_count(table_html('duas', [row]*10), '*')
        self.assertEqual(len(parse_table(source, MID, 'duas').rows), 10)
        both_masked = source.replace('&quot;nRC_Grid1&quot;: &quot;10&quot;', '&quot;nRC_Grid1&quot;: &quot;*&quot;')
        with self.assertRaises(IncompleteTable):
            parse_table(both_masked, MID, 'duas')

    def test_bad_counter_and_impossible_overflow_remain_pending_errors(self):
        row = ['']*len(HEADERS['duas'])
        for count in ('****', 'not-a-number', '2', '****0'):
            source = table_html('duas', [row]).replace('&quot;nRC_Grid1&quot;: &quot;1&quot;',
                                                      f'&quot;nRC_Grid1&quot;: &quot;{count}&quot;')
            with self.subTest(count=count), self.assertRaises(IncompleteTable) as error:
                parse_table(source, MID, 'duas')
            self.assertNotIsInstance(error.exception, PortalErrorPage)

    def test_overflow_never_bypasses_independent_count_width_or_identity(self):
        row = ['']*len(HEADERS['duas'])
        # Una máscara de un dígito permite un fixture pequeño; se exige Count >= 10.
        source = table_html('duas', [row]*10).replace('&quot;nRC_Grid1&quot;: &quot;10&quot;',
                                                   '&quot;nRC_Grid1&quot;: &quot;*&quot;')
        with self.assertRaises(IncompleteTable):
            parse_table(source, MID.replace('20260376', '20260000'), 'duas')
        with self.assertRaises(IncompleteTable):
            parse_table(change_grid_count(source, 11), MID, 'duas')
        short = table_html('duas', [row[:-1]]*10).replace('&quot;nRC_Grid1&quot;: &quot;10&quot;',
                                                       '&quot;nRC_Grid1&quot;: &quot;*&quot;')
        with self.assertRaises(IncompleteTable):
            parse_table(short, MID, 'duas')


class ReconsiderConversionTests(unittest.TestCase):
    def test_restart_reconsiders_conversion_exclusions_preserving_real_portal_exclusion_and_results(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'duas_aereo_2026_09.csv'
            store = ManifestTableStore(path, {'flow': 'duas'})
            conversion = MID.replace('20260376', '00000377')
            actual_portal = MID.replace('20260376', '00000378')
            pending = MID.replace('20260376', '00000379')
            jobs = [(i+19, 'url', {}, mid) for i, mid in enumerate((MID, conversion, actual_portal, pending))]
            store.prepare_selection(jobs)
            store.start_run()
            row = ['00001'] + ['']*(len(HEADERS['duas'])-1) + [MID]
            store.claim(MID)
            store.save(MID, 1, [row], {'pages': 1, 'read': 1, 'kept': 1})
            store.claim(conversion)
            store.exclude(conversion, 2, REASON)  # Simula una exclusión antigua incorrecta.
            store.claim(actual_portal)
            store.exclude(actual_portal, 3, 'TICA devolvió frmAmbiente; excluido de reintentos')
            store.claim(pending)
            store.fail(pending, 4, REASON)
            store.finish_run(4)
            history = store.db.execute('SELECT * FROM attempts').fetchall()
            store.close()
            store = KnowledgeStore.open_existing(path.with_suffix('.sqlite3'))
            store.start_run()
            self.assertEqual([job['state'] for job in store.jobs()], ['Guardado', 'Pendiente', 'Excluido', 'Pendiente'])
            self.assertEqual([job['attempts'] for job in store.jobs()], [1, 1, 1, 1])
            self.assertEqual(store.db.execute('SELECT * FROM attempts').fetchall(), history)
            self.assertEqual(store.db.execute('SELECT previous_reason FROM job_reconsiderations WHERE manifest=?',
                                             (conversion,)).fetchone()[0], REASON)
            store.claim(conversion)
            self.assertEqual(store.job(conversion)['attempts'], 2)
            store.interrupt('Detenido')
            store.export()
            store.close()
            with exclusion_csv_path(path).open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual([r['IDManifiesto'] for r in csv.DictReader(stream)], [actual_portal])
            with path.open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(list(csv.reader(stream))[1][1], '00001')

    def test_retry_reconsideration_is_idempotent_and_only_for_duas(self):
        for flow in ('duas', 'movimientos'):
            with self.subTest(flow=flow), tempfile.TemporaryDirectory() as folder:
                store = ManifestTableStore(Path(folder)/f'{flow}.csv', {'flow': flow})
                store.prepare_selection([(1, 'url', {}, MID)])
                with store.db:
                    store.db.execute("UPDATE jobs SET state='Excluido',error=?", (REASON,))
                store.start_run()
                store.start_run()
                self.assertEqual(store.job(MID)['state'], 'Pendiente' if flow == 'duas' else 'Excluido')
                if flow == 'duas':
                    self.assertEqual(store.db.execute('SELECT COUNT(*) FROM job_reconsiderations').fetchone()[0], 1)
                store.close()
