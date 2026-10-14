"""Revisiones aisladas: navegación local, error visible y progreso intacto."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until
from manual_review import ManualReview

ROOT=Path(__file__).resolve().parents[2]
SEED='''
from pathlib import Path
import json,sys,sqlite3
from contextlib import closing
repo,root,module=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
sys.path.insert(0,str(repo))
from chc_runtime.profiles import load_profile
from chc_runtime.catalog import TableCatalog
profile=load_profile(module)
catalog=TableCatalog(root/'data/queues',store_factory=profile['store'])
p=catalog.folder/'test.sqlite3';store=profile['store'](p)
store.import_values(['001-2026-000001','001-2026-999997']);store.close()
with catalog.connection() as db:
 db.execute("INSERT INTO saved_tables(id,name,name_key,filename,source_path,source_sheet,output_name) VALUES ('test','Prueba','prueba','test.sqlite3','base.xlsx','Base','Prueba')")
(root/'config').mkdir()
(root/'config/machine.json').write_text(json.dumps({'timeout':5,'max_retries':3,'cant_hilos':2}),encoding='utf-8')
'''


class ManualReviewTests(unittest.TestCase):
    def test_close_during_start_cannot_launch_a_late_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            subprocess.run([str(ROOT/'bots/talon/.venv/Scripts/python.exe'),'-c',SEED,str(ROOT),str(root),'talon'],check=True,cwd=ROOT)
            review=ManualReview('talon',root,fixture=True)
            try:
                self.assertTrue(review.open({'tableId':'test','jobId':'001-2026-999997'}))
                review.stop()
                wait_until(lambda:review.isClosed,timeout=15000)
                self.assertFalse(review.error,review.error)
                self.assertFalse(list(root.glob('data/manual_reviews/*/report.json')))
            finally:review.shutdown()

    def test_bls_and_manifest_reviews_use_original_identity_and_leave_data_untouched(self):
        for module,flow in [('bls','bls'),('manifiestos','conocimientos'),('manifiestos','duas'),('manifiestos','movimientos'),('manifiestos','contenedores')]:
            with self.subTest(module=module,flow=flow),tempfile.TemporaryDirectory() as folder:
                import sqlite3
                from contextlib import closing
                root=Path(folder);record_folder=root/'data/jobs'/flow/'test'
                database=record_folder/'BLS/scope/SQLite/bls.sqlite3' if module=='bls' else record_folder/'progress.sqlite3'
                database.parent.mkdir(parents=True)
                mid='1-0-00001-A01-01/09/26' if module=='bls' else '1-0-20260001-P027-01/09/26'
                with closing(sqlite3.connect(database)) as db:
                    if module=='bls':
                        db.execute('CREATE TABLE jobs(ordinal,payload,state)')
                        payload={'IDManifiesto':mid,'Secuencia Tica':'1','BL original':'00001234567890123456789','Fecha Manifiesto':'01/09/2026','Mes':'2026-09'}
                        db.execute('INSERT INTO jobs VALUES (1,?,\'Pendiente\')',(json.dumps(payload),))
                    else:
                        db.execute('CREATE TABLE jobs(id,state)');db.execute('CREATE TABLE metadata(scope)')
                        db.execute('INSERT INTO jobs VALUES (?,\'Pendiente\')',(mid,))
                        db.execute('INSERT INTO metadata VALUES (?)',(json.dumps({'flow':flow,'mode':'maritimo','year':2026,'month':9}),))
                    db.commit()
                index=root/'data/workbench'/flow/'session.json';index.parent.mkdir(parents=True)
                index.write_text(json.dumps({'active':'test','history':[{'id':'test','config':{'timeout':5},'databases':[str(database)]}]}),encoding='utf-8')
                before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (database,index)}
                review=ManualReview(module,root,fixture=True)
                try:
                    self.assertTrue(review.open({'recordId':'test','jobId':mid,'ordinal':1,'flow':flow}))
                    wait_until(lambda:review.status!='Abriendo revisión en TICA…',timeout=25000)
                    self.assertFalse(review.error,review.error+' '+review.stderr)
                    self.assertTrue(review.running)
                    self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before},before)
                finally:
                    review.shutdown();wait_until(lambda:review.isClosed,timeout=15000)

    def test_four_dua_screens_use_own_profile_without_changing_queue(self):
        for module in ('detalles','duas_transito','talon','xmovimientos'):
            with self.subTest(module=module),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                subprocess.run([str(ROOT/'bots'/module/'.venv/Scripts/python.exe'),'-c',SEED,str(ROOT),str(root),module],check=True,cwd=ROOT)
                files=list((root/'data/queues').glob('*.sqlite3'))
                before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
                review=ManualReview(module,root,fixture=True)
                try:
                    dua='001-2026-999997' if module in ('talon','xmovimientos') else '001-2026-000001'
                    self.assertTrue(review.open({'tableId':'test','jobId':dua}))
                    wait_until(lambda:review.status!='Abriendo revisión en TICA…',timeout=30000)
                    self.assertFalse(review.error,review.error+' '+review.stderr)
                    self.assertTrue(review.running)
                    self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},before)
                    report=json.loads(next(root.glob('data/manual_reviews/*/report.json')).read_text(encoding='utf-8'))
                    self.assertEqual(report['module'],module)
                    self.assertEqual(report['result']['outcome'],'empty_page' if module in ('talon','xmovimientos') else 'has_rows' if module=='duas_transito' else 'opened')
                finally:
                    review.shutdown();wait_until(lambda:review.isClosed,timeout=15000)

    def test_bad_selection_finishes_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as folder:
            review=ManualReview('talon',folder,fixture=True)
            try:
                self.assertTrue(review.open({'tableId':'missing','jobId':'001-2026-000001'}))
                wait_until(lambda:review.isClosed,timeout=15000)
                self.assertTrue(review.error)
                self.assertFalse((Path(folder)/'data/queues').exists())
            finally:review.shutdown()


if __name__=='__main__':unittest.main()
