"""Subidas individuales explícitas: CSV exacto, alcance, propiedad y recuperación."""
import json
import os
from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from chc_cloud.service import CloudService
from chc_cloud.graph import GraphError
from chc_cloud.tests.test_service import Account, Graph
from chc_runtime import output_layout


class ManualUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.account=Account();self.graph=Graph()
        self.monthly=lambda:{'rows':[]}
        self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)
        self.service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
        self.service.save_destination('drive','folder')
        self.original=b'Numero;Descripcion\r\n00001;Texto original\r\n'

    def tearDown(self):
        self.service.db.close()

    def csv(self,name='Contenedores_julio26.CSV'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(self.original)
        return path

    def inspect(self,path):
        result=self.service.execute({'command':'inspect_upload','path':str(path)})
        return result['snapshot']['manualUpload']

    def upload(self,plan):
        return self.service.execute({'command':'upload_file','token':plan['token']})['uploadResult']

    def restart(self):
        self.service.db.close()
        self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)

    def test_independent_july_and_august_require_action_and_send_only_selected_csv(self):
        # Un envío anterior no debe colarse en la acción de subir un archivo.
        earlier=self.csv('Talon_enero26.csv')
        self.service.enqueue({'target':'talon','path':str(earlier),'name':'enero26','owner':'old'})
        for name,period in [('Contenedores_julio26.CSV','2026-07'),('Contenedores_agosto26.CSV','2026-08')]:
            plan=self.inspect(self.csv(name))
            self.assertEqual(plan['target'],'manifiestos:contenedores')
            self.assertEqual(plan['period'],period)
            self.assertEqual(plan['mode'],'maritimo')
            self.assertTrue(plan['reviewed'])
            self.assertEqual(self.service.months(),[])
            before=len(self.graph.sent)
            self.service.execute({'command':'status'})
            self.assertEqual(len(self.graph.sent),before)
            self.assertEqual(self.upload(plan)['state'],'synced')
            self.assertEqual(len(self.graph.sent),before+1)
            self.assertEqual(self.graph.sent[-1][1],self.original)
        self.assertEqual(self.service.db.execute("SELECT state FROM jobs WHERE owner='old'").fetchone()[0],'pending')
        self.assertEqual(self.service.months(),[])

    def test_unknown_filename_needs_review_and_rejects_old_token(self):
        plan=self.inspect(self.csv('reporte.csv'))
        self.assertFalse(plan['reviewed'])
        with self.assertRaisesRegex(ValueError,'Revisa'):self.upload(plan)
        result=self.service.execute({'command':'review_upload','token':plan['token'],
            'target':'manifiestos:contenedores','period':'2026-08','mode':'maritimo'})
        reviewed=result['snapshot']['manualUpload']
        self.assertIn('AGOSTO_2026',reviewed['relativePath'])
        with self.assertRaises(ValueError):self.upload(plan)
        self.assertEqual(self.upload(reviewed)['state'],'synced')

    def test_failed_new_file_selection_invalidates_previous_authorization(self):
        plan=self.inspect(self.csv())
        with self.assertRaises(ValueError):self.inspect(self.csv('not-a-csv.txt'))
        with self.assertRaisesRegex(ValueError,'Revisa'):self.upload(plan)
        self.assertFalse(self.graph.sent)

    def test_only_csv_and_maritime_containers_and_valid_metadata(self):
        for name in ('secret.txt','Contenedores_AEREO_julio26.csv','Contenedores_TERRESTRE_julio26.csv'):
            with self.assertRaises(ValueError):self.inspect(self.csv(name))
        plan=self.inspect(self.csv('reporte.csv'))
        for target,period,mode in [('unknown','2026-07','maritimo'),('talon','2026-99',''),
                                   ('manifiestos:contenedores','2026-07','aereo'),('bls','2026-07','terrestre')]:
            with self.assertRaises(ValueError):self.service.review_upload(plan['token'],target,period,mode)
        self.assertFalse(self.graph.sent)

    def test_file_changed_even_with_preserved_size_and_timestamp_is_rejected(self):
        path=self.csv();plan=self.inspect(path);before=path.stat()
        path.write_bytes(self.original.replace(b'00001',b'00002'))
        os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'cambió'):self.upload(plan)
        self.assertFalse(self.graph.sent)
        self.assertEqual(self.service.db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)

    def test_destination_or_account_changed_after_review_requires_another_review(self):
        plan=self.inspect(self.csv())
        self.service.save_destination('drive','other-folder')
        with self.assertRaisesRegex(ValueError,'destino cambiaron'):self.upload(plan)
        self.service.destination['accountId']='different-account'
        with self.assertRaises(ValueError):self.upload(plan)
        self.assertFalse(self.graph.sent)

    def test_failure_survives_restart_and_only_explicit_retry_sends_exact_spool(self):
        source=self.csv();plan=self.inspect(source)
        self.graph.fail=True
        self.assertEqual(self.upload(plan)['state'],'error')
        source.unlink()
        self.restart();self.graph.fail=False
        self.service.execute({'command':'status'})
        self.service.sync()  # El mecanismo mensual no envía autorizaciones individuales.
        self.assertFalse(self.graph.sent)
        self.service.execute({'command':'retry'})
        self.assertEqual(len(self.graph.sent),1)
        self.assertEqual(self.graph.sent[0][1],self.original)
        self.assertEqual(self.service.snapshot()['pending'],0)

    def test_manual_update_keeps_etag_and_other_file_cannot_overwrite_destination(self):
        source=self.csv();self.upload(self.inspect(source))
        duplicate=self.csv('other/'+source.name)
        with self.assertRaises(GraphError):self.upload(self.inspect(duplicate))
        source.write_bytes(self.original+b'00002;Otro\r\n')
        self.upload(self.inspect(source))
        self.assertEqual(len(self.graph.sent),2)
        self.assertEqual(self.graph.sent[-1][2]['etag'],'tag1')
        self.assertEqual(self.graph.sent[-1][1],source.read_bytes())

    def test_registered_csv_reuses_identity_without_month_completion_and_retired_csv_is_rejected(self):
        source=self.csv();base=self.root/'RESULTADOS'
        self.service.execute({'command':'local_root','path':str(base)})
        spec=output_layout.specification('manifiestos:contenedores','2026-07','maritimo')
        export=output_layout.publish(source,base,spec,'containers-july',self.service.exports_registry)
        self.service.enqueue({'target':spec['target'],'path':export['path'],'spec':spec,'owner':'containers-july','name':'julio26'})
        plan=self.inspect(Path(export['path']))
        self.assertTrue(plan['registered'])
        self.assertEqual(Path(plan['relativePath']).name,spec['filename'])
        self.assertEqual(self.upload(plan)['state'],'synced')
        self.assertEqual(self.service.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
        self.assertEqual(self.service.months(),[])
        with closing(output_layout.open_registry(self.service.exports_registry)) as db:
            with db:db.execute('UPDATE exports SET final=0')
        with self.assertRaisesRegex(ValueError,'sustituido'):self.inspect(Path(export['path']))

    def test_tampered_spool_is_not_sent_on_retry(self):
        self.graph.fail=True;self.upload(self.inspect(self.csv()))
        spool=Path(self.service.db.execute('SELECT spool FROM jobs').fetchone()[0])
        spool.write_bytes(b'Changed data')
        self.graph.fail=False;self.service.execute({'command':'retry'})
        self.assertFalse(self.graph.sent)
        self.assertIn('cambió',self.service.snapshot()['tasks'][0]['error'])


if __name__=='__main__':unittest.main()
