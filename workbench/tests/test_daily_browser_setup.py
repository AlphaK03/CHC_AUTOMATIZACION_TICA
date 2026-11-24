"""Arranque compartido, errores y cierre Qt con un instalador falso sin red."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_bridge import APP, DetailsBridge, wait_until
from daily_browser_bridge import DailyBrowserSetup


class BrowserStartupTests(unittest.TestCase):
    def run_setup(self, script, check):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'tools').mkdir()
            (root / 'tools/install_daily_driver.py').write_text(script, encoding='utf-8')
            with patch('daily_browser_bridge.packaged', return_value=False), patch('daily_browser_bridge.ROOT', root):
                setup = DailyBrowserSetup()
                try:
                    check(setup, root)
                finally:
                    setup.shutdown()
                    wait_until(lambda: setup.isClosed)

    def test_one_background_preparation_serves_four_bots_without_starting_downloads(self):
        def check(setup, root):
            bridges = [DetailsBridge(module_id=module, storage_root=root/module, browser_setup=setup)
                       for module in ('detalles', 'duas_transito', 'talon', 'xmovimientos')]
            self.assertTrue(all(not bridge.dailyBrowserReady for bridge in bridges))
            setup.start()
            setup.start()
            for bridge in bridges:
                bridge.startDaily()
                self.assertFalse(bridge._requests)
                self.assertFalse(bridge.dailyActive)
            ticks = []
            from PySide6.QtCore import QTimer
            timer = QTimer()
            timer.timeout.connect(lambda: ticks.append(1))
            timer.start(10)
            wait_until(lambda: not setup.busy)
            timer.stop()
            self.assertTrue(ticks, 'La comprobación no bloquea el bucle Qt.')
            self.assertTrue(setup.ready, setup.error)
            self.assertTrue(all(bridge.dailyBrowserReady for bridge in bridges))
            self.assertEqual((root/'calls').read_text(), '1')
            self.assertFalse(list(root.rglob('*.sqlite3')))
            for bridge in bridges:
                bridge.shutdown()
        self.run_setup("""
from pathlib import Path
import json,time
path=Path('calls');path.write_text(path.read_text()+'1' if path.exists() else '1')
time.sleep(.2)
print(json.dumps({'event':'result','message':'Listo','updated':False,'version':'158'}),flush=True)
""", check)

    def test_failed_preparation_keeps_daily_start_disabled_and_displays_reason(self):
        def check(setup, root):
            bridge = DetailsBridge(storage_root=root/'bot', browser_setup=setup)
            setup.start()
            wait_until(lambda: not setup.busy)
            self.assertFalse(setup.ready)
            self.assertIn('Sin conexión', bridge.error)
            bridge.retryMonth('2026-11')
            self.assertFalse(bridge._requests)
            self.assertFalse(bridge.dailyActive)
            bridge.shutdown()
        self.run_setup("""
import json,sys
print(json.dumps({'event':'error','message':'Sin conexión; controlador anterior conservado.'}),flush=True)
sys.exit(1)
""", check)

    def test_close_prevents_late_success_from_enabling_bots(self):
        def check(setup, root):
            setup.start()
            wait_until(lambda: setup.process.processId() > 0)
            setup.shutdown()
            wait_until(lambda: setup.isClosed)
            self.assertFalse(setup.ready)
            self.assertFalse(setup.busy)
        self.run_setup("""
import json,sys
sys.stdin.readline()
print(json.dumps({'event':'result','message':'Respuesta tardía'}),flush=True)
""", check)

    def test_demo_or_packaged_app_never_starts_installer(self):
        for packaged, enabled in ((False, False), (True, True)):
            with self.subTest(packaged=packaged), patch('daily_browser_bridge.packaged', return_value=packaged):
                setup = DailyBrowserSetup(enabled=enabled)
                with patch.object(setup.process, 'start') as start:
                    setup.start()
                    start.assert_not_called()
                self.assertTrue(setup.ready)
                setup.shutdown()


if __name__ == '__main__':
    unittest.main()
