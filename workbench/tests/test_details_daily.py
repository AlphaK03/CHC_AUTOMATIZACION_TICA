"""Prueba puntual del ciclo diario: base local, calendario y reanudación sin red."""
from datetime import date, timedelta
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_bridge import APP, DetailsBridge, wait_until


class DailyPilotTest(unittest.TestCase):
    def test_two_days_accumulate_and_resume_without_redownloading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bridge = DetailsBridge(storage_root=root, offline_fixture=True)
            try:
                bridge.connectModule()
                wait_until(lambda: bridge.ready or bool(bridge.error))
                self.assertTrue(bridge.ready, bridge.error)
                wait_until(lambda: not bridge.busy)
                today = date.fromisoformat(bridge.daily['startDate']) + timedelta(days=1)
                start = today - timedelta(days=2)
                self.assertTrue(bridge._send('configure', {'config': {
                    'daily_mode': True, 'daily_start_date': start.isoformat(),
                    'output_base_path': str(root / 'output'), 'cant_hilos': 1, 'max_retries': 1}}))
                wait_until(lambda: not bridge.busy)
                bridge.startDaily()
                wait_until(lambda: bridge.daily['phase'] == 'waiting' or bool(bridge.error), timeout=60000)
                self.assertFalse(bridge.error, bridge.error)
                self.assertTrue(bridge.dailyActive)
                with closing(sqlite3.connect(root / 'data/daily/calendar.sqlite3')) as db:
                    days = db.execute('SELECT day,state,total,succeeded FROM days ORDER BY day').fetchall()
                self.assertEqual(days, [(start.isoformat(), 'completed', 9, 9),
                                        ((start + timedelta(days=1)).isoformat(), 'completed', 9, 9)])
                self.assertEqual(sum(item['summary']['succeeded'] for item in bridge.tables), 18)
                self.assertTrue(list((root / 'output').rglob('*.csv')))
                self.assertTrue(all(path.suffix == '.csv' for path in (root / 'output').rglob('*') if path.is_file()))
                bridge.loadCalendar(start.strftime('%Y-%m'))
                wait_until(lambda: not any(item['command'] == 'daily_calendar' for item in bridge._requests.values()))
                self.assertTrue(any(cell['state'] == 'completed' for cell in bridge.daily['days']))
                self.assertTrue(bridge.busy, 'Leer calendario no libera la operación diaria.')
                bridge.stopQueries()
                wait_until(lambda: not bridge.busy)
                self.assertFalse(bridge.dailyActive)
                with closing(sqlite3.connect(root / 'data/daily/bases.sqlite3')) as db:
                    attempts = db.execute('SELECT SUM(attempts) FROM queries').fetchone()[0]
                bridge.startDaily()
                wait_until(lambda: bridge.daily['phase'] == 'waiting' or bool(bridge.error))
                self.assertFalse(bridge.error, bridge.error)
                bridge.stopQueries()
                wait_until(lambda: not bridge.busy)
                with closing(sqlite3.connect(root / 'data/daily/bases.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT SUM(attempts) FROM queries').fetchone()[0], attempts)
                self.assertEqual(sum(item['summary']['succeeded'] for item in bridge.tables), 18)
            finally:
                bridge.shutdown()
                wait_until(lambda: bridge.isClosed)


if __name__ == '__main__':
    unittest.main()
