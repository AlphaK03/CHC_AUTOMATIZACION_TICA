"""Comparación con la lectura anterior sobre los mismos SQLite, sin red."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from chc_runtime.worker import DetailsService
from chc_runtime.catalog import TableCatalog
from chc_runtime.job_store import JobStore


class LoadingSnapshotTests(unittest.TestCase):
    def test_same_data_same_analysis_for_four_profiles_and_no_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            catalog=TableCatalog(root/'queues')
            for name in ('octubre26','septiembre26'):
                store=JobStore(catalog.folder/(name+'.sqlite3'))
                with store.db:
                    store.db.executemany('INSERT INTO jobs(id,dua,status,attempts,result,error_kind) VALUES (?,?,?,?,?,?)',
                        [(str(i),f'001-2026-{i:06d}',('pending','running','retry','succeeded','invalid','empty')[i%6],
                          i%4,json.dumps({'numero_del_dua':f'001-2026-{i:06d}'}) if i%6==3 else None,
                          'NoMovimientosError' if i%6==2 else '') for i in range(18000)])
                    store.db.executemany('INSERT INTO source_rows VALUES (?,?,?,?)',
                        [('actual' if i%12<6 else 'anterior',i,str(i),str(i)) for i in range(18000)])
                    store._set_meta(store.db,'active_revisions',['actual'])
                    store._set_meta(store.db,'source_rows',18000)
                    store.db.execute('INSERT INTO retained_results VALUES (?,?)',('001-2025-000001','{}'))
                store.close()
                with catalog.connection() as db:
                    db.execute('INSERT INTO saved_tables(id,name,name_key,filename,source_path,source_sheet,output_name) VALUES (?,?,?,?,?,?,?)',
                        (name,name,name,name+'.sqlite3','','',name))
            hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in catalog.folder.glob('*.sqlite3')}
            for module in ('detalles','duas_transito','talon','xmovimientos'):
                service=DetailsService.__new__(DetailsService)
                service.catalog=catalog;service.active_id='octubre26';service.module_id=module
                service.root=root;service.Store=SimpleNamespace(supports_empty=module=='xmovimientos')
                service.machine={};service.session={};service.fields=[]
                service.daily=SimpleNamespace(snapshot=lambda:{'active':False,'days':[]})
                # Algoritmo anterior: todas las tablas y otra lectura de la activa.
                before=time.perf_counter()
                tables=catalog.list_tables()
                for table in tables:table['summary']=service.summary(table)
                active=service.summary(service.record())
                baseline_time=time.perf_counter()-before
                with patch.object(service,'summary',wraps=service.summary) as summaries:
                    before=time.perf_counter();snapshot=service.snapshot();elapsed=time.perf_counter()-before
                self.assertEqual(snapshot['tables'],tables,module)
                self.assertEqual(snapshot['summary'],active,module)
                self.assertEqual(snapshot['activeTable'],service.record())
                self.assertEqual(summaries.call_count,2)
                self.assertEqual(snapshot['summary']['invalid'],1500)
                print(f'{module}: anterior={baseline_time:.4f}s actual={elapsed:.4f}s lecturas={summaries.call_count}',flush=True)
            self.assertEqual(hashes,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in hashes})
            # Una nueva escritura es visible en la siguiente petición.
            store=JobStore(catalog.database(service.record()))
            with store.db:store.db.execute("UPDATE jobs SET attempts=attempts+1 WHERE id='0'")
            store.close()
            self.assertEqual(service.snapshot()['summary']['attempts'],active['attempts']+1)


if __name__=='__main__':unittest.main()
