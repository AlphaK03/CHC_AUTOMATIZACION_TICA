"""Tres oportunidades persistentes, avance al día siguiente y reintento mensual explícito."""
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest

from chc_runtime.catalog import TableCatalog
from chc_runtime.daily import DailyJobStore, DailyCoordinator, DownloadPending, ZONE
from chc_runtime.job_store import JobStore

A='001-2026-000001'
B='001-2026-000002'
C='001-2026-000003'


class QuickEvent(Event):
    def wait(self, timeout=None):return self.is_set()


class OmissionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)

    def tearDown(self):self.temp.cleanup()

    def test_budget_persists_across_restart_and_cancellation_does_not_consume_it(self):
        p=self.root/'jobs.sqlite3'
        store=JobStore(p);store.import_values([A]);store.close()
        store=DailyJobStore(p,[A],automatic=True)
        try:
            store.begin_run()
            store.retry(store.claim(1),'Detenido','interrupted',cancelled=True)
            self.assertEqual(store.db.execute('SELECT used FROM daily_automatic_attempts').fetchone()[0],0)
            store.begin_run()
            for n in range(1,4):store.retry(store.claim(n),'Sin tributos','NoRowsException')
            self.assertIsNone(store.claim(4))
        finally:store.close()
        store=DailyJobStore(p,[A],automatic=True)
        try:
            store.begin_run()
            self.assertIsNone(store.claim(1))
            self.assertEqual(store.summary()['automatic_ready'],0)
            self.assertEqual(store.summary()['attempts'],4)
        finally:store.close()
        store=DailyJobStore(p,[A],automatic=False)
        try:
            store.begin_run();store.complete(store.claim(1),{'numero_del_dua':A})
            self.assertEqual(store.summary()['succeeded'],1)
        finally:store.close()

    def service(self):
        service=SimpleNamespace(root=self.root,profile={'id':'detalles'},Store=JobStore,
            machine={'daily_mode':True,'daily_start_date':'2026-09-01','daily_end_date':'2026-09-02','output_base_path':str(self.root/'out')},
            stop_event=QuickEvent(),protocol=SimpleNamespace(emit=lambda *a,**k:None))
        service.catalog=TableCatalog(self.root/'data/queues')
        service.snapshot=lambda:{}
        service.local_root=lambda:self.root/'out'
        service.configure=lambda values:service.machine.update(values)
        service.select=lambda table_id:setattr(service,'active_id',table_id)
        service.read_database=lambda record:closing(sqlite3.connect(service.catalog.database(record)))
        return service

    def test_bad_day_is_omitted_next_day_completes_and_manual_month_only_retries_pending(self):
        service=self.service();daily=DailyCoordinator(service,offline=True,now=lambda:datetime(2026,10,14,10,tzinfo=ZONE))
        daily.download=lambda day:[A,B] if day.day==1 else [C]
        recover=False
        def execute(command,request):
            store=DailyJobStore(service.catalog.database(service.catalog.get(service.active_id)),request['daily_duas'],automatic=request['daily_automatic'])
            try:
                store.begin_run()
                for n in range(1,4):
                    while (job:=store.claim(n)) is not None:
                        if job['dua']==A and not recover:store.retry(job,'Sin tributos','NoRowsException')
                        else:store.complete(job,{'numero_del_dua':job['dua']})
            finally:store.close()
        service.execute=execute
        result=daily.run()
        self.assertEqual(result['runStatus'],'pending')
        self.assertEqual(daily.ledger.get(date(2026,9,1))['state'],'omitted')
        self.assertEqual(daily.ledger.get(date(2026,9,2))['state'],'completed')
        path=service.catalog.database(service.catalog.get(service.active_id))
        with closing(sqlite3.connect(path)) as db:
            before=db.execute('SELECT dua,attempts,status FROM jobs ORDER BY dua').fetchall()
        self.assertEqual(before,[(A,3,'retry'),(B,1,'succeeded'),(C,1,'succeeded')])
        daily.run()
        with closing(sqlite3.connect(path)) as db:self.assertEqual(db.execute('SELECT dua,attempts,status FROM jobs ORDER BY dua').fetchall(),before)
        service.machine.update(daily_start_date='2026-10-05',daily_end_date='2026-10-06')
        config=dict(service.machine);recover=True
        result=daily.run(date(2026,9,1),date(2026,9,2),manual=True)
        self.assertEqual(result['runStatus'],'completed')
        self.assertEqual(service.machine,config)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT dua,attempts,status FROM jobs ORDER BY dua').fetchall(),[(A,4,'succeeded'),(B,1,'succeeded'),(C,1,'succeeded')])
        self.assertEqual(daily.ledger.get(date(2026,9,1))['state'],'completed')

    def test_missing_base_is_omitted_after_three_cycles_without_blocking_next_day(self):
        service=self.service();daily=DailyCoordinator(service,offline=True,now=lambda:datetime(2026,10,14,10,tzinfo=ZONE))
        calls=[]
        def download(day):
            calls.append(day)
            if day.day==1:raise DownloadPending('No se confirmó la base')
            return []
        daily.download=download;service.execute=lambda *a,**k:None
        self.assertEqual(daily.run()['runStatus'],'pending')
        self.assertEqual(calls.count(date(2026,9,1)),3)
        self.assertEqual(calls.count(date(2026,9,2)),1)
        self.assertEqual(daily.ledger.get(date(2026,9,1))['base_ready'],0)
        self.assertEqual(daily.ledger.get(date(2026,9,1))['state'],'omitted')
        before=list(calls);daily.run();self.assertEqual(calls,before)


if __name__=='__main__':unittest.main()
