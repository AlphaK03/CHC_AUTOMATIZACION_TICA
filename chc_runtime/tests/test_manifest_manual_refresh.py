"""Actualización manual con portal local y SQLite propios de cada prueba."""
import asyncio
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'bots/manifiestos/src'))
from chc_runtime.manifest_service import BatchService
from chc_runtime.manifest_manual_refresh import refresh_saved,apply_manifest
from chc_runtime.manifest_refresh_audit import fingerprints,packed,now
from chc_runtime.manifest_fixture import FixturePortal


class ManualRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.services = []
        self.addCleanup(lambda:[s.close() for s in self.services])

    def prepare(self,flow):
        service = BatchService(self.root,flow,lambda *args,**kwargs:None,Event(),True)
        self.services.append(service)
        service.execute('run',dict(config=dict(year=2026,month=9,modes=['maritimo'],
            headless=True,timeout=5,workers=2)))
        return service,Path(service.active()['databases'][0])

    def request(self,service):
        return dict(recordId=service.active()['id'],year=2026,month=9,modes=['maritimo'],workers=2)

    def rows(self,path):
        with closing(sqlite3.connect(path)) as db:
            return list(db.execute('SELECT * FROM rows ORDER BY manifest,sequence'))

    def test_two_flows_replace_complete_preserve_pending_csv_backup_and_repeat(self):
        for flow in ('conocimientos','duas'):
            with self.subTest(flow=flow):
                service,path = self.prepare(flow)
                before = self.rows(path)
                with closing(sqlite3.connect(path)) as db:
                    pending = list(db.execute("SELECT * FROM jobs WHERE state!='Guardado'"))
                service.execute('export',{})
                csvs = {p:p.read_bytes() for p in self.root.rglob('*.CSV')}
                service.execute('refresh_saved',self.request(service))
                self.assertEqual(len(self.rows(path)),len(before)+1)
                info = service.snapshot()['refreshSaved']
                self.assertEqual((info['total'],info['updated'],info['unchanged'],info['failed']),(2,1,1,0))
                self.assertFalse(info['active'])
                with closing(sqlite3.connect(path)) as db:
                    self.assertEqual(list(db.execute("SELECT * FROM jobs WHERE state!='Guardado'")),pending)
                self.assertEqual({p:p.read_bytes() for p in csvs},csvs)
                # El nombre incorpora el identificador de fuente para evitar colisiones.
                backups = list((self.root/'data/backups/refresh_saved').rglob('*-'+path.name))
                self.assertTrue(backups)
                self.assertEqual(self.rows(backups[-1]),before)
                after = self.rows(path)
                service.execute('refresh_saved',self.request(service))
                self.assertEqual(self.rows(path),after)
                self.assertEqual(service.snapshot()['refreshSaved']['unchanged'],2)

    def test_invalid_download_preserves_saved_rows_and_states(self):
        service,path = self.prepare('duas')
        before = self.rows(path)
        original = FixturePortal.response
        def response(portal,path,query,post,form):
            if portal.refresh_details and path != '/hcicgmic.aspx' and query.get('n')==['1']:
                return '<html>Incompleta</html>','text/html'
            return original(portal,path,query,post,form)
        with patch.object(FixturePortal,'response',response):
            service.execute('refresh_saved',self.request(service))
        self.assertEqual(self.rows(path),before)
        self.assertEqual(service.snapshot()['refreshSaved']['failed'],1)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM jobs WHERE state='Guardado'").fetchone()[0],2)

    def test_stale_selection_rejected_without_modifying_sqlite(self):
        service,path = self.prepare('conocimientos')
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        for change in (dict(recordId='otro'),dict(month=10),dict(modes=['aereo'])):
            with self.assertRaises(ValueError):
                service.execute('refresh_saved',dict(self.request(service),**change))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_cancellation_before_apply_does_not_modify_sources(self):
        service,path = self.prepare('duas')
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        def notify(event):
            if event['stage']=='done':
                raise asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(refresh_saved(self.root,service.active(),'duas',['maritimo'],2,notify,True))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_failed_insert_rolls_back_all_old_rows(self):
        service,path = self.prepare('conocimientos')
        before = self.rows(path)
        mid = before[0][0]
        old = [json.loads(r[2]) for r in before if r[0]==mid]
        target = dict(flow='conocimientos',manifest=mid,hashes=packed(fingerprints(old,'conocimientos',mid)))
        # Duplicar secuencia invalida la inserción después del DELETE; debe revertirlo.
        bad = [old[0],old[0]]
        observation = dict(rows=packed(bad),stats=json.dumps(dict(kept=2,pages=1,read=2)),new_count=2,checked=now())
        with closing(sqlite3.connect(path)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                apply_manifest(db,target,observation,'test')
        self.assertEqual(self.rows(path),before)

    def test_auxiliary_receipt_failure_does_not_abort_confirmed_updates(self):
        service,path = self.prepare('duas')
        before = len(self.rows(path))
        with patch('chc_runtime.manifest_service.write_json',side_effect=OSError('recibo bloqueado')):
            result = asyncio.run(refresh_saved(self.root,service.active(),'duas',['maritimo'],2,lambda event:None,True))
        self.assertEqual(result['updated'],1)
        self.assertEqual(result['failed'],0)
        self.assertIn('recibo bloqueado',result['receiptError'])
        self.assertEqual(len(self.rows(path)),before+1)


if __name__=='__main__':unittest.main()
