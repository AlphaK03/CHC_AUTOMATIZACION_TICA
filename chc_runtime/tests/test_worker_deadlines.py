"""Un hilo bloqueado libera su reserva y no impide completar ni detener el lote."""
import asyncio
from pathlib import Path
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime.job_store import JobStore
from chc_runtime.playwright_processor import PlaywrightDUAProcessor, close_browser_resource


class BlockedProcessor(PlaywrightDUAProcessor):
    async def _block_static(self, page):
        pass

    async def _extract_record(self, page, row):
        if row['NroDUA'].endswith('000001') and self.block:
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                if not getattr(self, 'ignore_cancellation', False):
                    raise
                self.cancel_received.set()
                await self.release.wait()
        return {'numero_del_dua': row['NroDUA']}


class DeadlineTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.folder.name)/'cola.sqlite3')
        self.store.import_values(['001-2026-000001', '001-2026-000002', '001-2026-000003'])
        self.store.begin_run()
        self.processor = BlockedProcessor({'timeout': 1, 'cant_hilos': 2}, {},
                                          SimpleNamespace(fields=['numero_del_dua']), {}, Event())
        self.processor.block = True
        self.processor.started = asyncio.Event()
        self.processor.cancel_received = asyncio.Event()
        self.processor.release = asyncio.Event()
        self.browser = SimpleNamespace(new_context=AsyncMock(side_effect=lambda:
            SimpleNamespace(new_page=AsyncMock(return_value=Mock()), close=AsyncMock())))

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    async def test_blocked_dua_times_out_others_finish_and_retry_can_run(self):
        await asyncio.wait_for(self.processor._run_round(self.store, self.browser, 1, lambda _: None), 7)
        summary = self.store.summary()
        self.assertEqual((summary['running'], summary['succeeded'], summary['retry']), (0, 2, 1))
        self.assertEqual(self.store.db.execute("SELECT error_kind FROM jobs WHERE dua='001-2026-000001'").fetchone()[0], 'TimeoutError')
        self.processor.block = False
        await self.processor._run_round(self.store, self.browser, 2, lambda _: None)
        self.assertEqual(self.store.summary()['succeeded'], 3)

    async def test_stop_releases_active_claim_even_when_dua_never_returns(self):
        task = asyncio.create_task(self.processor._run_round(self.store, self.browser, 1, lambda _: None))
        await asyncio.wait_for(self.processor.started.wait(), 1)
        self.processor.stop_event.set()
        await asyncio.wait_for(task, 1)
        self.assertEqual(self.store.summary()['running'], 0)
        job = self.store.db.execute("SELECT status FROM jobs WHERE dua='001-2026-000001'").fetchone()
        self.assertEqual(job[0], 'pending')

    async def test_browser_close_has_its_own_deadline(self):
        async def never_closes():
            await asyncio.Event().wait()
        await asyncio.wait_for(close_browser_resource(never_closes, timeout=.02), .5)

    async def test_cancel_resistant_attempt_cannot_block_retry_or_save_late(self):
        self.processor.ignore_cancellation = True
        await asyncio.wait_for(self.processor._run_round(self.store, self.browser, 1, lambda _: None), 7)
        self.assertTrue(self.processor.cancel_received.is_set())
        summary = self.store.summary()
        self.assertEqual((summary['running'], summary['succeeded'], summary['retry']), (0, 2, 1))
        # La tarea vieja devuelve un resultado tarde: no puede marcar éxito.
        self.processor.release.set()
        await asyncio.sleep(.02)
        self.assertEqual(self.store.summary()['succeeded'], 2)
        self.processor.block = False
        await self.processor._run_round(self.store, self.browser, 2, lambda _: None)
        self.assertEqual(self.store.summary()['succeeded'], 3)
        attempts = [tuple(row) for row in self.store.db.execute('SELECT dua,attempts FROM jobs ORDER BY dua')]
        self.assertEqual([value for _, value in attempts], [2, 1, 1])

    async def test_close_ignoring_cancellation_does_not_block_supervisor(self):
        release = asyncio.Event()
        async def stubborn_close():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await release.wait()
        try:
            self.assertFalse(await asyncio.wait_for(close_browser_resource(stubborn_close, timeout=.02), .5))
        finally:
            release.set()
            await asyncio.sleep(.02)

    async def test_retry_round_starts_all_six_configured_workers(self):
        self.store.import_values(['001-2026-000004', '001-2026-000005', '001-2026-000006'], append=True)
        for _ in range(6):
            self.store.retry(self.store.claim(1), 'Primer intento fallido', 'TimeoutError')
        started = set()
        release = asyncio.Event()
        async def retry(page, row):
            started.add(row['NroDUA'])
            await release.wait()
            return {'numero_del_dua': row['NroDUA']}
        self.processor._extract_record = retry
        self.processor.machine['cant_hilos'] = 6
        task = asyncio.create_task(self.processor._run_round(self.store, self.browser, 2, lambda _: None))
        async def all_started():
            while len(started) != 6:
                await asyncio.sleep(.005)
        try:
            await asyncio.wait_for(all_started(), 1)
        finally:
            release.set()
            await asyncio.wait_for(task, 2)
        self.assertEqual(self.store.summary()['succeeded'], 6)

    async def test_run_finishes_even_when_abandoned_task_never_accepts_cancel(self):
        async def extract(page, row):
            if row['NroDUA'].endswith('000001'):
                while True:
                    try:
                        await asyncio.sleep(60)
                    except asyncio.CancelledError:
                        continue
            return {'numero_del_dua': row['NroDUA']}
        self.processor._extract_record = extract
        self.processor.machine['max_retries'] = 1
        root = Path(self.folder.name)
        self.processor.output_paths = {key: root/name for key, name in
            [('output_csv', 'resultado.csv'), ('processed_log', 'procesados.txt'),
             ('failed_duas', 'pendientes.txt'), ('pending_json', 'pendientes.json')]}
        driver = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=self.browser)),
                                 stop=AsyncMock())
        self.browser.close = AsyncMock()
        manager = SimpleNamespace(start=AsyncMock(return_value=driver))
        with patch('chc_runtime.playwright_processor.async_playwright', return_value=manager):
            await asyncio.wait_for(asyncio.to_thread(self.processor.run, self.store, lambda _: None), 15)
        summary = self.store.summary()
        self.assertEqual((summary['running'], summary['succeeded'], summary['retry']), (0, 2, 1))
        self.assertTrue(self.processor.output_paths['output_csv'].is_file())


if __name__ == '__main__':
    unittest.main()
