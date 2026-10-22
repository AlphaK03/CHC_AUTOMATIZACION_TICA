"""Evidencia pequeña, decisiones equivalentes y conversión sin tocar resultados."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest

from chc_runtime.import_bots import ImportRowsProcessor, MovementsJobStore
from chc_runtime.activity import ActivityReporter
from chc_runtime.job_store import RunLock, JobStore
from chc_runtime.movement_empty import verified_empty_html
from chc_runtime.movement_evidence import MAX_REPORT_BYTES, read_summary, summarize_html
from chc_runtime.tests.test_movement_empty import DUA, OTHER, html
from tools.compact_movement_evidence import compact


def heavy_html(source=None):
    return (source if source is not None else html()) + '<input name="GXState" value="' + 'x' * 2000000 + '">'


class MovementEvidenceTests(unittest.TestCase):
    def test_compact_report_preserves_every_empty_rejection_and_is_bounded(self):
        cases = [html(), html(OTHER), html() + '<div id="ERROR">CAPTCHA inválido</div>',
                 html() + '<p class="gx-error-message">Error de red</p>',
                 html() + '<button name="SIGUIENTE">Más</button>',
                 html() + '<button name="SIGUIENTE" disabled>Más</button>',
                 html().replace('<th>Campo</th>', ''),
                 html().replace('</table>', '<tr><td>Incompleta</td></tr></table>'),
                 '<html>Timeout, sin tabla</html>']
        for index, source in enumerate(cases):
            with self.subTest(index=index):
                raw = heavy_html(source)
                report = summarize_html(raw, DUA)
                self.assertEqual(verified_empty_html(raw, DUA), verified_empty_html(report, DUA))
                self.assertFalse(verified_empty_html(report, OTHER))
                data = read_summary(report)
                self.assertEqual(data['source_sha256'], hashlib.sha256(raw.encode()).hexdigest())
                self.assertNotIn('GXState', report)
                self.assertLess(len(report.encode()), 5000)
                self.assertLess(len(report.encode()), MAX_REPORT_BYTES)

    def test_samples_are_limited_and_portal_markup_is_escaped(self):
        value = '&lt;img src=x onerror=alert(1)&gt;' + 'y' * 10000
        rows = ''.join('<tr>' + f'<td>{value}</td>' * 8 + '</tr>' for _ in range(6))
        raw = html().replace('</table>', rows + '</table>') + '<div id="ERROR">' + value + '</div>'
        report = summarize_html(raw, DUA, {'requested': DUA,
                                         'fields': {'vVCODI_ADUA': '001', '_cfield': 'SECRET'},
                                         'captcha_src': 'SECRET'})
        data = read_summary(report)
        self.assertEqual(data['table']['data_rows'], 6)
        self.assertEqual(len(data['table']['sample_rows']), 3)
        self.assertEqual(len(data['table']['sample_rows'][0]), 6)
        self.assertNotIn('SECRET', report)
        self.assertNotIn('<img', report)
        self.assertLess(len(report.encode()), MAX_REPORT_BYTES)
        # Las comillas se expanden seis veces al escapar HTML: tampoco exceder el límite.
        worst = raw.replace(value, '&quot;' * 10000)
        worst += ('<p class="gx-error-message">' + '&quot;' * 10000 + '</p>') * 6
        self.assertLess(len(summarize_html(worst, DUA).encode()), MAX_REPORT_BYTES)

    def test_corrupt_unknown_and_inconsistent_summaries_never_confirm_empty(self):
        data = read_summary(summarize_html(html(), DUA))
        for change in ({'format': 'unknown'}, {'version': 999},
                       {'table': {**data['table'], 'data_rows': 1}},
                       {'table': {**data['table'], 'total_rows': True}},
                       {'observed_dua': OTHER}, {'source_sha256': 'invalid'}):
            broken = deepcopy(data)
            broken.update(change)
            # Construir un informe deliberadamente inválido sin el validador de escritura.
            report = '<pre id="chc-movement-evidence">' + json.dumps(broken) + '</pre>'
            self.assertFalse(verified_empty_html(report, DUA))
        self.assertFalse(verified_empty_html('<pre id="chc-movement-evidence">broken</pre>', DUA))

    def test_live_saving_uses_small_report_only_for_movements(self):
        raw = heavy_html()
        class Page:
            url = 'http://localhost/test?session=SECRET'
            _dua_form_snapshot = {'requested': DUA, 'fields': {'vVCODI_ADUA': '001', '_cfield': 'SECRET'}}
            async def content(self):
                return raw
        for module in ('xmovimientos', 'talon'):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as folder:
                flow = SimpleNamespace(module_id=module, fields=[])
                processor = ImportRowsProcessor({}, {'diagnostics': folder}, flow, {}, Event())
                path = Path(asyncio.run(processor._save_evidence(Page(), DUA)))
                saved = path.read_text(encoding='utf-8')
                if module == 'xmovimientos':
                    self.assertTrue(verified_empty_html(saved, DUA))
                    self.assertLess(path.stat().st_size, 5000)
                    self.assertNotIn('SECRET', saved)
                    self.assertNotIn('SECRET', path.with_suffix('.json').read_text())
                else:
                    self.assertEqual(saved, raw)
                if module == 'xmovimientos':
                    # Una página que cambió después no debe sustituir la respuesta validada.
                    reporter = ActivityReporter(lambda *a, **kw: None)
                    with reporter.session('Consulta observada'):
                        path = Path(asyncio.run(processor._save_evidence(Page(), DUA, source_html=html(OTHER))))
                    self.assertEqual(read_summary(path.read_text(encoding='utf-8'))['observed_dua'], OTHER)
                    self.assertFalse(verified_empty_html(path.read_text(encoding='utf-8'), DUA))

    def test_legacy_classification_still_accepts_compacted_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = root / (DUA + '.html')
            evidence.write_text(summarize_html(heavy_html(), DUA), encoding='utf-8')
            path = root / 'queue.sqlite3'
            store = JobStore(path)
            store.import_values([DUA]); store.begin_run()
            store.retry(store.claim(1), 'Sin movimientos', 'NoMovimientosError', str(evidence))
            attempts = [tuple(row) for row in store.db.execute('SELECT * FROM attempts')]
            store.close()
            store = MovementsJobStore(path)
            try:
                self.assertEqual(store.summary()['empty'], 1)
                self.assertEqual([tuple(row) for row in store.db.execute('SELECT * FROM attempts')], attempts)
                self.assertEqual(store.db.execute('SELECT evidence FROM jobs').fetchone()[0], str(evidence))
            finally:
                store.close()


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'xmovimientos'
        self.diag = self.root / 'data/exports/month/diagnosticos'
        self.diag.mkdir(parents=True)
        self.path = self.diag / (DUA + '.html')
        self.path.write_text(heavy_html(), encoding='utf-8')
        self.sidecar = self.path.with_suffix('.json')
        self.sidecar.write_text(json.dumps({'requested': DUA, 'captcha_src': 'x' * 10000,
                                            'fields': {'vVCODI_ADUA': '001'}}), encoding='utf-8')
        self.queue = self.root / 'data/queues/month.sqlite3'
        self.queue.parent.mkdir(parents=True)
        self.queue.write_bytes(b'unchanged SQLite sentinel')
        self.csv = self.diag.parent / 'resultados.csv'
        self.csv.write_bytes(b'0001,000001,1203.5\r\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_is_read_only_apply_preserves_paths_dates_and_results_and_is_idempotent(self):
        before = {p: p.read_bytes() for p in (self.path, self.sidecar, self.queue, self.csv)}
        old_date = self.path.stat().st_mtime_ns
        preview = compact(self.root)
        self.assertEqual(preview['convertible'], 1)
        self.assertGreater(preview['saved_bytes'], 1900000)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        applied = compact(self.root, apply=True, confirmation='BORRAR')
        self.assertEqual(applied['errors'], 0)
        self.assertEqual(applied['saved_bytes'], preview['saved_bytes'])
        self.assertEqual(self.path.stat().st_mtime_ns, old_date)
        self.assertTrue(verified_empty_html(self.path.read_text(encoding='utf-8'), DUA))
        self.assertEqual(read_summary(self.path.read_text(encoding='utf-8'))['timestamp_origin'], 'file_mtime')
        for path in (self.queue, self.csv):
            self.assertEqual(path.read_bytes(), before[path])
        self.assertEqual(compact(self.root, apply=True, confirmation='BORRAR')['unchanged'], 1)
        entries = [json.loads(line) for line in Path(applied['report']).read_text(encoding='utf-8').splitlines()]
        self.assertEqual([r.get('status') for r in entries if 'status' in r], ['prepared', 'converted'])

    def test_confirmation_and_busy_engine_block_changes(self):
        before = self.path.read_bytes()
        for confirmation in ('', 'borrar', 'BORRAR '):
            with self.assertRaises(ValueError):
                compact(self.root, apply=True, confirmation=confirmation)
        with RunLock(self.queue):
            with self.assertRaises(RuntimeError):
                compact(self.root, apply=True, confirmation='BORRAR')
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(ValueError):
            compact(self.root.parent, apply=True, confirmation='BORRAR')

    def test_invalid_and_changed_files_are_preserved(self):
        self.path.write_text('<pre id="chc-movement-evidence">broken</pre>', encoding='utf-8')
        before = self.path.read_bytes()
        result = compact(self.root, apply=True, confirmation='BORRAR')
        self.assertEqual(result['errors'], 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.path.write_text(heavy_html(), encoding='utf-8')
        from tools.compact_movement_evidence import convert_file
        def concurrent_write(_):
            self.path.write_text('new response', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            convert_file(self.path, apply=True, journal=concurrent_write)
        self.assertEqual(self.path.read_text(), 'new response')


if __name__ == '__main__':
    unittest.main()
