"""Un hilo bloqueado libera su reserva y no impide completar ni detener el lote."""
import asyncio
from pathlib import Path
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime.job_store import JobStore
from chc_runtime.playwright_processor import PlaywrightDUAProcessor, close_browser_resource


class BlockedProcessor(PlaywrightDUAProcessor):
    async def _block_static(self, page):
        pass

    async def _extract_record(self, page, row):
        if row['NroDUA'].endswith('000001') and self.block:
            self.started.set()
            await asyncio.Event().wait()
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


if __name__ == '__main__':
    unittest.main()
