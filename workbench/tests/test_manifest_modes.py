"""Modalidades independientes en la observación, sin escribir en las bases."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Event
import time
import tempfile
import unittest

from chc_runtime.manifest_service import BatchService
from chc_runtime.manual_review_data import load_selection


class ManifestModesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = BatchService(self.root,'tabla',lambda *a,**k:None,Event())
        self.record = dict(id='test',name='octubre26',config={},summary={},databases=[],
                           work=str(self.root/'data/jobs/tabla/test'))
        self.service.index.update(history=[self.record],active='test')

    def database(self,mode,jobs,rows=0):
        path = Path(self.record['work'])/'SQLite'/mode/'results.sqlite3'
        path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(path)) as db:
            db.executescript('''CREATE TABLE metadata(scope);
                CREATE TABLE jobs(id,ordinal,state,attempts,kept_count,error);
                CREATE TABLE rows(value TEXT);''')
            db.execute('INSERT INTO metadata VALUES (?)',(json.dumps(dict(mode=mode,year=2026,month=10)),))
            db.executemany('INSERT INTO jobs VALUES (?,?,?,?,?,?)',jobs)
            db.executemany('INSERT INTO rows VALUES (?)',[('000001',)]*rows)
            db.commit()
        self.record['databases'].append(str(path))
        return path

    def test_two_listados_keep_their_own_rows_filters_and_readonly_review(self):
        sea = self.database('maritimo',[('listado',1,'Guardado',1,1833,'')],1833)
        air = self.database('aereo',[('listado',1,'Guardado',2,257,'')],257)
        before = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (sea,air)}
        self.service.inspect()
        snapshot = self.service.snapshot()
        self.assertEqual([(j['mode'],j['id'],j['rows']) for j in snapshot['jobs']],
                         [('maritimo','listado',1833),('aereo','listado',257)])
        self.assertEqual(snapshot['summary']['rows'],2090)
        self.assertEqual(snapshot['summary']['succeeded'],2)
        self.assertEqual([(s['label'],s['rows']) for s in snapshot['modeSummaries']],
                         [('Marítimo',1833),('Aéreo',257)])
        result = self.service.execute('view',dict(mode='aereo',search='',offset=0))['snapshot']
        self.assertEqual([j['mode'] for j in result['jobs']],['aereo'])
        self.assertEqual(result['summary'],snapshot['summary'])
        self.assertEqual(result['modeSummaries'],snapshot['modeSummaries'])
        self.service.save()
        request = dict(flow='tabla',recordId='test',jobId='listado',ordinal=1)
        with self.assertRaises(ValueError):load_selection(self.root,'manifiestos',request)
        selected = load_selection(self.root,'manifiestos',{**request,'database':str(air)})
        self.assertEqual(selected['scope']['mode'],'aereo')
        external = self.database('terrestre',[('listado',1,'Guardado',1,0,'')])
        # El archivo está dentro del lote, pero no figura en el índice guardado.
        with self.assertRaises(ValueError):
            load_selection(self.root,'manifiestos',{**request,'database':str(external)})
        self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before},before)
        reopened = BatchService(self.root,'tabla',lambda *a,**k:None,Event())
        reopened.inspect()
        self.assertEqual(len(reopened.snapshot()['jobs']),2)

    def test_live_same_id_does_not_overwrite_other_mode_or_double_rows(self):
        self.service.processing = True
        self.service._last_save = time.monotonic()
        def event(mode,state,kept):
            return dict(mode=mode,database=str(self.root/(mode+'.sqlite3')),
                progress=dict(selected=1,saved=int(state=='Guardado'),pending=0,
                              active=int(state=='Descargando'),excluded=0),
                job=dict(id='listado',ordinal=1,state=state,attempts=1,kept=kept))
        self.service.progress(event('maritimo','Descargando',0))
        self.service.progress(event('aereo','Descargando',0))
        self.assertEqual(len(self.service.snapshot()['activeJobs']),2)
        self.assertEqual(self.service.snapshot()['summary']['running'],2)
        self.service.progress(event('maritimo','Guardado',1833))
        self.service.progress(event('aereo','Guardado',257))
        self.service.progress(event('aereo','Guardado',257))
        snapshot = self.service.snapshot()
        self.assertEqual(len(snapshot['jobs']),2)
        self.assertEqual(snapshot['summary']['rows'],2090)
        self.assertEqual(snapshot['summary']['succeeded'],2)
        self.service.progress(dict(phase='waiting',message='Esperando respuesta'))
        self.assertEqual(self.service.snapshot()['summary'],snapshot['summary'])
        self.service.progress(event('maritimo','Descargando',0))
        self.service._view_mode = 'aereo'
        snapshot = self.service.snapshot()
        self.assertEqual([j['mode'] for j in snapshot['jobs']],['aereo'])
        self.assertEqual([j['mode'] for j in snapshot['activeJobs']],['maritimo'])

    def test_combined_pagination_has_no_missing_rows_and_active_survives_filter(self):
        jobs = [(str(i),i,'Guardado',1,1,'') for i in range(300)]
        self.database('maritimo',jobs,300)
        self.database('aereo',jobs[:10]+[('listado',1000,'Descargando',1,0,'')],10)
        self.service.inspect()
        first = self.service.snapshot()['jobs']
        self.service.execute('view',dict(offset=200))
        second = self.service.snapshot()['jobs']
        self.assertEqual(len(first),200)
        self.assertEqual(len(second),111)
        keys = [(j['database'],j['id']) for j in first+second]
        self.assertEqual(len(set(keys)),311)
        self.service.processing = True
        self.service.execute('view',dict(mode='maritimo',search='299',offset=0))
        snapshot = self.service.snapshot()
        self.assertEqual([j['id'] for j in snapshot['jobs']],['299'])
        self.assertEqual([(j['mode'],j['id']) for j in snapshot['activeJobs']],[('aereo','listado')])

    def test_interrupted_reservations_do_not_hide_the_first_page(self):
        jobs=[(str(i),i,'Guardado' if i<700 else 'Descargando',1,0,'') for i in range(1000)]
        self.database('maritimo',jobs)
        self.service.inspect()
        snapshot=self.service.snapshot()
        self.assertEqual([j['ordinal'] for j in snapshot['jobs']],list(range(200)))
        self.assertEqual(snapshot['summary']['pending'],300)
        self.assertEqual(snapshot['summary']['running'],0)
        self.assertFalse(snapshot['activeJobs'])
        self.service.processing=True
        self.service.inspect()
        snapshot=self.service.snapshot()
        self.assertEqual(len(snapshot['activeJobs']),300)
        self.assertTrue(all(j['state']=='Descargando' for j in snapshot['jobs']))


if __name__=='__main__':unittest.main()
