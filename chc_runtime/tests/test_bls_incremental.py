"""Ampliación BLs con firmas antiguas, historial y restricciones de mes/modo."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'bots/bls/src'))
import pandas as pd
from config_manager import DEFAULTS
from core.inputs import batch_scope
from chc_runtime.bls_incremental import family,find_record
from chc_runtime.bls_session import WorkbenchBLSProcessor


def row(sequence, bl=None, month=10, mode='4'):
    return {'IDManifiesto':f'{mode}-1-0002601287L-P001-13/{month:02d}/26',
            'Secuencia Tica':str(sequence),'BL original':bl or '000000'+str(sequence),
            'Fecha Manifiesto':f'13/{month:02d}/2026','Mes':f'2026-{month:02d}'}


class IncrementalBLSTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config={**DEFAULTS,'output_base_path':str(self.root/'jobs'),'cant_hilos':1,'max_retries':1}
        self.queried=[];self.fail=set();self.empty=set()

    async def run_bot(self, data, request=None, empty_retry=None):
        owner=self
        class Session:
            async def query(self, record):
                owner.queried.append(record['BL original'])
                if record['BL original'] in owner.fail:raise RuntimeError('Fallo temporal de prueba')
                return {'status':'success','columns':['dato','manifiesto','bls'],
                    'rows':[] if record['BL original'] in owner.empty else [['valor',record['IDManifiesto'],record['BL original']]]}
            async def close(self):pass
        config=dict(self.config)
        if request:config['workbench_bls_accumulation']=request
        if empty_retry:config['workbench_empty_retry']=empty_retry
        return await WorkbenchBLSProcessor(config,Event()).run_async(pd.DataFrame(data),session_factory=lambda _:Session())

    def request(self, first, data, periods=None):
        with closing(sqlite3.connect(first['database'])) as db:
            metadata=dict(db.execute('SELECT key,value FROM metadata'))
        signature,_=batch_scope(pd.DataFrame(data),self.config)
        scope=json.loads(metadata['scope'])
        return dict(signature=metadata['signature'],scope=scope,input_signature=signature,
            family=family({'inputMode':'knowledge','knowledgePeriods':periods or ['2026-10|aereo']},scope),
            backups=str(self.root/'backups'))

    async def test_legacy_grows_reordered_input_and_retries_pending_without_repeating_saved_or_empty(self):
        self.fail={'0000002'};self.empty={'0000003'}
        first=await self.run_bot([row(1),row(2),row(3)])
        self.assertEqual((first['saved'],first['pending']),(2,1))
        with closing(sqlite3.connect(first['database'])) as db:
            saved=db.execute("SELECT * FROM jobs WHERE ordinal IN (1,3) ORDER BY ordinal").fetchall()
            signature=db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0]
        data=[row(4),row(3),row(2),row(1)]
        self.fail.clear();self.queried.clear()
        request=self.request(first,data)
        second=await self.run_bot(data,request)
        self.assertEqual(second['database'],first['database'])
        self.assertEqual(self.queried,['0000002','0000004'])
        with closing(sqlite3.connect(first['database'])) as db:
            self.assertEqual(db.execute("SELECT * FROM jobs WHERE ordinal IN (1,3) ORDER BY ordinal").fetchall(),saved)
            self.assertEqual(db.execute('SELECT ordinal,attempts FROM jobs ORDER BY ordinal').fetchall(),[(1,1),(2,2),(3,1),(4,1)])
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0],signature)
            self.assertEqual(db.execute('SELECT expected,added FROM workbench_bls_queries').fetchall(),[(4,1)])
        self.queried.clear();await self.run_bot(data,request)
        self.assertEqual(self.queried,[])
        self.assertEqual(len(list((self.root/'jobs').rglob('bls.sqlite3'))),1)

    async def test_smaller_snapshot_keeps_old_results_and_does_not_query_absent_pending(self):
        self.fail={'0000002'}
        first=await self.run_bot([row(1),row(2)])
        self.queried.clear();self.fail.clear()
        data=[row(1),row(3)]
        second=await self.run_bot(data,self.request(first,data))
        self.assertEqual(self.queried,['0000003'])
        self.assertEqual((second['total'],second['pending'],second['result_rows']),(3,1,2))
        with closing(sqlite3.connect(first['database'])) as db:
            self.assertEqual(db.execute('SELECT state,attempts FROM jobs WHERE ordinal=2').fetchone(),('Pendiente',1))

    async def test_accumulated_input_keeps_manual_empty_retry_available(self):
        from chc_runtime.bls_incremental import verify_input
        self.empty={'0000001'}
        first=await self.run_bot([row(1)])
        data=[row(1),row(2)];request=self.request(first,data)
        second=await self.run_bot(data,request)
        with closing(sqlite3.connect(second['database'])) as db:
            records=[json.loads(r[0]) for r in db.execute('SELECT payload FROM inputs ORDER BY ordinal')]
            verify_input(db,records,request['scope'])
        self.empty.clear();self.queried.clear()
        request={**request,'append':False};request.pop('input_signature')
        third=await self.run_bot(data,request,dict(database=second['database'],backups=str(self.root/'empty_backups')))
        self.assertEqual(third['database'],second['database'])
        self.assertEqual(self.queried,['0000001'])
        self.assertEqual((third['saved'],third['result_rows']),(2,2))

    async def test_conflicting_bl_or_other_month_mode_cannot_change_confirmed_jobs(self):
        first=await self.run_bot([row(1)])
        with closing(sqlite3.connect(first['database'])) as db:
            before=db.execute('SELECT * FROM jobs').fetchall()
        for data in ([row(1,bl='otro')],[row(1),row(2,month=9)],[row(1),row(2,mode='1')]):
            with self.subTest(data=data),self.assertRaises(ValueError):
                await self.run_bot(data,self.request(first,data))
            with closing(sqlite3.connect(first['database'])) as db:
                self.assertEqual(db.execute('SELECT * FROM jobs').fetchall(),before)
        self.assertFalse(list((self.root/'backups').glob('*.sqlite3')))

    async def test_backup_failure_keeps_legacy_jobs_and_results(self):
        from core.store import JobStore
        from chc_runtime.bls_incremental import append
        first=await self.run_bot([row(1)])
        data=[row(1),row(2)];request=self.request(first,data)
        store=JobStore(first['database'],request['signature'],request['scope'])
        try:
            before=store.db.execute('SELECT * FROM jobs').fetchall()
            with patch('chc_runtime.bls_incremental.sqlite3.connect',side_effect=OSError('disco')):
                with self.assertRaises(OSError):append(store,pd.DataFrame(data),request)
            self.assertEqual(store.db.execute('SELECT * FROM jobs').fetchall(),before)
            self.assertEqual(store.db.execute('SELECT count(*) FROM results').fetchone()[0],1)
        finally:store.close()

    async def test_failed_append_rolls_back_jobs_and_inputs_without_touching_results(self):
        first=await self.run_bot([row(1)])
        with closing(sqlite3.connect(first['database'])) as db:
            db.execute("""CREATE TRIGGER reject_addition BEFORE INSERT ON jobs WHEN NEW.ordinal>1
                BEGIN SELECT RAISE(ABORT,'fallo de prueba'); END""")
            db.commit()
        data=[row(1),row(2)]
        with self.assertRaises(sqlite3.IntegrityError):
            await self.run_bot(data,self.request(first,data))
        with closing(sqlite3.connect(first['database'])) as db:
            self.assertEqual(db.execute('SELECT state,attempts,result_count FROM jobs').fetchall(),[('Guardado',1,1)])
            self.assertEqual(db.execute('SELECT count(*) FROM inputs').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM results').fetchone()[0],1)

    def test_family_requires_identical_months_modes_and_scope_and_can_find_legacy_record(self):
        _,scope=batch_scope(pd.DataFrame([row(1)]),self.config)
        config={'inputMode':'knowledge','knowledgePeriods':['2026-10|aereo'],'sheet':'BLS'}
        record={'id':'old','config':config,'summary':{'succeeded':20}}
        selected=family(config,scope)
        self.assertIs(find_record([record],selected),record)
        for periods in (['2026-09|aereo'],['2026-10|maritimo'],['2026-10|aereo','2026-10|maritimo']):
            self.assertIsNone(find_record([record],family({**config,'knowledgePeriods':periods},scope)))
        self.assertNotEqual(selected,family(config,{**scope,'target_url':'otra-busqueda'}))


if __name__=='__main__':unittest.main()
