"""Tránsito: varias páginas, fallo parcial, SQLite y base TRANSITO sin red."""
import csv
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_bridge import DetailsBridge, wait_until


class TransitIntegrationTest(unittest.TestCase):
    def test_multirow_failure_daily_range_and_retained_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bridge = DetailsBridge(module_id='duas_transito', storage_root=root, offline_fixture=True)
            events = []
            bridge.eventReceived.connect(events.append)
            def call(command, data=None):
                offset = len(events)
                self.assertTrue(bridge._send(command, data))
                wait_until(lambda: not bridge.busy)
                replies = [event for event in events[offset:] if event['event'] in ('result', 'error')]
                self.assertTrue(replies, bridge.error)
                self.assertEqual(replies[-1]['event'], 'result', bridge.error)
                return replies[-1]
            try:
                bridge.connectModule()
                wait_until(lambda: bridge.ready or bool(bridge.error))
                self.assertTrue(bridge.ready, bridge.error)
                wait_until(lambda: not bridge.busy)
                self.assertEqual(len(bridge._snapshot['fields']), 8)
                call('configure', {'config': {'output_base_path': str(root/'output'), 'cant_hilos': 2, 'max_retries': 1}})
                source = root/'base.xlsx'
                # Qt conserva su entorno sin paquetes de bots; el Excel se prepara
                # con el entorno independiente de Tránsito.
                python = Path(__file__).resolve().parents[2]/'bots/duas_transito/.venv/Scripts/python.exe'
                subprocess.run([str(python), '-c',
                    "from openpyxl import Workbook; import sys; b=Workbook(); b.active.title='base'; "
                    "b.active.append(['NroDUA']); b.active.append(['001-2026-000001']); "
                    "b.active.append(['001-2026-999998']); b.save(sys.argv[1]); b.close()", str(source)], check=True)
                today = date.fromisoformat(bridge.daily['startDate']) + timedelta(days=1)
                start, end = today-timedelta(days=2), today-timedelta(days=1)
                month_names = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
                name = month_names[start.month-1] + str(start.year)[-2:]
                plan = call('prepare_import', {'source': str(source), 'sheet': 'base', 'name': name})['importPlan']
                call('import', plan)
                call('run')
                self.assertEqual(bridge.summary['succeeded'], 1)
                self.assertEqual(bridge.summary['retry'], 1)
                path = next((root/'output').rglob('*.csv'))
                def exported_rows():
                    with path.open(encoding='utf-8-sig', newline='') as stream:
                        return list(csv.DictReader(stream))
                rows = exported_rows()
                self.assertEqual(len(rows), 52)
                self.assertEqual(rows[-1]['Item'], '52')
                self.assertEqual(rows[0]['Partida'], '00001234')
                self.assertEqual(rows[0]['Descripción_Comercial'], 'Descripción con texto original')
                call('detail', {'jobId': '001-2026-000001'})
                self.assertEqual(len(bridge.jobDetail['resultRows']), 52)
                call('configure', {'config': {'daily_mode': True, 'daily_start_date': start.isoformat(), 'daily_end_date': end.isoformat()}})
                call('daily_run', {'bounded': True})
                self.assertEqual(bridge.daily['phase'], 'completed')
                self.assertFalse(bridge.dailyActive)
                self.assertEqual(bridge.summary['retry'], 1, 'El rango diario no procesa pendientes de otros días.')
                with closing(sqlite3.connect(root/'data/daily/bases.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT DISTINCT regimen FROM queries').fetchall(), [('TRANSITO',)])
                    attempts = db.execute('SELECT SUM(attempts) FROM queries').fetchone()[0]
                    self.assertEqual(attempts, 2)
                with closing(sqlite3.connect(root/'data/daily/calendar.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT state,total,succeeded FROM days ORDER BY day').fetchall(), [('completed',1,1), ('completed',1,1)])
                call('daily_run', {'bounded': True})
                with closing(sqlite3.connect(root/'data/daily/bases.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT SUM(attempts) FROM queries').fetchone()[0], attempts)
                # Limpiar filas completadas conserva todas sus líneas en el CSV mensual.
                call('clean', {'confirmTableId': bridge.activeTable['id'], 'confirmation': 'BORRAR'})
                call('export')
                rows = exported_rows()
                self.assertEqual(len(rows), 156 if start.month == end.month else 52 + 52)
                self.assertTrue(all(item.suffix=='.CSV' for item in (root/'output').rglob('*') if item.is_file()))
                self.assertTrue(list((root/'data/queues/backups').glob('*.sqlite3')))
            finally:
                bridge.shutdown()
                wait_until(lambda: bridge.isClosed)


if __name__ == '__main__':
    unittest.main()
