import asyncio
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core.internet import ConnectionWaitStopped, InternetGuard, probe_internet
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout


class InternetTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_workers_share_one_pause_and_resume(self):
        probe = AsyncMock(side_effect=['offline', 'offline', 'online'])
        stages = []
        guard = InternetGuard(probe, Event(), lambda phase, message: stages.append(phase), interval=.005)
        results = await asyncio.gather(*[guard.recover_if_offline(PlaywrightTimeout('TICA timeout')) for _ in range(10)])
        self.assertEqual(results, [True] * 10)
        self.assertEqual(guard.pauses, 1)
        self.assertEqual(guard.checks, 3)
        self.assertEqual(stages, ['network_wait', 'network_resumed'])

    async def test_portal_failure_with_internet_online_keeps_finite_retries(self):
        probe = AsyncMock(return_value='online')
        guard = InternetGuard(probe, Event(), interval=.001)
        self.assertFalse(await guard.recover_if_offline(PlaywrightTimeout('TICA timeout')))
        self.assertEqual(guard.pauses, 0)

    async def test_unknown_connectivity_does_not_authorize_infinite_wait(self):
        guard = InternetGuard(AsyncMock(return_value='unknown'), Event(), interval=.001)
        self.assertFalse(await guard.recover_if_offline(PlaywrightTimeout('TICA timeout')))
        self.assertTrue(guard.online.is_set())

    async def test_invalid_table_does_not_probe_internet(self):
        probe = AsyncMock()
        guard = InternetGuard(probe, Event())
        self.assertFalse(await guard.recover_if_offline(ValueError('Tabla incompatible')))
        probe.assert_not_awaited()

    async def test_offline_wait_continues_until_stop(self):
        stop = Event()
        guard = InternetGuard(AsyncMock(return_value='offline'), stop, interval=.005)
        task = asyncio.create_task(guard.recover_if_offline(PlaywrightTimeout('timeout')))
        try:
            while guard.checks < 5:
                await asyncio.sleep(.01)
            self.assertFalse(task.done())
            stop.set()
            with self.assertRaises(ConnectionWaitStopped):
                await asyncio.wait_for(task, 1)
        finally:
            stop.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_independent_probe_accepts_http_errors_as_online_and_ssl_as_unknown(self):
        pw = AsyncMock()
        context = pw.request.new_context.return_value
        response = AsyncMock()
        response.status = 503
        context.get.side_effect = [response, PlaywrightTimeout('timeout')]
        self.assertEqual(await probe_internet(pw), 'online')
        response.dispose.assert_awaited_once()
        context.dispose.assert_awaited_once()
        context.get.side_effect = [PlaywrightError('certificate verify failed'), PlaywrightTimeout('timeout')]
        self.assertEqual(await probe_internet(pw), 'unknown')


if __name__ == '__main__':
    unittest.main()
