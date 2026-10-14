"""Presentación del progreso BLs recuperado y actualización sin filas duplicadas."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest

from chc_runtime.manifest_service import BatchService


class BLSProgressTests(unittest.TestCase):
    def test_original_identifiers_search_and_live_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            service = BatchService(root, 'bls', lambda *args, **kwargs: None, Event())
            database = root/'batch/BLS/signature/SQLite/bls.sqlite3'
            database.parent.mkdir(parents=True)
            manifest = '1-0-00001-A01-01/09/26'
            bl = '00001234567890123456789'
            with closing(sqlite3.connect(database)) as db:
                db.executescript('''CREATE TABLE jobs (id TEXT, ordinal INTEGER, payload TEXT,
                    state TEXT, attempts INTEGER, result_count INTEGER, error TEXT);
                    CREATE TABLE results (value TEXT);
                    CREATE TABLE metadata (key TEXT, value TEXT);
                    INSERT INTO metadata VALUES ('signature','fixture');''')
                for ordinal in range(1, 4):
                    payload = json.dumps({'IDManifiesto':manifest, 'BL original':bl,
                                          'Secuencia Tica':str(ordinal)})
                    db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',
                               ('hash-'+str(ordinal),ordinal,payload,'Guardado' if ordinal==1 else 'Pendiente',
                                1 if ordinal==1 else 0,1 if ordinal==1 else 0,''))
                db.execute("INSERT INTO results VALUES ('dato confirmado')")
                db.commit()
            digest = hashlib.sha256(database.read_bytes()).hexdigest()
            service.index.update(active='batch', history=[{'id':'batch','name':'BLs septiembre',
                'work':str(root/'batch'), 'output':str(root/'resultados'), 'summary':{}}])
            service.inspect()
            jobs = service.snapshot()['jobs']
            self.assertEqual(len(jobs),3)
            self.assertEqual(jobs[0]['id'],manifest+' / '+bl)
            self.assertEqual(jobs[0]['bl'],bl)
            self.assertEqual(service.snapshot()['summary']['succeeded'],1)
            service.inspect(search=bl)
            self.assertEqual(len(service.snapshot()['jobs']),3)
            service.inspect(search='hash-')
            self.assertEqual(service.snapshot()['jobs'],[])
            service.inspect()
            service.processing = True
            service.progress({'phase':'prepare'})
            self.assertEqual(service.snapshot()['summary']['succeeded'],1)
            service.progress({'total':3,'saved':1,'pending':1,'running':1,'result_rows':1,
                'job':{'ordinal':3,'manifest':manifest,'bl':bl,'state':'Descargando','attempts':1,
                       'result_count':0,'error':''}})
            self.assertEqual(len(service._jobs),3)
            self.assertEqual(service.snapshot()['jobs'][0]['ordinal'],3)
            self.assertEqual(service.snapshot()['jobs'][0]['state'],'Descargando')
            self.assertEqual(service.snapshot()['jobs'][0]['id'],manifest+' / '+bl)
            service.progress({'total':3,'saved':1,'pending':1,'running':1,'result_rows':1,
                'job':{'ordinal':3,'manifest':manifest,'bl':bl,'state':'Descargando','attempts':1,
                       'result_count':0,'page':4,'checkpointPage':3,'collectedRows':6,'error':''}})
            self.assertEqual(service._jobs[3]['page'],4)
            self.assertEqual(service._jobs[3]['collectedRows'],6)
            service.progress({'total':3,'saved':1,'pending':2,'running':0,'result_rows':1,
                'job':{'ordinal':3,'manifest':manifest,'bl':bl,'state':'Pendiente','attempts':1,
                       'result_count':0,'error':'Detenido'}})
            self.assertEqual(service._jobs[3]['page'],3)
            self.assertEqual(service._jobs[3]['collectedRows'],6)
            self.assertEqual(service.snapshot()['summary']['rows'],1)
            # La reapertura recupera páginas sin convertir sus filas en éxitos.
            from chc_runtime.bls_pages import PageStore, DetailPage
            pages=PageStore(database.with_name('bls_pages.sqlite3'),'fixture')
            try:
                pages.save('hash-3',3,1,DetailPage({}, {},['campo'],[['001'],['002']],0,False))
                pages.save('hash-3',3,2,DetailPage({}, {},['campo'],[['003']],2,False))
            finally: pages.close()
            service.processing=False
            service.inspect()
            self.assertEqual(service._jobs[3]['page'],2)
            self.assertEqual(service._jobs[3]['collectedRows'],3)
            self.assertEqual(service._jobs[3]['rows'],0)
            self.assertEqual(service.snapshot()['summary']['succeeded'],1)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(),digest)


if __name__ == '__main__': unittest.main()
