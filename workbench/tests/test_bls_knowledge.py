"""Solo conocimientos completos → base automática → motor BLs, en almacenamiento temporal."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until
from batch_bridge import BatchBridge

ROOT=Path(__file__).resolve().parents[2]


def sources(root, empty=False):
    code=("import sys; from pathlib import Path; sys.path.insert(0,str(Path('bots/manifiestos/src').resolve())); "
          "from chc_runtime.knowledge_fixture import create; root=Path(sys.argv[1]); ")
    if empty:
        code+="create(root,'vacio',rows=False)"
    else:
        code+=("create(root,'mar'); create(root,'aire',mode='aereo'); create(root,'agosto',mode='aereo',month=8); "
               "create(root,'pendiente',month=10,state='pending'); create(root,'activo',month=7,state='active'); "
               "create(root,'limitado',month=6,limited=True); create(root,'terrestre',month=5,mode='terrestre'); "
               "create(root,'courier',month=4,courier='S'); "
               "create(root,'rango',month=3,start='2026-03-01',end='2026-03-11')")
    subprocess.run([str(ROOT/'bots/manifiestos/.venv/Scripts/python.exe'),'-c',code,str(root)],cwd=ROOT,check=True)


class KnowledgeConnection(unittest.TestCase):
    def test_available_periods_pipeline_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            manifests=root/'manifiestos'
            sources(manifests)
            digests={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in manifests.glob('data/jobs/**/*.sqlite3')}
            bridge=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=manifests,offline_fixture=True)
            events=[]
            bridge.eventReceived.connect(events.append)
            try:
                bridge.connectModule()
                wait_until(lambda:bridge.ready and not bridge.busy)
                self.assertFalse(bridge.error,bridge.error)
                entries=bridge.knowledgeCatalog['periods']
                self.assertEqual({e['key'] for e in entries},{'2026-09|maritimo','2026-09|aereo','2026-08|aereo','2026-03|maritimo'})
                self.assertFalse(next(e for e in entries if e['period']=='2026-03')['fullMonth'])
                config={'inputMode':'knowledge','knowledgePeriods':['2026-09|maritimo','2026-09|aereo'],
                        'workers':1,'headless':True,'timeout':5,'max_retries':1,'name':''}
                self.assertTrue(bridge.command('run',{'config':config}))
                wait_until(lambda:not bridge.busy,timeout=20000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.summary['succeeded'],2)
                self.assertTrue(bridge.current().snapshot['outputFolder'].endswith('BLS'))
                self.assertTrue(any('BLs 2026-09 Marítimo y Aéreo' in r['label'] for r in bridge.current().snapshot['history']))
                original_input=bridge.config['input']
                with closing(sqlite3.connect(original_input)) as db:
                    rows=db.execute('SELECT * FROM BLS ORDER BY rowid').fetchall()
                    self.assertEqual(len(rows),2)
                    self.assertEqual({r[0].split('-')[0] for r in rows},{'1','4'})
                    self.assertTrue(all(r[2]=='00001234567890123456789' for r in rows))
                self.assertTrue(bridge.command('run',{'config':config}))
                wait_until(lambda:not bridge.busy,timeout=20000)
                self.assertFalse(bridge.error,bridge.error)
                records=list((root/'bls/data/jobs/bls').glob('**/SQLite/bls.sqlite3'))
                self.assertEqual(len(records),1)
                with closing(sqlite3.connect(records[0])) as db:
                    self.assertEqual(db.execute('select sum(attempts) from jobs').fetchone()[0],2)
                self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in digests.items()))
                self.assertTrue(bridge.command('run',{'config':{**config,'knowledgePeriods':['2026-08|aereo']}}))
                wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.summary['succeeded'],1)
                self.assertTrue(bridge.current().snapshot['outputFolder'].endswith('BLS'))
                self.assertTrue(any('BLs 2026-08 Aéreo' in r['label'] for r in bridge.current().snapshot['history']))
                # Un período no ofrecido se rechaza antes de arrancar BLs.
                count=len([e for e in events if e.get('flow')=='bls' and e.get('command')=='run' and e['event']=='result'])
                bridge.command('run',{'config':{**config,'knowledgePeriods':['2026-10|maritimo']}})
                wait_until(lambda:not bridge.busy)
                self.assertIn('no está disponible',bridge.error)
                self.assertEqual(len([e for e in events if e.get('flow')=='bls' and e.get('command')=='run' and e['event']=='result']),count)
            finally:
                bridge.shutdown(); wait_until(lambda:bridge.isClosed)

    def test_completed_empty_source_starts_no_queries(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sources(root/'manifiestos',empty=True)
            bridge=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=root/'manifiestos',offline_fixture=True)
            try:
                bridge.connectModule()
                wait_until(lambda:bridge.ready and not bridge.busy)
                self.assertEqual(len(bridge.knowledgeCatalog['periods']),1)
                bridge.command('run',{'config':{'inputMode':'knowledge','knowledgePeriods':['2026-09|maritimo']}})
                wait_until(lambda:not bridge.busy)
                self.assertFalse(bridge.error,bridge.error)
                self.assertIn('no hay BLs',bridge.status)
                self.assertFalse(list((root/'bls/data/jobs').glob('**/*.sqlite3')))
            finally:
                bridge.shutdown(); wait_until(lambda:bridge.isClosed)


if __name__=='__main__': unittest.main()
