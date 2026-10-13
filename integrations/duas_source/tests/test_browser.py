"""Selenium real sobre file:// local. Nunca visita TICA. Driver opcional por entorno."""
import os
from pathlib import Path
import sys
from threading import Event
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tica_dua_bot import TICADUAExtractor, Cancelled


@unittest.skipUnless(os.environ.get('DUA_TEST_DRIVER'), 'Establecer DUA_TEST_DRIVER para pruebas locales de Edge')
class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.cancel = Event()
        self.bot = TICADUAExtractor({'edge_driver_path': os.environ['DUA_TEST_DRIVER'], 'mostrar_navegador': False}, cancel_event=self.cancel)
        self.addCleanup(self.bot.close)
        self.url = (Path(__file__).parent / 'fixtures/form.html').resolve().as_uri()

    def test_dates_over_twelve_months_and_focus_changes(self):
        with patch('tica_dua_bot.URL', self.url):
            records = self.bot.fetch_range('TRANSITO', '2024-02', 16, 29)
        self.assertEqual(records[0]['ano'], '2024')
        self.assertEqual(records[0]['numero'], '000001')

    def test_changed_date_is_never_submitted(self):
        with patch('tica_dua_bot.URL', self.url + '#change-start'):
            with self.assertRaisesRegex(ValueError, 'formulario cambió'):
                self.bot.fetch_range('TRANSITO', '2026-03', 1, 15)
        self.assertEqual(self.bot.driver.execute_script('return submitCount'), 0)

    def test_cancel_interrupts_wait(self):
        self.cancel.set()
        with self.assertRaises(Cancelled):
            self.bot.wait(lambda driver: False, 300)

    def test_transport_wait_exceeds_navigation_limit(self):
        connection = self.bot.driver.command_executor
        with patch.object(connection._conn, 'request', wraps=connection._conn.request) as request:
            self.assertEqual(self.bot.driver.timeouts.page_load, 180)
        self.assertEqual(request.call_args.kwargs['timeout'], 210)


if __name__ == '__main__':
    unittest.main()
