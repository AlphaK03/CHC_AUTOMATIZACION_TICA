"""Descargas guardadas sin CSV y selección múltiple, sin TICA ni Graph reales."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sqlite3

from chc_cloud.service import CloudService
from chc_cloud.tests.test_service import Account,Graph
from chc_runtime import output_layout


def manifest_history(root):
    history=[]
    for month,name in ((7,'julio26'),(8,'agosto26'),(9,'septiembre26')):
        history.append(dict(id='record-'+str(month),name=name,state='Completado',cumulative=True,
            spec=dict(year=2026,month=month,modes=['maritimo','aereo'],courier='todos',ids=[],limit=0),databases=[]))
    path=root/'data/workbench/contenedores/session.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'history':history,'active':'record-9','config':{'month':9}}),encoding='utf-8')
    return history,path


class DownloadCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.bot=self.root/'bots/manifiestos'
        self.history,self.session=manifest_history(self.bot)
        self.graph=Graph();self.account=Account()
        self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=lambda:{'rows':[]},roots={'manifiestos':self.bot})
        self.service.execute({'command':'local_root','path':str(self.root/'RESULTADOS')})
        self.service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
        self.service.save_destination('drive','folder')
        self.source=self.root/'rows.csv';self.source.write_bytes(b'DUA;Texto\r\n0001;original\r\n')

    def tearDown(self):self.service.db.close()

    def refresh(self):
        return self.service.execute({'command':'list_downloads'})['snapshot']['downloadCatalog']

    def publish(self,month):
        record=next(record for record in self.history if record['spec']['month']==month)
        spec=output_layout.manifest_spec('contenedores',record,'maritimo')
        return output_layout.publish(self.source,self.root/'RESULTADOS',spec,'contenedores:'+record['id'],self.service.exports_registry)

    def upload(self,catalog,ids):
        return self.service.execute({'command':'upload_downloads','token':catalog['token'],'ids':ids,
            'destination':{k:self.service.destination[k] for k in ('accountId','driveId','folderId')}})['downloadUploadResult']

    def test_lists_saved_july_august_before_export_without_writes_or_coverage_requirement(self):
        before=self.session.read_bytes();catalog=self.refresh()
        self.assertEqual({r['period'] for r in catalog['rows']},{'2026-07','2026-08','2026-09'})
        self.assertTrue(all(r['canGenerate'] and not r['csvReady'] for r in catalog['rows']))
        self.assertEqual({r['mode'] for r in catalog['rows']},{'maritimo'})
        self.assertFalse(self.graph.sent)
        self.assertEqual(before,self.session.read_bytes())
        self.assertFalse(self.service.exports_registry.exists())

    def test_dua_catalogs_are_separate_and_bls_never_guesses_period_from_batch_name(self):
        for module in output_layout.BOTS:
            if module=='bls':continue
            root=self.root/'bots'/module;folder=root/'data/queues';folder.mkdir(parents=True)
            with closing(sqlite3.connect(folder/'catalog.sqlite3')) as db:
                db.execute('CREATE TABLE saved_tables(id TEXT,name TEXT,filename TEXT,source_path TEXT,deleted INTEGER)')
                db.execute("INSERT INTO saved_tables VALUES('same-id','julio26','jobs.sqlite3','daily://2026-07',0)")
                db.commit()
            (folder/'jobs.sqlite3').touch()
            self.service.download_roots[module]=root
        bls=self.root/'bots/bls';path=bls/'data/workbench/bls/session.json';path.parent.mkdir(parents=True)
        record=dict(id='multi',name='octubre26',config={})
        path.write_text(json.dumps({'history':[record]}),encoding='utf-8')
        self.service.download_roots['bls']=bls
        rows=self.refresh()['rows']
        dua=[row for row in rows if row['module'] in ('detalles','duas_transito','talon','xmovimientos')]
        self.assertEqual(len(dua),4)
        self.assertEqual(len({row['id'] for row in dua}),4)
        self.assertEqual({row['period'] for row in dua},{'2026-07'})
        self.assertEqual([row['period'] for row in rows if row['module']=='bls'],[''])
        record['publicSpecs']=[output_layout.specification('bls',period,'maritimo') for period in ('2026-07','2026-08')]
        path.write_text(json.dumps({'history':[record]}),encoding='utf-8')
        self.assertEqual({row['period'] for row in self.refresh()['rows'] if row['module']=='bls'},{'2026-07','2026-08'})

    def test_generation_keeps_stable_ids_and_batch_upload_uses_each_route_and_only_selection(self):
        old=self.refresh();ids=[r['id'] for r in old['rows'] if r['period'] in ('2026-07','2026-08')]
        for month in (7,8,9):self.publish(month)
        catalog=self.refresh()
        self.assertEqual(set(ids),{r['id'] for r in catalog['rows'] if r['period'] in ('2026-07','2026-08')})
        report=self.upload(catalog,ids)
        self.assertEqual((report['uploaded'],report['errors']),(2,0))
        self.assertEqual({r[0] for r in self.graph.sent},
            {'MANIFIESTOS_CONTENEDORES_MARITIMO_JULIO_2026.CSV','MANIFIESTOS_CONTENEDORES_MARITIMO_AGOSTO_2026.CSV'})
        self.assertTrue(all(r[1]==self.source.read_bytes() for r in self.graph.sent))
        self.assertTrue(any(folder[2]=='JULIO_2026' for folder in self.graph.created))
        self.assertTrue(any(folder[2]=='AGOSTO_2026' for folder in self.graph.created))
        self.assertFalse(any(folder[2]=='SEPTIEMBRE_2026' for folder in self.graph.created))
        self.assertEqual(self.service.months(),[])

    def test_missing_csv_stale_list_or_unknown_id_cannot_upload(self):
        catalog=self.refresh();ids=[r['id'] for r in catalog['rows']]
        with self.assertRaisesRegex(ValueError,'Falta un CSV'):self.upload(catalog,ids)
        with self.assertRaises(ValueError):self.upload(catalog,['unknown'])
        self.refresh()
        with self.assertRaisesRegex(ValueError,'Actualiza'):self.upload(catalog,ids)
        self.assertFalse(self.graph.sent)

    def test_changed_destination_and_deleted_csv_are_revalidated(self):
        export=self.publish(7);catalog=self.refresh();ids=[r['id'] for r in catalog['rows'] if r['period']=='2026-07']
        request={'command':'upload_downloads','token':catalog['token'],'ids':ids,
            'destination':{k:self.service.destination[k] for k in ('accountId','driveId','folderId')}}
        self.service.save_destination('drive','different')
        with self.assertRaisesRegex(ValueError,'destino cambiaron'):self.service.execute(request)
        Path(export['path']).unlink()
        with self.assertRaisesRegex(ValueError,'Falta un CSV'):self.upload(catalog,ids)
        self.assertFalse(self.graph.sent)

    def test_unrelated_pending_job_is_not_sent_and_failed_selected_jobs_can_retry(self):
        self.publish(7);self.publish(8)
        self.service.enqueue({'target':'talon','path':str(self.source),'name':'2026-06','owner':'other'})
        catalog=self.refresh();ids=[r['id'] for r in catalog['rows'] if r['period'] in ('2026-07','2026-08')]
        self.graph.fail=True;report=self.upload(catalog,ids)
        self.assertEqual(report['errors'],2)
        self.assertEqual(self.service.db.execute("SELECT state FROM jobs WHERE owner='other'").fetchone()[0],'pending')
        self.graph.fail=False;self.service.execute({'command':'retry'})
        self.assertEqual(len(self.graph.sent),2)


if __name__=='__main__':unittest.main()
