import asyncio
import csv
import html
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pandas as pd
from core.engine import BLSProcessor
from core.inputs import batch_scope, input_job, query_dates
from core.store import JobStore
from core.tables import DETAIL_COLUMNS, DETAIL_FIELDS, InvalidResponse, parse_detail, parse_search, table_data
from data_reader import parse_fecha_manifiesto

MID = '4-0-26000125-P010-01/04/26'
BL = '001-000023547860'


def record(sequence=1, bl=None, mid=MID):
    return {'BL original': bl or f'000{sequence}', 'IDManifiesto': mid, 'Secuencia Tica': str(sequence),
            'Fecha Manifiesto': '01/04/2026', 'Mes': '2026-04'}


def frame(count=3):
    return pd.DataFrame([record(index) for index in range(1, count + 1)])


def detail(values=None, count=1, mid=MID, bl=BL):
    row = ['Resources/OPEN.GIF'] * 5 + ['001', '', '191.000', 'PKG', '20.000', '0.000', 'A222',
                                     'Almacén', '013', 'ORD', 'CER', '', '', '', '1']
    state = dict(zip(['CGTPOTRANS', 'CGTPOMIC', 'CGNROMIC', 'RGDEPID', 'CGFCHARR'], mid.split('-')))
    state.update(CGNROCON=bl, CGNROCONDNA='1', nRC_Grid1=str(count), Grid1ContainerData={
        'Count': count, 'Columns': [{} for _ in range(20)], '0': {'Props': [[f + '_0001'] for f in DETAIL_FIELDS]}})
    return '<input name="GXState" value="' + html.escape(json.dumps(state), quote=True) + '">' + \
           '<input name="Grid1ContainerDataV" value="' + html.escape(json.dumps([row] if values is None else values), quote=True) + '">'


def search():
    row = MID.split('-') + ['img', 'img', '1', BL] + [''] * 15
    return {'gxHiddens': {'GXH_vCGNROCON': BL, 'GXH_vVFCH1': '01/04/2026', 'GXH_vVFCHF': '30/04/2026',
                         'Grid2ContainerDataV': json.dumps([row]), 'nRC_Grid2': '1'},
            'gxGrids': [{'GridName': 'Grid2', 'Count': 1, '0': {'Props': [['vVLIN_0001', 'hcglineas.aspx?confirmed']]}}]}


class ProtocolTests(unittest.TestCase):
    def test_no_padding_and_original_zeroes(self):
        self.assertFalse(hasattr(BLSProcessor, '_pad_bl'))
        self.assertEqual(input_job(record(bl=BL), 1)['record']['BL original'], BL)

    def test_input_invalid_and_month_dates(self):
        self.assertEqual(query_dates(record(), {}), ('01/04/2026', '30/04/2026'))
        for key, value in [('Fecha Manifiesto', '02/04/2026'), ('BL original', ''), ('Secuencia Tica', '0')]:
            self.assertTrue(input_job(dict(record(), **{key: value}), 1)['error'])

    def test_mixed_dates(self):
        dates = parse_fecha_manifiesto(pd.Series(['01/04/2026', 'miércoles, 2 de abril de 2025'], index=[9, 12]))
        self.assertEqual(dates.dt.strftime('%d/%m/%Y').tolist(), ['01/04/2026', '02/04/2025'])
        self.assertEqual(dates.index.tolist(), [9, 12])

    def test_batch_signature_tracks_input_but_not_workers(self):
        data = frame()
        signature = batch_scope(data, {'cant_hilos': 1})[0]
        self.assertEqual(signature, batch_scope(data, {'cant_hilos': 20})[0])
        self.assertNotEqual(signature, batch_scope(data.iloc[::-1], {})[0])

    def test_search_confirms_ajax_identity_and_sequence(self):
        chosen, _ = parse_search(search(), record(bl=BL), ('01/04/2026', '30/04/2026'))
        self.assertEqual(chosen['href'], 'hcglineas.aspx?confirmed')
        self.assertIsNone(parse_search(search(), record(sequence=2, bl=BL), ('01/04/2026', '30/04/2026'))[0])
        with self.assertRaises(InvalidResponse):
            parse_search(search(), record(bl='0' + BL), ('01/04/2026', '30/04/2026'))

    def test_hidden_detail_keeps_text(self):
        columns, rows = parse_detail(detail(), record(bl=BL))
        self.assertEqual(columns, DETAIL_COLUMNS)
        self.assertEqual((rows[0][5], rows[0][6], rows[0][12]), ('001', '191.000', '013'))

    def test_invalid_response_never_becomes_empty_success(self):
        for response in [detail(bl='0' + BL), detail(mid=MID.replace('125', '126')), detail(count=2),
                         detail(values=[['one']]), '<html>503</html>']:
            with self.subTest(response=response[:35]), self.assertRaises(InvalidResponse):
                parse_detail(response, record(bl=BL))

    def test_confirmed_empty_is_saved(self):
        self.assertEqual(parse_detail(detail(values=[], count=0), record(bl=BL))[1], [])

    def test_table_preserves_literal_numeric_identifiers(self):
        self.assertEqual(table_data('<table><tr><th>BL</th><th>Aduana</th></tr><tr><td>0001</td><td>013</td></tr></table>')[1], [['0001', '013']])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'bls.sqlite3'
        self.signature, self.scope = batch_scope(frame(), {})
        self.store = JobStore(self.path, self.signature, self.scope)
        self.store.prepare(frame())
        self.store.start_run()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_results_and_export_follow_input_order(self):
        for key, ordinal, data in reversed(self.store.pending()):
            token = self.store.claim(key)
            self.store.save(key, token, ['BL', 'Aduana'], [[data['BL original'], '013']])
        output = self.root / 'data.csv'
        self.assertEqual(self.store.export(output), 3)
        with output.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.reader(stream))[1:], [[f'000{i}', '013'] for i in range(1, 4)])
        self.assertEqual(self.store.summary()['saved'], 3)

    def test_save_rolls_back_on_insert_failure(self):
        key, _, _ = self.store.pending()[0]
        token = self.store.claim(key)
        self.store.db.execute("CREATE TRIGGER reject_result BEFORE INSERT ON results BEGIN SELECT RAISE(ABORT,'disco'); END")
        self.store.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save(key, token, ['BL'], [['0001']])
        self.assertEqual(self.store.summary()['saved'], 0)
        self.assertEqual(self.store.summary()['result_rows'], 0)
        self.assertIsNone(self.store.get_metadata('columns'))

    def test_lock_prevents_second_writer_recovering_active_jobs(self):
        self.store.claim(self.store.pending()[0][0])
        with self.assertRaises(RuntimeError):
            JobStore(self.path, self.signature, self.scope)
        self.assertEqual(self.store.summary()['running'], 1)

    def test_resume_keeps_saved_and_recovers_interrupted(self):
        jobs = self.store.pending()
        token = self.store.claim(jobs[0][0])
        self.store.save(jobs[0][0], token, ['BL'], [['0001']])
        self.store.claim(jobs[1][0])
        self.store.close()
        self.store = JobStore(self.path, self.signature, self.scope)
        self.assertEqual((self.store.summary()['saved'], self.store.summary()['running']), (1, 0))
        self.assertEqual(len(self.store.pending()), 2)

    def test_stale_token_cannot_commit(self):
        key, _, _ = self.store.pending()[0]
        token = self.store.claim(key)
        self.store.fail(key, token, 'error')
        new_token = self.store.claim(key)
        with self.assertRaises(RuntimeError):
            self.store.save(key, token, ['BL'], [['wrong']])
        self.store.save(key, new_token, ['BL'], [['correct']])

    def test_close_releases_database_with_unconsumed_queue_still_referenced(self):
        count, queue = self.store.pending_queue()
        self.assertEqual(count, 3)
        next(queue)
        self.store.close()
        # Mantener la cola viva reproduce la referencia que dejan tareas canceladas.
        # El commit debe funcionar sin esperar al recolector de basura.
        with sqlite3.connect(self.path, timeout=.1) as probe:
            probe.execute("UPDATE metadata SET value=value WHERE key='signature'")
        probe.close()
        self.store = JobStore(self.path, self.signature, self.scope)
        self.assertEqual(self.store.summary()['pending'], 3)
        queue.close()

    def test_readonly_export_does_not_recover_active_jobs_or_keep_locks(self):
        from core.store import export_saved
        jobs = self.store.pending()
        self.store.save(jobs[0][0], self.store.claim(jobs[0][0]), ['BL', 'Aduana'], [['0001', '013']])
        token = self.store.claim(jobs[1][0])
        output = self.root / 'snapshot.csv'
        self.assertEqual(export_saved(self.path, output), 1)
        self.assertEqual(self.store.summary()['running'], 1)
        # Un exportador que deje abierta su transacción de lectura bloquea este commit.
        self.store.save(jobs[1][0], token, ['BL', 'Aduana'], [['0002', '013']])
        with output.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.reader(stream)), [['BL', 'Aduana'], ['0001', '013']])

    def test_blocked_export_preserves_output_and_sqlite(self):
        key, _, _ = self.store.pending()[0]
        self.store.save(key, self.store.claim(key), ['BL'], [['0001']])
        output = self.root / 'data.csv'
        output.write_text('previous')
        with patch('core.store.os.replace', side_effect=PermissionError('Excel')):
            with self.assertRaises(PermissionError):
                self.store.export(output)
        self.assertEqual(output.read_text(), 'previous')
        self.assertEqual(self.store.summary()['saved'], 1)

    def test_duplicate_inputs_preserve_references_but_query_once(self):
        self.store.close()
        data = pd.concat([frame(1), frame(1)], ignore_index=True)
        signature, scope = batch_scope(data, {})
        self.store = JobStore(self.root / 'duplicates.sqlite3', signature, scope)
        self.store.prepare(data)
        self.store.start_run()
        self.assertEqual(self.store.summary()['total'], 1)
        key, _, _ = self.store.pending()[0]
        self.store.save(key, self.store.claim(key), ['BL'], [['0001']])
        self.assertEqual(self.store.export(self.root / 'dups.csv'), 2)

    def test_review_exports_distinguish_confirmed_empty_failed_and_unattempted(self):
        jobs = self.store.pending()
        self.store.save(jobs[0][0], self.store.claim(jobs[0][0]), ['BL'], [])
        self.store.fail(jobs[1][0], self.store.claim(jobs[1][0]), 'Sin coincidencia', 'no_match')
        empty, pending = self.root / 'empty.csv', self.root / 'pending.csv'
        self.assertEqual(self.store.export_review(empty, empty=True), 1)
        self.assertEqual(self.store.export_review(pending), 2)
        with empty.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['BL original'], '0001')
        self.assertEqual(rows[0]['Estado'], 'Guardado')
        self.assertEqual(rows[0]['Lineas guardadas'], '0')
        with pending.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row['BL original'] for row in rows], ['0002', '0003'])
        self.assertEqual([row['Intentos'] for row in rows], ['1', '0'])
        self.assertEqual(rows[0]['Codigo error'], 'no_match')
        self.assertEqual(self.store.summary()['empty_saved'], 1)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_outage_resume_portal_failure_and_stop_use_real_sqlite(self):
        from core.internet import InternetGuard
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        for mode in ('resume', 'portal_failure', 'stop'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                stop, paused = Event(), asyncio.Event()
                config = {'output_base_path': folder, 'cant_hilos': 3, 'max_retries': 1}
                def event(data):
                    if data.get('phase') == 'network_wait':
                        paused.set()
                config['event_callback'] = event
                calls = []
                class Session:
                    async def query(self, data):
                        bl = data['BL original']
                        first = bl not in calls
                        calls.append(bl)
                        await asyncio.sleep(.01)
                        if first or mode != 'resume':
                            raise PlaywrightTimeout('TICA timeout')
                        return {'status': 'success', 'columns': ['BL'], 'rows': [[bl]]}
                    async def close(self):
                        pass
                manager = MagicMock()
                manager.__aenter__ = AsyncMock(return_value=AsyncMock())
                manager.__aexit__ = AsyncMock(return_value=False)
                probe = AsyncMock(return_value='offline' if mode == 'stop' else 'online')
                if mode == 'resume':
                    probe.side_effect = ['offline', 'offline', 'online']
                def guard_factory(*args, **kwargs):
                    return InternetGuard(*args, **kwargs, interval=.01)
                with patch('playwright.async_api.async_playwright', return_value=manager), \
                     patch('core.engine.launch_chromium', new_callable=AsyncMock), \
                     patch('core.engine.TicaSession', side_effect=lambda *args: Session()), \
                     patch('core.engine.probe_internet', probe), \
                     patch('core.engine.InternetGuard', side_effect=guard_factory):
                    processor = BLSProcessor(config, stop)
                    task = asyncio.create_task(processor.run_async(frame()))
                    if mode == 'stop':
                        await asyncio.wait_for(paused.wait(), 2)
                        stop.set()
                    result = await asyncio.wait_for(task, 3)
                self.assertEqual(result['attempts'], 3)
                self.assertEqual(result['running'], 0)
                self.assertEqual(result['saved'], 3 if mode == 'resume' else 0)
                self.assertEqual(result['pending'], 0 if mode == 'resume' else 3)
                self.assertEqual(result['internet_pauses'] if 'internet_pauses' in result else processor.stats['internet_pauses'],
                                 0 if mode == 'portal_failure' else 1)
                self.assertEqual(result['pending_exported'], 0 if mode == 'resume' else 3)
                if mode == 'resume':
                    self.assertEqual(calls.count('0001'), 2)

    async def test_browser_setup_failure_or_stop_preserves_saved_results_and_attempts(self):
        from core.browser_runtime import BrowserSetupCancelled
        for mode in ('failure', 'stop'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                config = {'output_base_path': folder, 'cant_hilos': 2, 'max_retries': 1}
                stop = Event()
                class Session:
                    async def query(self, data):
                        if data['Secuencia Tica'] == '1':
                            return {'status': 'success', 'columns': ['BL'], 'rows': [[data['BL original']]]}
                        return {'status': 'no_match', 'error': 'Pendiente para otra consulta'}
                    async def close(self):
                        pass
                first = await BLSProcessor(config, stop).run_async(frame(), session_factory=lambda worker: Session())
                manager = MagicMock()
                manager.__aenter__ = AsyncMock(return_value=AsyncMock())
                manager.__aexit__ = AsyncMock(return_value=False)
                async def setup(*args, **kwargs):
                    if mode == 'stop':
                        stop.set()
                        raise BrowserSetupCancelled()
                    raise RuntimeError('No se pudo descargar Chromium')
                with patch('playwright.async_api.async_playwright', return_value=manager), \
                     patch('core.engine.launch_chromium', side_effect=setup):
                    processor = BLSProcessor(config, stop)
                    if mode == 'failure':
                        with self.assertRaisesRegex(RuntimeError, 'descargar Chromium'):
                            await processor.run_async(frame())
                    else:
                        result = await processor.run_async(frame())
                        self.assertEqual((result['saved'], result['pending']), (1, 2))
                    self.assertEqual(processor.stats['attempted_this_run'], 0)
                probe = sqlite3.connect(first['database'])
                try:
                    self.assertEqual(dict(probe.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state')),
                                     {'Guardado': 1, 'Pendiente': 2})
                    self.assertEqual(probe.execute('SELECT SUM(attempts) FROM jobs').fetchone()[0], 3)
                    self.assertEqual(probe.execute('SELECT COUNT(*) FROM results').fetchone()[0], 1)
                finally:
                    probe.close()

    async def test_357_jobs_then_retry_only_27_then_zero_network(self):
        with tempfile.TemporaryDirectory() as folder:
            config = {'output_base_path': folder, 'cant_hilos': 20, 'max_retries': 1}
            calls, failures = [], set(range(1, 28))
            class Session:
                async def query(self, data):
                    sequence = int(data['Secuencia Tica'])
                    calls.append(data['BL original'])
                    await asyncio.sleep(.001)
                    if sequence in failures:
                        raise RuntimeError('conexión simulada')
                    return {'status': 'success', 'columns': ['BL', 'Aduana'], 'rows': [[data['BL original'], '013']]}
                async def close(self):
                    pass
            factory = lambda worker: Session()
            first = await BLSProcessor(config, Event()).run_async(frame(357), session_factory=factory)
            self.assertEqual((first['saved'], first['pending'], first['running']), (330, 27, 0))
            self.assertEqual(len(calls), 357)
            calls.clear()
            failures.clear()
            second = await BLSProcessor(config, Event()).run_async(frame(357), session_factory=factory)
            self.assertEqual((second['saved'], second['pending'], second['running']), (357, 0, 0))
            self.assertEqual(len(calls), 27)
            calls.clear()
            third = await BLSProcessor(config, Event()).run_async(frame(357), session_factory=factory)
            self.assertEqual(len(calls), 0)
            self.assertEqual(third['exported'], 357)

    async def test_retry_keeps_same_bl_and_does_not_repeat_no_match_in_next_round(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            class Session:
                async def query(self, data):
                    calls.append(data['BL original'])
                    if len(calls) == 1:
                        raise RuntimeError('red')
                    return {'status': 'no_match', 'error': 'BL ausente'}
                async def close(self):
                    pass
            result = await BLSProcessor({'output_base_path': folder, 'cant_hilos': 1, 'max_retries': 3}, Event()).run_async(
                pd.DataFrame([record(bl=BL)]), session_factory=lambda worker: Session())
            self.assertEqual(calls, [BL, BL])
            self.assertEqual((result['saved'], result['pending']), (0, 1))

    async def test_stop_returns_inflight_jobs_to_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = Event()
            class Session:
                async def query(self, data):
                    if data['Secuencia Tica'] != '1':
                        await asyncio.sleep(100)
                    return {'status': 'success', 'columns': ['BL'], 'rows': [[data['BL original']]]}
                async def close(self):
                    pass
            processor = BLSProcessor({'output_base_path': folder, 'cant_hilos': 2, 'max_retries': 1}, stop)
            task = asyncio.create_task(processor.run_async(frame(50), session_factory=lambda worker: Session()))
            await asyncio.sleep(.2)
            stop.set()
            result = await asyncio.wait_for(task, 3)
            self.assertEqual((result['saved'], result['pending'], result['running']), (1, 49, 0))
            self.assertEqual(result['exported'], 1)
            stop.clear()
            class CompletedSession:
                async def query(self, data):
                    return {'status': 'success', 'columns': ['BL'], 'rows': [[data['BL original']]]}
                async def close(self):
                    pass
            resumed = await processor.run_async(frame(50), session_factory=lambda worker: CompletedSession())
            self.assertEqual((resumed['saved'], resumed['pending']), (50, 0))


if __name__ == '__main__':
    unittest.main()
