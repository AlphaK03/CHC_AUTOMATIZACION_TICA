"""Reabrir un lote incompleto: conservar un BL confirmado y consultar solo el pendiente."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import wait_until
from batch_bridge import BatchBridge

ROOT = Path(__file__).resolve().parents[2]
SEED = '''
from pathlib import Path
import sys, sqlite3
from threading import Event
from contextlib import closing
repo, root = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0,str(repo))
sys.path.insert(0,str(repo/'bots/bls/src'))
from input_files import load_input_file, BLS_COLUMNS
from config_manager import DEFAULTS
from core.inputs import batch_scope
from core.store import JobStore
from chc_runtime.manifest_service import BatchService
base=root/'base.sqlite3'
with closing(sqlite3.connect(base)) as db:
    db.execute('CREATE TABLE BLS ('+','.join('"'+c+'" TEXT NOT NULL' for c in BLS_COLUMNS)+')')
    db.executemany('INSERT INTO BLS VALUES (?,?,?,?,?)',[
        ('1-0-00001-A01-01/09/26','1','00001234567890123456789','01/09/2026','2026-09'),
        ('1-0-00001-A01-01/09/26','2','0000987654321','01/09/2026','2026-09')])
    db.commit()
service=BatchService(root,'bls',lambda *a,**k:None,Event())
service.index['config'].update(input=str(base),inputMode='file',name='Retomar',workers=1,max_retries=1)
record=service.prepare()
frame=load_input_file(base,'BLS')
signature,scope=batch_scope(frame,{**DEFAULTS,'sheet_name':'BLS'})
scope['revision']=''
store=JobStore(Path(record['work'])/'BLS'/signature[:16]/'SQLite/bls.sqlite3',signature,scope)
try:
    store.prepare(frame)
    store.start_run()
    key,ordinal,original=store.pending()[0]
    token=store.claim(key)
    store.save(key,token,['BL','Aduana','manifiesto','bls'],[
        [original['BL original'],'013',original['IDManifiesto'],original['BL original']]])
    store.finish_run(stopped=True)
finally: store.close()
record['state']='Detenido'
service.inspect()
service.save()
'''


class BLSResumeTests(unittest.TestCase):
    def test_pending_only_after_reopening(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            subprocess.run([str(ROOT/'bots/bls/.venv/Scripts/python.exe'),'-c',SEED,str(ROOT),str(root)],
                           cwd=ROOT,check=True)
            database=next(root.glob('data/jobs/bls/**/SQLite/bls.sqlite3'))
            bridge=BatchBridge(module_id='bls',storage_root=root,offline_fixture=True)
            events=[]
            bridge.eventReceived.connect(events.append)
            try:
                bridge.connectModule()
                wait_until(lambda:bridge.ready and not bridge.busy)
                self.assertEqual(bridge.summary['succeeded'],1)
                self.assertEqual(bridge.summary['pending'],1)
                self.assertIn('00001234567890123456789',bridge.jobs[0]['id'])
                self.assertEqual(bridge.jobs[0]['ordinal'],1)
                original_id=bridge.activeId
                self.assertTrue(bridge.command('run',{}))
                wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.activeId,original_id)
                self.assertEqual(bridge.summary['succeeded'],2)
                messages=[event['message'] for event in bridge.activityModel.rows]
                self.assertTrue(any('BL=0000987654321' in message for message in messages))
                self.assertTrue(any('Exportando CSV de BLs' in message for message in messages))
                self.assertTrue(any('Exportando CSV desde SQLite' in message for message in messages))
                self.assertFalse(bridge.consoleMonitor.running)
                self.assertEqual(len(bridge.history),1)
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('SELECT ordinal,attempts,state FROM jobs ORDER BY ordinal').fetchall(),
                                     [(1,1,'Guardado'),(2,1,'Guardado')])
                self.assertEqual(len(list(root.glob('data/jobs/bls/**/SQLite/bls.sqlite3'))),1)
                self.assertTrue(all(e['snapshot']['summary']['succeeded']>=1
                    for e in events if e.get('event')=='progress' and 'snapshot' in e))
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)


if __name__=='__main__': unittest.main()
