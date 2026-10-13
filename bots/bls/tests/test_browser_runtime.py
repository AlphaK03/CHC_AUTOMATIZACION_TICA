import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core.browser_runtime import (BrowserSetupCancelled, configure_browser_cache,
                                  install_chromium, launch_chromium)
from playwright.async_api import Error as PlaywrightError


class LaunchTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_browser_does_not_download(self):
        pw = AsyncMock()
        with patch('core.browser_runtime.install_chromium', new_callable=AsyncMock) as install:
            browser = await launch_chromium(pw, False, Event())
        self.assertIs(browser, pw.chromium.launch.return_value)
        pw.chromium.launch.assert_awaited_once_with(headless=False)
        install.assert_not_awaited()

    async def test_missing_browser_installs_then_verifies_and_resumes(self):
        pw = AsyncMock()
        browser = AsyncMock()
        pw.chromium.launch.side_effect = [PlaywrightError("Executable doesn't exist at C:/missing/browser.exe"), browser]
        events = []
        with patch('core.browser_runtime.install_chromium', new_callable=AsyncMock) as install:
            result = await launch_chromium(pw, True, Event(), lambda stage, message: events.append(stage))
        self.assertIs(result, browser)
        install.assert_awaited_once()
        self.assertEqual(pw.chromium.launch.await_count, 2)
        self.assertEqual(events, ['ready'])

    async def test_other_launch_errors_do_not_trigger_a_download(self):
        pw = AsyncMock()
        pw.chromium.launch.side_effect = PlaywrightError('Access is denied')
        with patch('core.browser_runtime.install_chromium', new_callable=AsyncMock) as install:
            with self.assertRaisesRegex(PlaywrightError, 'Access is denied'):
                await launch_chromium(pw, True, Event())
        install.assert_not_awaited()

    async def test_failed_install_does_not_attempt_another_launch(self):
        pw = AsyncMock()
        pw.chromium.launch.side_effect = PlaywrightError("Executable doesn't exist at C:/missing/browser.exe")
        with patch('core.browser_runtime.install_chromium', new_callable=AsyncMock, side_effect=RuntimeError('Sin Internet')):
            with self.assertRaisesRegex(RuntimeError, 'Sin Internet'):
                await launch_chromium(pw, True, Event())
        self.assertEqual(pw.chromium.launch.await_count, 1)

    async def test_stop_before_launch_does_not_spawn(self):
        pw, stop = AsyncMock(), Event()
        stop.set()
        with self.assertRaises(BrowserSetupCancelled):
            await launch_chromium(pw, True, stop)
        pw.chromium.launch.assert_not_awaited()


class InstallerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.audit = self.root / 'audit.json'
        self.cli = self.root / 'cli.py'
        self.cli.write_text('''import json, os, sys, time
from pathlib import Path
Path(os.environ['BLS_TEST_AUDIT']).write_text(json.dumps({
    'args': sys.argv[1:], 'cache': os.environ['PLAYWRIGHT_BROWSERS_PATH'],
    'skip_gc': os.environ['PLAYWRIGHT_SKIP_BROWSER_GC']}))
print('Downloading Chrome for Testing', flush=True)
mode = os.environ['BLS_TEST_INSTALL_MODE']
if mode == 'slow':
    time.sleep(30)
if mode == 'error':
    print('Simulated network failure', flush=True)
    sys.exit(1)
print('Chromium downloaded', flush=True)
''', encoding='utf-8')
        self.driver_patch = patch('core.browser_runtime.compute_driver_executable', return_value=(sys.executable, str(self.cli)))
        self.env_patch = patch.dict(os.environ, {'BLS_TEST_AUDIT': str(self.audit),
            'BLS_TEST_INSTALL_MODE': 'ok', 'PLAYWRIGHT_BROWSERS_PATH': str(self.root / 'cache')})
        self.driver_patch.start()
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.driver_patch.stop()
        self.temp.cleanup()

    async def test_installer_uses_bundled_cli_exact_cache_and_no_browser_gc(self):
        events = []
        await install_chromium(Event(), lambda stage, message: events.append(stage))
        audit = json.loads(self.audit.read_text())
        self.assertEqual(audit['args'], ['install', 'chromium', '--no-progress'])
        self.assertEqual(audit['cache'], str(self.root / 'cache'))
        self.assertEqual(audit['skip_gc'], '1')
        self.assertEqual(events[0], 'installing')
        self.assertEqual(events[-1], 'verifying')

    async def test_failed_download_reports_retry_in_the_app(self):
        os.environ['BLS_TEST_INSTALL_MODE'] = 'error'
        with self.assertRaisesRegex(RuntimeError, 'pulse Iniciar'):
            await install_chromium(Event())

    async def test_stop_terminates_the_owned_installer(self):
        os.environ['BLS_TEST_INSTALL_MODE'] = 'slow'
        stop = Event()
        task = asyncio.create_task(install_chromium(stop))
        try:
            for _ in range(200):
                if self.audit.exists():
                    break
                await asyncio.sleep(.01)
            self.assertTrue(self.audit.exists())
            stop.set()
            with self.assertRaises(BrowserSetupCancelled):
                await asyncio.wait_for(task, 5)
        finally:
            stop.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_timeout_terminates_installer_and_allows_retry(self):
        os.environ['BLS_TEST_INSTALL_MODE'] = 'slow'
        with self.assertRaisesRegex(RuntimeError, 'tiempo permitido'):
            await asyncio.wait_for(install_chromium(Event(), timeout=.25), 5)
        os.environ['BLS_TEST_INSTALL_MODE'] = 'ok'
        await install_chromium(Event())

    def test_frozen_cache_is_outside_the_executable_extraction_folder(self):
        with patch.object(sys, 'frozen', True, create=True), patch.dict(os.environ, {'LOCALAPPDATA': str(self.root)}):
            os.environ.pop('PLAYWRIGHT_BROWSERS_PATH', None)
            configure_browser_cache()
            self.assertEqual(os.environ['PLAYWRIGHT_BROWSERS_PATH'], str(self.root / 'ms-playwright'))


if __name__ == '__main__':
    unittest.main()
