"""Resumen de todo el lote BLs, sin escribir ni depender de la página visible."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Event
import tempfile
import unittest

from chc_runtime.manifest_service import BatchService


class BlsModesTests(unittest.TestCase):
    def test_entire_batch_counts_survive_search_pagination_and_reopen_readonly(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            service=BatchService(root,'bls',lambda *a,**k:None,Event())
            work=root/'data/jobs/bls/test'
            dbpath=work/'BLS/signature/SQLite/bls.sqlite3'
            dbpath.parent.mkdir(parents=True)
            with closing(sqlite3.connect(dbpath)) as db:
                db.executescript('''CREATE TABLE jobs(ordinal,payload,state,attempts,result_count,error);
                    CREATE TABLE results(value);''')
                jobs=[]
                for ordinal in range(1,306):
                    mode='1' if ordinal<=300 else '4'
                    state='Guardado' if ordinal<=302 else 'Descargando' if ordinal==303 else 'Pendiente' if ordinal==304 else 'Inválido'
                    rows=2 if state=='Guardado' and ordinal!=302 else 0
                    payload=json.dumps({'IDManifiesto':f'{mode}-1-000123-P001-13/10/26','BL original':f'{ordinal:09d}'})
                    jobs.append((ordinal,payload,state,1,rows,''))
                db.executemany('INSERT INTO jobs VALUES (?,?,?,?,?,?)',jobs)
                db.executemany('INSERT INTO results VALUES (?)',[('fila',)]*602)
                db.commit()
            digest=hashlib.sha256(dbpath.read_bytes()).digest()
            service.index.update(active='test',history=[dict(id='test',name='Prueba',work=str(work),summary={},databases=[])])
            service.inspect()
            snapshot=service.snapshot()
            sea,air=snapshot['modeSummaries']
            self.assertEqual((sea['total'],sea['succeeded'],sea['rows']),(300,300,600))
            self.assertEqual((air['total'],air['succeeded'],air['pending'],air['running'],air['invalid'],air['empty']),(5,2,2,0,1,1))
            self.assertEqual(len(snapshot['jobs']),200)
            service.inspect(search='000000305',offset=0)
            self.assertEqual(len(service.snapshot()['jobs']),1)
            self.assertEqual(service.snapshot()['modeSummaries'],snapshot['modeSummaries'])
            service.inspect(search='',offset=200)
            self.assertEqual(len(service.snapshot()['jobs']),105)
            self.assertEqual(service.snapshot()['modeSummaries'],snapshot['modeSummaries'])
            service.processing=True
            service.inspect()
            air=service.snapshot()['modeSummaries'][1]
            self.assertEqual((air['pending'],air['running']),(1,1))
            service.save()
            reopened=BatchService(root,'bls',lambda *a,**k:None,Event())
            reopened.inspect()
            self.assertEqual(reopened.snapshot()['modeSummaries'],snapshot['modeSummaries'])
            self.assertEqual(hashlib.sha256(dbpath.read_bytes()).digest(),digest)


if __name__=='__main__':unittest.main()
