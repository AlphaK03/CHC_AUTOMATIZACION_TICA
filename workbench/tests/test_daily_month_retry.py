"""El worker real deja un día omitido, avanza y vuelve a intentar su mes explícitamente."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import DetailsBridge, wait_until

ROOT=Path(__file__).resolve().parents[2]
SEED='''
from pathlib import Path
from datetime import date
import sys
sys.path.insert(0,sys.argv[1])
from chc_runtime.daily import DailyLedger
ledger=DailyLedger(Path(sys.argv[2]))
for number in range(1,31):
 day=date(2026,9,number)
 ledger.save_base(day,['001-2026-999997','001-2026-000001'] if number==1 else ['001-2026-000002'] if number==2 else [])
 if number>2:ledger.update(day,state='completed',table_id='daily-2026-09')
'''


class MonthRetryWorkerTests(unittest.TestCase):
    def test_daily_three_attempts_then_manual_month_only_retries_unsaved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            subprocess.run([str(ROOT/'bots/talon/.venv/Scripts/python.exe'),'-c',SEED,str(ROOT),str(root)],check=True,cwd=ROOT)
            bridge=DetailsBridge(module_id='talon',storage_root=root,offline_fixture=True)
            events=[];bridge.eventReceived.connect(events.append)
            def call(command,data=None):
                start=len(events)
                self.assertTrue(bridge._send(command,data))
                wait_until(lambda:not bridge.busy,timeout=60000)
                replies=[e for e in events[start:] if e['event'] in ('result','error')]
                self.assertEqual(replies[-1]['event'],'result',bridge.error)
                return replies[-1]
            def jobs():
                with closing(sqlite3.connect(root/'data/queues/daily-2026-09.sqlite3')) as db:
                    return db.execute('SELECT dua,status,attempts,result FROM jobs ORDER BY dua').fetchall()
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                call('configure',{'config':{'output_base_path':str(root/'out'),'cant_hilos':2,'timeout':5,'max_retries':1,
                                           'daily_mode':True,'daily_start_date':'2026-09-01','daily_end_date':'2026-09-02'}})
                result=call('daily_run',{'bounded':True})
                self.assertEqual(result['runStatus'],'pending')
                before=jobs()
                self.assertEqual([(r[0],r[1],r[2]) for r in before],[('001-2026-000001','succeeded',1),('001-2026-000002','succeeded',1),('001-2026-999997','retry',3)])
                with closing(sqlite3.connect(root/'data/daily/calendar.sqlite3')) as db:
                    self.assertEqual(db.execute('SELECT state FROM days ORDER BY day LIMIT 2').fetchall(),[('omitted',),('completed',)])
                # La marca verde vive fuera de SQLite y no convierte el omitido
                # en completado para el coordinador ni para Reintentar mes.
                calendar_path=root/'data/daily/calendar.sqlite3'
                calendar_before=calendar_path.read_bytes()
                bridge.markCalendarDay('2026-09-01', True)
                marked=next(day for day in bridge.daily['days'] if day['date']=='2026-09-01')
                self.assertTrue(marked['manualCompleted'])
                self.assertEqual(marked['state'],'omitted')
                self.assertEqual(calendar_path.read_bytes(),calendar_before)
                self.assertEqual(jobs(),before)
                call('view',{'filter':'manual_pending'})
                self.assertEqual([r['dua'] for r in bridge.rows],['001-2026-999997'])
                self.assertTrue(bridge.rows[0]['autoOmitted'])
                call('daily_run',{'bounded':True});self.assertEqual(jobs(),before)
                config=dict(bridge.config)
                result=call('retry_month',{'month':'2026-09'})
                self.assertEqual(result['runStatus'],'pending')
                after=jobs()
                self.assertEqual(after[:2],before[:2])
                self.assertEqual(after[-1][2],6)
                self.assertEqual(bridge.config,config)
                self.assertTrue(next(day for day in bridge.daily['days'] if day['date']=='2026-09-01')['manualCompleted'])
                call('daily_run',{'bounded':True});self.assertEqual(jobs(),after)
                bridge.shutdown();wait_until(lambda:bridge.isClosed,timeout=45000)
                bridge=DetailsBridge(module_id='talon',storage_root=root,offline_fixture=True)
                bridge.eventReceived.connect(events.append)
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                call('daily_calendar',{'month':'2026-09'})
                self.assertTrue(next(day for day in bridge.daily['days'] if day['date']=='2026-09-01')['manualCompleted'])
                self.assertEqual(jobs(),after)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed,timeout=45000)


if __name__=='__main__':unittest.main()
