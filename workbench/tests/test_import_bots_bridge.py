"""Talón/XMovimientos: formulario real con portal local, SQLite y calendario."""
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

IMPORT_REGIMES = {'IMPORTACION DEFINITIVA', 'IMPORTACION TEMPORAL', 'REIMPORTACION',
                  'REIMPORTACION PERFECCIONAMIENTO PASIVO'}


class ImportBotsIntegrationTest(unittest.TestCase):
    def check_module(self, module):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bridge = DetailsBridge(module_id=module, storage_root=root, offline_fixture=True)
            events = []
            bridge.eventReceived.connect(events.append)
            def call(command, data=None):
                offset = len(events)
                self.assertTrue(bridge._send(command, data))
                wait_until(lambda: not bridge.busy, timeout=90000)
                replies = [event for event in events[offset:] if event['event'] in ('result','error')]
                self.assertTrue(replies, bridge.error)
                self.assertEqual(replies[-1]['event'], 'result', bridge.error)
                return replies[-1]
            try:
                bridge.connectModule()
                wait_until(lambda: bridge.ready or bool(bridge.error))
                self.assertTrue(bridge.ready, bridge.error)
                wait_until(lambda: not bridge.busy)
                self.assertEqual(len(bridge._snapshot['fields']), 7 if module=='talon' else 6)
                call('configure', {'config': {'output_base_path':str(root/'output'),
                                              'cant_hilos':2, 'max_retries':1, 'timeout':5}})
                python = Path(__file__).resolve().parents[2]/'bots'/module/'.venv/Scripts/python.exe'
                source = root/'Total_DUAS - Importacion.xlsx'
                subprocess.run([str(python),'-c',
                    "from openpyxl import Workbook; import sys; b=Workbook(); b.active.title='base'; "
                    "b.active.append(['NroDUA']); [b.active.append(['001-2026-'+n]) for n in "
                    "['000001','000050','999998','999997']]; b.save(sys.argv[1]); b.close()", str(source)],check=True)
                plan=call('prepare_import',{'source':str(source),'sheet':'base','name':'Prueba importacion'})['importPlan']
                call('import',plan)
                manual_id=bridge.activeTable['id']
                call('run')
                self.assertEqual(bridge.summary['succeeded'],2,bridge.error)
                self.assertEqual(bridge.summary['retry'],2)
                csv_path=next(Path(bridge.outputFolder).glob('*.csv'))
                def read_csv(path):
                    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
                rows=read_csv(csv_path)
                self.assertEqual(len(rows),54)
                ordinary=[row for row in rows if row['numero_del_dua']=='001-2026-000001']
                self.assertEqual(len(ordinary),2)
                if module=='talon':
                    self.assertEqual(ordinary[0]['Tributo'],'001')
                    self.assertEqual(ordinary[0]['Valor_MN'],'1 234.50')
                else:
                    self.assertEqual(ordinary[0]['Cantidad_de_Bultos_asociada'],'1203.5')
                    self.assertEqual(ordinary[0]['Deposito'],'0001')
                call('detail',{'jobId':'001-2026-000050'})
                self.assertEqual(len(bridge.jobDetail['resultRows']),52)
                with closing(sqlite3.connect(root/'data/queues'/f'{manual_id}.sqlite3')) as db:
                    self.assertIsNone(db.execute("select result from jobs where dua='001-2026-999998'").fetchone()[0])
                no_rows=root/'data/exports'/manual_id/'sin_filas.txt'
                self.assertEqual(no_rows.read_text().strip(),'001-2026-999997')
                today=date.fromisoformat(bridge.daily['startDate'])+timedelta(days=1)
                start,end=today-timedelta(days=2),today-timedelta(days=1)
                call('configure',{'config':{'daily_mode':True,'daily_start_date':start.isoformat(),'daily_end_date':end.isoformat()}})
                call('daily_run')
                self.assertEqual(bridge.daily['phase'],'completed')
                with closing(sqlite3.connect(root/'data/daily/bases.sqlite3')) as db:
                    self.assertEqual({row[0] for row in db.execute('select distinct regimen from queries')},IMPORT_REGIMES)
                    self.assertEqual(db.execute('select sum(attempts) from queries').fetchone()[0],8)
                with closing(sqlite3.connect(root/'data/daily/calendar.sqlite3')) as db:
                    self.assertEqual(db.execute('select state,total,succeeded from days order by day').fetchall(),
                                     [('completed',4,4),('completed',4,4)])
                call('daily_run')
                with closing(sqlite3.connect(root/'data/daily/bases.sqlite3')) as db:
                    self.assertEqual(db.execute('select sum(attempts) from queries').fetchone()[0],8)
                call('select',{'tableId':manual_id})
                self.assertEqual(bridge.summary['retry'],2)
                call('clean',{'confirmTableId':manual_id})
                call('export')
                self.assertEqual(len(read_csv(csv_path)),54)
                self.assertTrue(all(path.suffix=='.csv' for path in (root/'output').rglob('*') if path.is_file()))
            finally:
                bridge.shutdown()
                wait_until(lambda:bridge.isClosed)

    def test_talon(self):
        self.check_module('talon')

    def test_xmovimientos(self):
        self.check_module('xmovimientos')


if __name__=='__main__':
    unittest.main()
