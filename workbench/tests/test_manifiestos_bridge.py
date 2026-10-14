"""Qt → workers propios → portal HTTP local → SQLite, recuperación y bases BLs."""
import csv
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until
from batch_bridge import BatchBridge


class ManifestIntegration(unittest.TestCase):
    def test_five_procedures_resume_and_bls_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bridge = BatchBridge(storage_root=root/'manifiestos',offline_fixture=True)
            bls = BatchBridge(module_id='bls',storage_root=root/'bls',offline_fixture=True)
            events = []
            bridge.eventReceived.connect(events.append)
            def call(flow, command, data=None, target=bridge):
                if target is bridge and flow!='bases':
                    target.setFlow(flow)
                channel = target.channels[flow]
                wait_until(lambda: not channel.busy,timeout=30000)
                start = len(events)
                self.assertTrue(channel.send(command,data))
                try:
                    wait_until(lambda: not channel.busy,timeout=60000)
                except AssertionError:
                    self.fail(flow+': '+channel.error+'\n'+channel.stderr[-3500:])
                self.assertFalse(channel.error, channel.error+'\n'+channel.stderr[-2500:])
                return [e for e in events[start:] if e.get('flow')==flow and e['event']=='result'][-1] if target is bridge else {}
            try:
                for flow in ('tabla','conocimientos','duas','movimientos','contenedores'):
                    call(flow,'run',{'config':{'year':2026,'month':10,'modes':['maritimo'],
                        'workers':2,'headless':True,'timeout':5,'name':flow}})
                    summary = dict(bridge.summary)
                    print(flow,summary,flush=True)
                    if flow=='tabla':
                        self.assertEqual((summary['total'],summary['succeeded'],summary['rows']),(1,1,3))
                    else:
                        self.assertEqual(summary['total'],3)
                        self.assertEqual(summary['succeeded'],2)
                        self.assertEqual(summary['excluded'],1 if flow=='duas' else 0)
                        self.assertEqual(summary['pending'],0 if flow=='duas' else 1)
                    record = bridge.current().snapshot
                    output = Path(record['outputFolder'])
                    self.assertTrue(list(output.glob('*.csv')))
                    self.assertTrue(all(p.suffix=='.csv' for p in output.iterdir()))
                    prefix = 'manifiestos' if flow=='tabla' else flow
                    with next(output.glob(prefix+'_*.csv')).open(encoding='utf-8-sig',newline='') as stream:
                        rows = list(csv.reader(stream))
                    if flow=='contenedores':
                        self.assertEqual(len(rows[0]),19)  # índice + los 18 campos, sin ID duplicado.
                    if flow=='conocimientos':
                        self.assertEqual(len(rows),4)  # tres conocimientos, uno Courier S.
                        self.assertEqual(rows[1][2],'00001234567890123456789')
                    # Reanudar solo lo pendiente; los guardados no repiten intentos.
                    call(flow,'run')
                    dbs = list((root/'manifiestos/data/jobs'/flow).glob('**/SQLite/**/*.sqlite3'))
                    self.assertTrue(dbs)
                    with closing(sqlite3.connect(dbs[0])) as db:
                        self.assertTrue(all(row[0]==1 for row in db.execute("select attempts from jobs where state='Guardado'")))
                        self.assertEqual(db.execute("select count(*) from jobs where state='Descargando'").fetchone()[0],0)
                event = call('bases','base_load',{'year':2026,'month':10,'mode':'maritimo','kind':'preferred'})
                info = event['snapshot']['baseInfo']
                self.assertEqual(len(info['sources']),1)
                self.assertEqual(info['periods'][0]['pending'],1)
                destination = root/'manifiestos/bases_bls/base.sqlite3'
                result = call('bases','base_build',{'periods':['2026-10|maritimo'],'destination':str(destination)})
                self.assertEqual(result['baseResult']['exported'],2)
                with closing(sqlite3.connect(destination)) as db:
                    rows = db.execute('select * from BLS order by rowid').fetchall()
                    self.assertEqual(rows[0][2],'00001234567890123456789')
                call('bls','run',{'config':{'input':str(destination),'sheet':'BLS','workers':1,
                    'headless':True,'timeout':5,'max_retries':1}},target=bls)
                self.assertEqual(bls.summary['succeeded'],2)
                self.assertEqual(bls.summary['rows'],2)
                call('bls','run',target=bls)
                self.assertEqual(bls.summary['succeeded'],2)
                self.assertTrue(all(p.suffix=='.csv' for p in Path(bls.current().snapshot['outputFolder']).iterdir()))
                # La base anterior no se sustituye sin confirmación.
                channel = bridge.channels['bases']
                self.assertTrue(channel.send('base_build',{'periods':['2026-10|maritimo'],'destination':str(destination)}))
                wait_until(lambda:not channel.busy)
                self.assertIn('ya existe',channel.error)
                self.assertEqual(destination.stat().st_size>0,True)
                source=next((root/'manifiestos/data/jobs/conocimientos').glob('**/SQLite/**/*.sqlite3'))
                digest=hashlib.sha256(source.read_bytes()).hexdigest()
                imported=BatchBridge(storage_root=root/'importado',offline_fixture=True)
                try:
                    channel=imported.current()
                    channel.send('import_progress',{'source':str(source)})
                    wait_until(lambda:not channel.busy)
                    self.assertFalse(channel.error,channel.error)
                    self.assertEqual(imported.summary['succeeded'],2)
                    self.assertEqual(imported.summary['pending'],1)
                    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)
                finally:
                    imported.shutdown()
                    wait_until(lambda:imported.isClosed)
            finally:
                bridge.shutdown(); bls.shutdown()
                wait_until(lambda:bridge.isClosed and bls.isClosed)

    def test_stop_keeps_confirmed_data_and_releases_active_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            previous=os.environ.get('CHC_MANIFEST_FIXTURE_SLOW')
            os.environ['CHC_MANIFEST_FIXTURE_SLOW']='3'
            bridge=BatchBridge(storage_root=Path(folder),offline_fixture=True)
            try:
                channel=bridge.current()
                self.assertTrue(channel.send('run',{'config':{'year':2026,'month':10,'headless':True,
                    'timeout':5,'workers':3,'name':'Detener'}}))
                wait_until(lambda:bridge.summary['succeeded']>=1 and bridge.summary['running']>0,timeout=20000)
                bridge.stop()
                wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertGreaterEqual(bridge.summary['succeeded'],1)
                self.assertEqual(bridge.summary['running'],0)
                dbpath=next((Path(folder)/'data/jobs/conocimientos').glob('**/SQLite/**/*.sqlite3'))
                with closing(sqlite3.connect(dbpath)) as db:
                    self.assertEqual(db.execute("select count(*) from jobs where state='Descargando'").fetchone()[0],0)
                    self.assertGreaterEqual(db.execute("select count(*) from jobs where state='Guardado'").fetchone()[0],1)
            finally:
                bridge.shutdown(); wait_until(lambda:bridge.isClosed)
                if previous is None: os.environ.pop('CHC_MANIFEST_FIXTURE_SLOW',None)
                else: os.environ['CHC_MANIFEST_FIXTURE_SLOW']=previous

    def test_existing_external_csv_is_preserved_before_query(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            output=root/'resultados/octubre26/conocimientos_maritimo_octubre26.csv'
            output.parent.mkdir(parents=True)
            output.write_text('archivo anterior',encoding='utf-8')
            bridge=BatchBridge(storage_root=root,offline_fixture=True)
            try:
                bridge.current().send('run',{'config':{'year':2026,'month':10,'name':'Existente','headless':True}})
                wait_until(lambda:not bridge.busy)
                self.assertIn('CSV ya existe',bridge.error)
                self.assertEqual(output.read_text(encoding='utf-8'),'archivo anterior')
                self.assertFalse(list((root/'data/jobs').glob('**/*.sqlite3')))
            finally:
                bridge.shutdown(); wait_until(lambda:bridge.isClosed)


if __name__=='__main__':
    unittest.main()
