"""Alcance persistente de la reconsulta, incluidas sus rondas de reintentos."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'bots/bls/src'))
import pandas as pd
from core.store import JobStore
from chc_runtime.bls_empty_retry import begin,generations


class EmptyRetryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/'work/BLS/signature/SQLite/bls.sqlite3'
        self.store=JobStore(self.path,'signature',{})
        self.addCleanup(self.store.close)
        frame=pd.DataFrame([{'IDManifiesto':'1-0-00001-A01-01/09/26','Secuencia Tica':str(n),
                'BL original':'000'+str(n),'Fecha Manifiesto':'01/09/2026','Mes':'2026-09'} for n in range(1,5)])
        self.store.prepare(frame);self.store.start_run()
        for key,ordinal,payload in self.store.pending():
            token=self.store.claim(key)
            if ordinal==4:self.store.fail(key,token,'Anterior','transient')
            else:self.store.save(key,token,['col'],[['existente']] if ordinal==3 else [])
        self.store.finish_run()
        self.request={'database':str(self.path),'backups':str(self.root/'backups')}

    def test_every_retry_round_stays_within_reopened_empty_jobs(self):
        before=self.store.db.execute('SELECT * FROM jobs WHERE ordinal IN (3,4) ORDER BY ordinal').fetchall()
        self.assertEqual(begin(self.store,self.request),2)
        self.assertEqual(len(generations(self.store.db)),2)
        count,queue=self.store.pending_queue()
        jobs=list(queue);self.store.close_pending_queue()
        self.assertEqual(count,2)
        self.assertEqual([j[1] for j in jobs],[1,2])
        for key,_,_ in jobs:
            token=self.store.claim(key);self.store.fail(key,token,'Nuevo fallo','transient')
        count,queue=self.store.pending_queue(transient_only=True)
        self.assertEqual(count,2)
        self.assertEqual([j[1] for j in queue],[1,2])
        self.store.close_pending_queue()
        self.assertEqual(self.store.db.execute('SELECT * FROM jobs WHERE ordinal IN (3,4) ORDER BY ordinal').fetchall(),before)

    def test_backup_failure_or_wrong_database_does_not_reopen_anything(self):
        before=self.store.db.execute('SELECT * FROM jobs ORDER BY ordinal').fetchall()
        with self.assertRaises(ValueError):
            begin(self.store,{**self.request,'database':str(self.root/'other.sqlite3')})
        with patch('chc_runtime.bls_empty_retry.sqlite3.connect',side_effect=OSError('disco')):
            with self.assertRaises(OSError):begin(self.store,self.request)
        self.assertEqual(self.store.db.execute('SELECT * FROM jobs ORDER BY ordinal').fetchall(),before)
        self.assertEqual(generations(self.store.db),{})


if __name__=='__main__':unittest.main()
