"""Acumulación aislada: nuevos manifiestos, filtros, cobertura y recuperación."""
from contextlib import closing
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'bots/manifiestos/src'))
from conocimientos import KnowledgeStore, COLUMNS, GridPage
from chc_runtime.manifest_adapters import CumulativeKnowledgeStore
from chc_runtime.manifest_coverage import cumulative_days, day_ranges
from chc_runtime.knowledge_source import completed_source, Unavailable
from chc_runtime.manifest_incremental import query_range

A='1-0-20260001-P027-01/09/26'
B='1-0-20260002-P027-01/09/26'
C='1-0-20260004-P027-20/09/26'
D='1-0-20260005-P027-21/09/26'


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.scope=dict(version=1,mode='maritimo',month=9,year=2026,courier=None,
                        url='https://ticaconsultas.hacienda.go.cr/Tica/hcicgmic.aspx',
                        desde='2026-09-01',hasta='2026-09-15',ids=[],limit=None)
        self.csv=self.root/'data.csv';self.path=self.root/'data.sqlite3'

    def jobs(self,*ids):return [(n,'',{},mid) for n,mid in enumerate(ids,1)]

    def rows(self,mid):return [[mid,'1']+['00001']*(len(COLUMNS)-2)]

    def finish(self,store):
        store.start_run();count=0
        for job in store.jobs():
            if job['state']!='Pendiente':continue
            store.claim(job['id']);count+=1
            store.save(job['id'],job['ordinal'],self.rows(job['id']),{'pages':1,'read':1,'kept':1})
        store.finish_run(count)

    def test_legacy_backup_expand_and_same_range_append_keep_saved_attempts_and_rows(self):
        old=KnowledgeStore(self.csv,self.scope,db_path=self.path)
        old.prepare_selection(self.jobs(A));self.finish(old)
        before=list(old.db.execute('SELECT * FROM jobs'))
        values=list(old.db.execute('SELECT * FROM rows'));old.close()
        store=CumulativeKnowledgeStore(self.csv,{**self.scope,'hasta':'2026-09-30'},db_path=self.path)
        try:
            backups=list((self.root/'backups').glob('incremental-*.sqlite3'));self.assertEqual(len(backups),1)
            with closing(sqlite3.connect(backups[0])) as db:
                self.assertEqual(list(db.execute('SELECT * FROM jobs')),before)
                self.assertEqual(list(db.execute('SELECT * FROM rows')),values)
            store.prepare_selection(self.jobs(A,B,C));self.finish(store)
            self.assertEqual(store.job(A)['attempts'],1)
            self.assertEqual(list(store.db.execute('SELECT * FROM rows WHERE manifest=?',(A,))),values)
            self.assertEqual(len(cumulative_days(store.db)),30)
            self.assertEqual(completed_source(store.db)['ranges'],[('2026-09-01','2026-09-30')])
            store.prepare_selection(self.jobs(A,B,C,D));self.finish(store)
            self.assertEqual([job['attempts'] for job in store.jobs()],[1,1,1,1])
            self.assertEqual(store.summary()['rows'],4)
            store.prepare_selection(self.jobs(A,B,C,D));self.finish(store)
            self.assertEqual([job['attempts'] for job in store.jobs()],[1,1,1,1])
        finally:store.close()

    def test_gap_ranges_and_failed_or_cancelled_queries_do_not_invent_coverage(self):
        store=CumulativeKnowledgeStore(self.csv,{**self.scope,'hasta':'2026-09-10'},db_path=self.path)
        store.prepare_selection(self.jobs(A));self.finish(store);store.close()
        store=CumulativeKnowledgeStore(self.csv,{**self.scope,'desde':'2026-09-20','hasta':'2026-09-30'},db_path=self.path)
        store.prepare_selection(self.jobs(C));self.finish(store)
        self.assertEqual(day_ranges(cumulative_days(store.db)),[('2026-09-01','2026-09-10'),('2026-09-20','2026-09-30')])
        self.assertEqual(len(completed_source(store.db)['ranges']),2)
        store.prepare_selection(self.jobs(C,D));store.start_run();store.claim(D)
        store.save_checkpoint(D,GridPage({}, {},self.rows(D),0,False))
        store.interrupt('Detenido');store.close()
        store=CumulativeKnowledgeStore(self.csv,{**self.scope,'desde':'2026-09-20','hasta':'2026-09-30'},db_path=self.path)
        try:
            self.assertEqual(len(store.load_checkpoint(D)),1)
            with self.assertRaises(Unavailable):completed_source(store.db)
            self.assertEqual(len(cumulative_days(store.db)),21)
            store.prepare_selection(self.jobs(C,D));self.finish(store)
            self.assertEqual(store.job(C)['attempts'],1)
            self.assertEqual(store.job(D)['attempts'],2)
            self.assertFalse(store.load_checkpoint(D))
        finally:store.close()

    def test_subset_only_reserves_current_selection_and_other_filters_rejected(self):
        store=CumulativeKnowledgeStore(self.csv,self.scope,db_path=self.path)
        store.prepare_selection(self.jobs(A,B));store.start_run();store.claim(A)
        store.save(A,1,self.rows(A),{'pages':1,'read':1,'kept':1});store.finish_run(1);store.close()
        store=CumulativeKnowledgeStore(self.csv,{**self.scope,'desde':'2026-09-20','hasta':'2026-09-30'},db_path=self.path)
        try:
            store.prepare_selection(self.jobs(C));self.finish(store)
            self.assertEqual(store.job(B)['attempts'],0)
            self.assertEqual(store.job(B)['state'],'Pendiente')
            self.assertEqual([job['id'] for job in store.jobs()],[C])
        finally:store.close()
        with self.assertRaisesRegex(ValueError,'otros filtros|otro mes'):
            CumulativeKnowledgeStore(self.csv,{**self.scope,'courier':'N'},db_path=self.path)

    def test_limited_selection_keeps_original_frozen_contract(self):
        scope={**self.scope,'limit':1}
        store=CumulativeKnowledgeStore(self.csv,scope,db_path=self.path)
        try:
            store.prepare_selection(self.jobs(A));self.finish(store)
            store.prepare_selection(self.jobs(A,B))
            self.assertEqual([job['id'] for job in store.jobs()],[A])
            self.assertIsNone(cumulative_days(store.db))
        finally:store.close()

    def test_removed_members_or_jobs_do_not_accredit_an_empty_query(self):
        store=CumulativeKnowledgeStore(self.csv,self.scope,db_path=self.path)
        try:
            store.prepare_selection(self.jobs(A));self.finish(store)
            self.assertEqual(len(cumulative_days(store.db,True)),15)
            row=store.db.execute('SELECT * FROM jobs').fetchone()
            with store.db:store.db.execute('DELETE FROM jobs')
            self.assertFalse(cumulative_days(store.db,True))
            with store.db:
                store.db.execute('INSERT INTO jobs VALUES ('+','.join('?' for _ in row)+')',row)
                store.db.execute('DELETE FROM workbench_query_jobs')
            self.assertFalse(cumulative_days(store.db,True))
        finally:store.close()

    def test_confirmed_empty_and_midnight_cutoff(self):
        store=CumulativeKnowledgeStore(self.csv,self.scope,db_path=self.path)
        try:
            store.prepare_selection([]);self.finish(store)
            self.assertEqual(len(cumulative_days(store.db)),15)
            self.assertEqual(completed_source(store.db)['manifests'],0)
        finally:store.close()
        scope={**self.scope,'desde':'2026-10-01','hasta':'2026-10-31'}
        self.assertEqual(query_range(scope,datetime.fromisoformat('2026-10-17T00:00:00-06:00'))[1],'2026-10-15')
        self.assertEqual(query_range(scope,datetime.fromisoformat('2026-10-17T00:01:00-06:00'))[1],'2026-10-16')

    def test_courier_n_is_valid_for_bls_but_not_unfiltered_month_coverage(self):
        from workbench.monthly_progress import MonthlyReader
        path=self.root/'data/jobs/conocimientos/month/rows.sqlite3'
        path.parent.mkdir(parents=True)
        store=CumulativeKnowledgeStore(self.csv,{**self.scope,'courier':'N','hasta':'2026-09-30'},db_path=path)
        try:
            store.prepare_selection(self.jobs(A));self.finish(store)
            self.assertEqual(completed_source(store.db)['ranges'],[('2026-09-01','2026-09-30')])
        finally:store.close()
        reader=MonthlyReader({'manifiestos':self.root},date(2026,10,17));reader.read()
        self.assertNotEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'completed')


if __name__=='__main__':unittest.main()
