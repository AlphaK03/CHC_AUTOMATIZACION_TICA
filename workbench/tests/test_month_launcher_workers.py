"""Inicio del mes → procesos originales aislados → SQLite local → reanudación."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import DetailsBridge,wait_until
from batch_bridge import BatchBridge
from month_launcher import MonthLauncher
from monthly_progress import MonthlyReader


class MonthWorkers(unittest.TestCase):
    def test_four_dua_bots_resume_bounded_month_and_do_not_repeat_confirmed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            bridges={m:DetailsBridge(module_id=m,storage_root=root/m,offline_fixture=True)
                     for m in ('detalles','duas_transito','talon','xmovimientos')}
            launcher=MonthLauncher(bridges)
            try:
                for bridge in bridges.values():bridge.connectModule()
                wait_until(lambda:all(b.ready and not b.busy for b in bridges.values()))
                # Historial local confirmado: 29 días vacíos; queda el último día.
                # No se lee ni escribe ningún calendario de producción.
                for module,bridge in bridges.items():
                    with closing(sqlite3.connect(root/module/'data/daily/calendar.sqlite3')) as db:
                        db.executemany('INSERT INTO days(day,state,base_ready,table_id,total,succeeded) VALUES (?,?,?,?,0,0)',
                            [(f'2026-09-{n:02d}','completed',1,'daily-2026-09') for n in range(1,30)])
                        db.commit()
                    launcher.setSelected(module,True);launcher.setWorkers(module,2)
                launcher.setPeriod(2026,9);launcher.start()
                wait_until(lambda:not launcher.active and all(not b.busy for b in bridges.values()),timeout=90000)
                self.assertTrue(all(t['stage']=='completed' for t in launcher.tasks.values()),launcher.items)
                attempts={}
                for module,bridge in bridges.items():
                    self.assertEqual((bridge.config['daily_start_date'],bridge.config['daily_end_date'],bridge.config['cant_hilos']),('2026-09-01','2026-09-30',2))
                    self.assertFalse(bridge.dailyActive)
                    with closing(sqlite3.connect(root/module/'data/queues/daily-2026-09.sqlite3')) as db:
                        attempts[module]=db.execute('SELECT sum(attempts) FROM jobs').fetchone()[0]
                        self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE status!='succeeded'").fetchone()[0],0)
                    self.assertEqual(attempts[module],9 if module=='detalles' else 1 if module=='duas_transito' else 4)
                report=MonthlyReader({m:root/m for m in bridges}).read()
                self.assertEqual(report['errors'],0)
                self.assertTrue(all(c['status']=='completed' for c in report['rows'][0]['cells'][:4]),report)
                launcher.start()
                wait_until(lambda:not launcher.active and all(not b.busy for b in bridges.values()))
                for module in bridges:
                    with closing(sqlite3.connect(root/module/'data/queues/daily-2026-09.sqlite3')) as db:
                        self.assertEqual(db.execute('SELECT sum(attempts) FROM jobs').fetchone()[0],attempts[module])
            finally:
                launcher.cancel()
                for bridge in bridges.values():bridge.shutdown()
                wait_until(lambda:all(b.isClosed for b in bridges.values()))

    @patch.dict(os.environ,{'CHC_MANIFEST_FIXTURE_COMPLETE':'1'})
    def test_five_manifest_procedures_then_bls_and_same_month_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            manifests=BatchBridge(storage_root=root/'manifiestos',offline_fixture=True)
            bls=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=root/'manifiestos',offline_fixture=True)
            # Mismo refresco automático que usa app.py al finalizar Conocimientos.
            manifests.eventReceived.connect(lambda event:bls.refreshKnowledge() if
                event.get('flow')=='conocimientos' and event.get('event')=='idle' and event.get('command')=='run' else None)
            launcher=MonthLauncher({'manifiestos':manifests,'bls':bls})
            try:
                manifests.connectModule();bls.connectModule()
                wait_until(lambda:manifests.ready and bls.ready and not manifests.busy and not bls.busy)
                launcher.setPeriod(2026,9)
                for item in launcher.items:launcher.setSelected(item['id'],item['module'] in ('manifiestos','bls'));launcher.setWorkers(item['id'],1)
                launcher.start()
                wait_until(lambda:not launcher.active,timeout=90000)
                self.assertEqual(launcher.tasks['conocimientos']['stage'],'completed',launcher.items)
                self.assertEqual(launcher.tasks['bls']['stage'],'completed',launcher.items)
                self.assertGreater(bls.summary['succeeded'],0)
                for flow in ('tabla','conocimientos','duas','movimientos','contenedores'):
                    snapshot=manifests.channels[flow].snapshot
                    self.assertEqual((snapshot['config']['year'],snapshot['config']['month'],snapshot['config']['workers']),(2026,9,1))
                    self.assertEqual(snapshot['summary']['pending'],0)
                databases=list((root/'bls/data/jobs').glob('**/SQLite/bls.sqlite3'))
                self.assertEqual(len(databases),1)
                with closing(sqlite3.connect(databases[0])) as db:before=db.execute('SELECT sum(attempts) FROM jobs').fetchone()[0]
                launcher.start();wait_until(lambda:not launcher.active,timeout=90000)
                self.assertEqual(launcher.tasks['bls']['stage'],'completed',launcher.items)
                self.assertEqual(len(list((root/'bls/data/jobs').glob('**/SQLite/bls.sqlite3'))),1)
                with closing(sqlite3.connect(databases[0])) as db:self.assertEqual(db.execute('SELECT sum(attempts) FROM jobs').fetchone()[0],before)
            finally:
                launcher.cancel();manifests.shutdown();bls.shutdown()
                wait_until(lambda:manifests.isClosed and bls.isClosed)


if __name__=='__main__':unittest.main()
