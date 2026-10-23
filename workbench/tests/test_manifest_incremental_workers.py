"""Cinco procesos/portales locales: ampliar mes/modalidades sin repetir guardados."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until
from batch_bridge import BatchBridge,BatchChannel
from PySide6.QtCore import QProcess
from monthly_progress import MonthlyReader
from datetime import date


class IncrementalWorkersTests(unittest.TestCase):
    def test_five_flows_partial_both_extend_one_then_other_and_reopen_without_duplicates(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{'CHC_MANIFEST_FIXTURE_APPEND':'1'}):
            root=Path(folder)
            bridge=BatchBridge(storage_root=root,offline_fixture=True)
            provider=None
            def call(flow,config):
                bridge.setFlow(flow)
                channel=bridge.channels[flow]
                wait_until(lambda:not channel.busy)
                self.assertTrue(channel.send('run',{'config':config}))
                wait_until(lambda:not channel.busy,timeout=60000)
                self.assertFalse(channel.error,channel.error+'\n'+channel.stderr[-2200:])
                return channel.snapshot['activeId']
            def jobs(flow):
                result={}
                for path in (root/'data/jobs'/flow).glob('**/SQLite/**/*.sqlite3'):
                    if 'backups' in path.parts:continue
                    with closing(sqlite3.connect(path)) as db:
                        for row in db.execute('SELECT id,attempts,state,kept_count FROM jobs ORDER BY ordinal'):
                            result[(str(path),row[0])]=row[1:]
                return result
            ids={}
            try:
                for flow in ('tabla','conocimientos','duas','movimientos','contenedores'):
                    config=dict(year=2026,month=9,modes=['maritimo','aereo'],start='2026-09-01',end='2026-09-15',
                                workers=2,headless=True,timeout=5)
                    if flow=='contenedores':config['modes']=['maritimo']
                    initial=call(flow,config);before=jobs(flow)
                    snapshot=bridge.current().snapshot
                    messages=[event['message'] for event in bridge.current().activity_model.rows]
                    self.assertTrue(any('Exportando CSV desde SQLite' in message for message in messages),flow)
                    self.assertFalse(bridge.current().console.running)
                    if flow in ('conocimientos','duas','movimientos'):
                        self.assertTrue(any('Esperando HTTP' in message for message in messages),flow)
                    if flow=='duas':
                        self.assertTrue(any('sin límite de tiempo' in message for message in messages))
                    expected_modes=set(config['modes'])
                    self.assertEqual({j['mode'] for j in snapshot['jobs']},expected_modes)
                    self.assertEqual({s['mode'] for s in snapshot['modeSummaries']},expected_modes)
                    self.assertEqual(snapshot['summary']['rows'],sum(s['rows'] for s in snapshot['modeSummaries']))
                    if flow=='tabla':
                        self.assertEqual([j['id'] for j in snapshot['jobs']],['listado','listado'])
                    channel=bridge.current()
                    view_mode='maritimo' if flow=='contenedores' else 'aereo'
                    self.assertTrue(channel.send('view',dict(mode=view_mode,offset=0,search='')))
                    wait_until(lambda:not channel.busy)
                    self.assertTrue(channel.snapshot['jobs'])
                    self.assertTrue(all(j['mode']==view_mode for j in channel.snapshot['jobs']))
                    self.assertEqual(channel.snapshot['summary'],snapshot['summary'])
                    self.assertTrue(channel.send('view',dict(mode='',offset=0,search='')))
                    wait_until(lambda:not channel.busy)
                    self.assertTrue(before)
                    self.assertTrue(all(row[0]==1 for row in before.values()))
                    self.assertEqual(call(flow,{**config,'modes':['maritimo'],'end':'2026-09-30'}),initial)
                    maritime=jobs(flow)
                    self.assertTrue(all(maritime[key][0]==value[0] for key,value in before.items()))
                    self.assertEqual(call(flow,{**config,'modes':[view_mode],'end':'2026-09-30'}),initial)
                    after=jobs(flow)
                    self.assertEqual(len(bridge.current().snapshot['history']),1)
                    self.assertTrue(all(value[0]==1 and value[1]=='Guardado' for value in after.values()))
                    if flow=='tabla':
                        self.assertEqual(sum(v[2] for v in after.values()),6)
                    else:
                        self.assertEqual(len(after),3 if flow=='contenedores' else 6)
                    outputs=list((root/'resultados'/'MANIFIESTOS').glob('**/*.CSV'))
                    own=[p for p in outputs if ('CONOCIMIENTOS' if flow=='conocimientos' else 'LISTADO' if flow=='tabla' else flow.upper()) in p.parts]
                    self.assertEqual(len(own),1 if flow=='contenedores' else 2)
                    contents={p:p.read_bytes() for p in own}
                    self.assertEqual(call(flow,{**config,'end':'2026-09-30'}),initial)
                    self.assertEqual(jobs(flow),after)
                    self.assertEqual({p:p.read_bytes() for p in own},contents)
                    ids[flow]=initial
                    print(flow,'acumulado, modalidades y reanudación correctos',flush=True)
                report=MonthlyReader({'manifiestos':root},date(2026,10,17)).read()
                self.assertTrue(all(c['status']=='completed' for c in report['rows'][0]['procedures']))
                # El proveedor BLs ve la cobertura real acumulada completa.
                for path in (root/'data/jobs/conocimientos').glob('**/SQLite/**/*.sqlite3'):
                    with closing(sqlite3.connect(path)) as db:
                        from chc_runtime.knowledge_source import completed_source
                        self.assertEqual(completed_source(db)['ranges'],[('2026-09-01','2026-09-30')])
                provider=BatchChannel('manifiestos','bls_source',root,fixture=True)
                replies=[];provider.eventReceived.connect(replies.append)
                self.assertTrue(provider.send('knowledge_catalog'))
                wait_until(lambda:not provider.busy)
                self.assertFalse(provider.error,provider.error)
                self.assertEqual(len(provider.snapshot['knowledgeCatalog']['periods']),2)
                self.assertTrue(all(p['fullMonth'] for p in provider.snapshot['knowledgeCatalog']['periods']))
                self.assertTrue(provider.send('knowledge_build',{'periods':['2026-09|maritimo','2026-09|aereo']}))
                wait_until(lambda:not provider.busy)
                self.assertFalse(provider.error,provider.error)
                built=next(e['knowledgeBase'] for e in reversed(replies) if e.get('knowledgeBase'))
                self.assertTrue(all(p['fullMonth'] for p in built['coverage']))
                provider.shutdown();wait_until(lambda:provider.process.state()==QProcess.NotRunning)
                bridge.shutdown();wait_until(lambda:bridge.isClosed)
                bridge=BatchBridge(storage_root=root,offline_fixture=True)
                for flow in ('tabla','conocimientos','duas','movimientos','contenedores'):
                    before=jobs(flow)
                    modes=['maritimo'] if flow=='contenedores' else ['aereo']
                    self.assertEqual(call(flow,dict(year=2026,month=9,modes=modes,start='2026-09-01',end='2026-09-30',
                        workers=1,headless=True,timeout=5)),ids[flow])
                    self.assertEqual(jobs(flow),before)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)
                if provider:
                    provider.shutdown();wait_until(lambda:provider.process.state()==QProcess.NotRunning)


if __name__=='__main__':unittest.main()
