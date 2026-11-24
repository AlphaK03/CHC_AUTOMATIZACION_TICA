"""Incompatibilidad local: detener antes de consultar, rearmar u omitir días."""
from datetime import date, datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from chc_runtime.daily import DailyCoordinator, ZONE
from chc_runtime.selenium_browser import prepare_daily_browser, validate_daily_browser


UPDATER = 'integrations.duas_source.src.driver_updater.'
ROOT = Path(__file__).resolve().parents[2]
MISMATCH = 'Edge 158.0.4370.33 y su controlador 155.0.4283.62 son incompatibles.'


class DailyBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.driver = self.root / 'msedgedriver.exe'
        self.driver.touch()

    def validate(self, installed, edge='158.0.4370.33'):
        with patch('chc_runtime.selenium_browser.packaged', return_value=False), \
                patch(UPDATER + 'get_edge_version', return_value=edge), \
                patch(UPDATER + 'get_current_driver_version', return_value=installed):
            validate_daily_browser(self.driver)

    def test_requires_same_build_but_accepts_different_revision(self):
        self.validate('158.0.4370.20')
        for installed in ('155.0.4283.62', '158.0.4300.33'):
            with self.subTest(installed=installed), self.assertRaisesRegex(RuntimeError, 'Instalar_Base_Diaria.bat'):
                self.validate(installed)

    def test_unreadable_driver_is_actionable_and_missing_driver_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'No se pudo comprobar'):
            self.validate(None)
        with self.assertRaisesRegex(RuntimeError, 'Instalar_Base_Diaria.bat'):
            validate_daily_browser(self.root / 'missing.exe')

    def test_packaged_browser_does_not_depend_on_system_edge(self):
        with patch('chc_runtime.selenium_browser.packaged', return_value=True), \
                patch(UPDATER + 'get_edge_version', side_effect=AssertionError('No leer Edge')):
            validate_daily_browser(self.driver)

    def test_startup_does_not_download_when_build_already_matches(self):
        with patch('chc_runtime.selenium_browser.packaged', return_value=False), \
                patch(UPDATER + 'get_edge_version', return_value='158.0.4370.33'), \
                patch(UPDATER + 'get_current_driver_version', return_value='158.0.4370.20'), \
                patch(UPDATER + 'get_latest_compatible_version') as latest, \
                patch(UPDATER + 'download_driver') as download:
            result = prepare_daily_browser(self.driver)
        self.assertEqual(result, {'updated': False, 'version': '158.0.4370.20'})
        latest.assert_not_called()
        download.assert_not_called()

    def test_update_is_verified_atomic_and_cleans_staging_even_on_failure_or_cancel(self):
        for mode in ('success', 'network_error', 'wrong_version', 'cancel'):
            with self.subTest(mode=mode):
                self.driver.write_bytes(b'previous')
                cancelled = Event()

                def download(version, destination, progress_callback):
                    self.assertEqual(self.driver.read_bytes(), b'previous')
                    Path(destination).write_bytes(b'new')
                    if mode == 'network_error':
                        raise RuntimeError('Sin conexión')
                    if mode == 'cancel':
                        cancelled.set()

                def version(path):
                    if Path(path) == self.driver:
                        return '155.0.4283.62'
                    return '155.0.4283.62' if mode == 'wrong_version' else '158.0.4370.33'

                with patch('chc_runtime.selenium_browser.packaged', return_value=False), \
                        patch(UPDATER + 'get_edge_version', return_value='158.0.4370.33'), \
                        patch(UPDATER + 'get_current_driver_version', side_effect=version), \
                        patch(UPDATER + 'get_latest_compatible_version', return_value='158.0.4370.33'), \
                        patch(UPDATER + 'download_driver', side_effect=download):
                    if mode == 'success':
                        self.assertTrue(prepare_daily_browser(self.driver, cancelled=cancelled)['updated'])
                    else:
                        with self.assertRaises(RuntimeError):
                            prepare_daily_browser(self.driver, cancelled=cancelled)
                self.assertEqual(self.driver.read_bytes(), b'new' if mode == 'success' else b'previous')
                self.assertFalse(list(self.root.glob('chc-driver-*')))

    def test_updaters_cannot_replace_driver_concurrently(self):
        from chc_runtime.job_store import RunLock
        with RunLock(str(self.driver) + '.actualizacion'), \
                patch(UPDATER + 'get_edge_version') as edge:
            with self.assertRaisesRegex(RuntimeError, 'otra instancia'):
                prepare_daily_browser(self.driver)
            edge.assert_not_called()

    def coordinator(self, module):
        service = SimpleNamespace(root=self.root / module,
            profile={'id': module}, stop_event=Event(),
            machine={'daily_mode': True, 'daily_start_date': '2026-11-06'},
            protocol=SimpleNamespace(emit=Mock()), snapshot=lambda: {},
            local_root=lambda: self.root / 'out')
        return DailyCoordinator(service, now=lambda: datetime(2026, 11, 24, 16, tzinfo=ZONE))

    def test_all_four_bots_reject_before_resetting_manual_range_or_spending_attempts(self):
        for module in ('detalles', 'duas_transito', 'talon', 'xmovimientos'):
            with self.subTest(module=module):
                daily = self.coordinator(module)
                day = date(2026, 11, 6)
                daily.ledger.update(day, state='omitted', retry_cycles=3, error='Fallo previo')
                before = daily.ledger.path.read_bytes()
                config = dict(daily.service.machine)
                with patch('chc_runtime.daily.validate_daily_browser', side_effect=RuntimeError(MISMATCH)), \
                        patch.object(daily, 'reset_manual_range') as reset, \
                        patch.object(daily, 'download') as download:
                    with self.assertRaisesRegex(RuntimeError, 'incompatibles'):
                        daily.run(day, day, manual=True)
                    reset.assert_not_called()
                    download.assert_not_called()
                self.assertEqual(before, daily.ledger.path.read_bytes())
                self.assertEqual(config, daily.service.machine)
                self.assertFalse(daily.active)

    def test_update_during_daily_loop_stops_without_omitting_or_spending_next_day(self):
        daily = self.coordinator('detalles')
        first, second = date(2026, 11, 6), date(2026, 11, 7)
        daily.ledger.update(second, retry_cycles=2)
        calls = []

        def download(day):
            calls.append(day)
            return []

        daily.download = download
        daily.service.execute = Mock()
        daily.append_day = Mock(return_value={})
        daily.confirmed = Mock(return_value=0)
        daily.empty_count = Mock(return_value=0)
        # El primer día termina vacío verificado; Edge cambia antes del segundo.
        with patch('chc_runtime.daily.validate_daily_browser', side_effect=[None, None, RuntimeError(MISMATCH)]):
            with self.assertRaisesRegex(RuntimeError, 'incompatibles'):
                daily.run(first, second, manual=False, bounded=False)
        self.assertEqual(calls, [first])
        self.assertEqual(daily.ledger.get(first)['retry_cycles'], 1)
        self.assertEqual(daily.ledger.get(first)['state'], 'completed')
        self.assertEqual(daily.ledger.get(second)['retry_cycles'], 2)
        self.assertEqual(daily.ledger.get(second)['state'], 'pending')
        self.assertFalse(daily.ledger.get(date(2026, 11, 8)))
        self.assertFalse(daily.active)

    def test_provider_rejects_mismatch_before_planning_ranges_or_starting_browser(self):
        script = '''
import sys
from unittest.mock import patch
from integrations.duas_source import worker
from integrations.duas_source.src import driver_updater
with patch.object(driver_updater, 'get_edge_version', return_value='158.0.4370.33'), \\
     patch.object(driver_updater, 'get_current_driver_version', return_value='155.0.4283.62'), \\
     patch.object(worker, 'run_downloads', side_effect=AssertionError('No consultar TICA')):
    sys.exit(worker.main())
'''
        for selection in ('total', 'transito', 'importacion'):
            with self.subTest(selection=selection):
                database = self.root / (selection + '.sqlite3')
                result = subprocess.run([sys.executable, '-u', '-c', script,
                    '--day', '2026-11-06', '--database', str(database),
                    '--driver', str(self.driver), '--selection', selection],
                    input='', capture_output=True, text=True, encoding='utf-8',
                    cwd=ROOT, timeout=15)
                self.assertEqual(result.returncode, 1, result.stderr)
                event = json.loads(result.stdout)
                self.assertEqual(event['event'], 'result')
                self.assertTrue(event['fatal'])
                self.assertFalse(event['complete'])
                self.assertIn('Instalar_Base_Diaria.bat', event['message'])
                self.assertFalse(database.exists())


if __name__ == '__main__':
    unittest.main()
