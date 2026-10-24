"""Preparación diaria: mismo presupuesto/resultados, sin escanear intentos por DUA."""
import json
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from chc_runtime.daily import DailyJobStore
from chc_runtime.job_store import JobStore


class DailyPreparationTests(unittest.TestCase):
    def test_same_budget_summary_and_exports_with_linear_history_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'jobs.sqlite3'
            store=JobStore(path)
            names=[f'001-2026-{i:06d}' for i in range(12000)]
            scope=names[9000:11000]
            with store.transaction() as db:
                db.executemany('INSERT INTO jobs(id,dua,status,attempts,result) VALUES (?,?,?,?,?)',
                    [(d,d,'succeeded' if i%4==0 else 'pending',i%5,
                      json.dumps({'numero_del_dua':d}) if i%4==0 else None) for i,d in enumerate(names)])
                db.executemany('INSERT INTO attempts(job_id,outcome) VALUES (?,?)',
                    [(d,'retry' if n%3 else 'interrupted') for i,d in enumerate(names) for n in range(i%5)])
                db.execute('CREATE TABLE daily_automatic_attempts(job_id TEXT PRIMARY KEY,used INTEGER)')
                db.execute('INSERT INTO daily_automatic_attempts VALUES (?,0)',(scope[1],))
            before=list(store.db.iterdump())
            store.db.execute('CREATE TEMP TABLE daily_scope(dua TEXT PRIMARY KEY)')
            store.db.executemany('INSERT INTO daily_scope VALUES (?)',[(d,) for d in scope])
            store.db.commit()
            started=time.perf_counter()
            old=store.db.execute('''SELECT j.id,MIN(3,(SELECT count(*) FROM attempts a
                WHERE a.job_id=j.id AND a.outcome='retry')) FROM jobs j
                WHERE EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=j.dua)''').fetchall()
            expected=dict(old);expected[scope[1]]=0
            previous=time.perf_counter()-started
            old_counts=dict(store.db.execute('''SELECT status,count(*) FROM jobs
                WHERE EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua) GROUP BY status'''))
            old_attempts=store.db.execute('''SELECT sum(attempts) FROM jobs
                WHERE EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua)''').fetchone()[0]
            old_ready=sum(expected[row[0]]<3 for row in store.db.execute('''SELECT id FROM jobs
                WHERE status IN ('pending','retry') AND EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua)'''))
            old_summary={**{s:old_counts.get(s,0) for s in ('pending','running','retry','succeeded','invalid','empty')},
                'total':sum(old_counts.values()),'attempts':old_attempts,'source_rows':len(scope),
                'active_duas':[],'automatic_ready':old_ready}
            # El export diario anterior también incluía el resumen acotado al día.
            store.summary=lambda:old_summary
            paths={key:str(root/(key+'.txt')) for key in ('output_csv','processed_log','failed_duas','pending_json')}
            store.export(paths,['numero_del_dua'])
            exports={key:Path(value).read_bytes() for key,value in paths.items()}
            store.close()
            started=time.perf_counter();store=DailyJobStore(path,scope,automatic=True)
            elapsed=time.perf_counter()-started
            try:
                self.assertEqual(dict(store.db.execute('SELECT job_id,used FROM daily_automatic_attempts')),expected)
                summary=store.summary()
                self.assertEqual(summary,old_summary)
                self.assertEqual(summary['attempts'],old_attempts)
                for state,count in old_counts.items():self.assertEqual(summary[state],count)
                self.assertEqual(summary['total'],len(scope))
                self.assertEqual(summary['source_rows'],len(scope))
                # Solo se agregan presupuestos; jobs/attempts/resultados permanecen idénticos.
                after=list(store.db.iterdump())
                stable=lambda rows:[r for r in rows if 'daily_automatic_attempts' not in r]
                self.assertEqual(stable(before),stable(after))
                store.export(paths,['numero_del_dua'])
                for key,value in paths.items():
                    self.assertEqual(hashlib.sha256(exports[key]).digest(),hashlib.sha256(Path(value).read_bytes()).digest(),key)
                # Orden/reservas fuera del día permanecen intactos.
                store.begin_run();job=store.claim(1)
                self.assertIn(job['dua'],scope)
                self.assertLess(expected[job['id']],3)
                print(f'Preparación 2.000 DUAs/24.000 intentos: anterior={previous:.3f}s nueva={elapsed:.3f}s',flush=True)
            finally:store.close()

    def test_constructor_failure_closes_connection_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'jobs.sqlite3'
            store=JobStore(path);store.close()
            def broken_input():
                yield '001-2026-000001'
                raise ValueError('interrumpido')
            closed=[]
            original=JobStore.close
            def close(store):closed.append(store.db);original(store)
            with patch.object(JobStore,'close',close):
                with self.assertRaisesRegex(ValueError,'interrumpido'):
                    DailyJobStore(path,broken_input(),automatic=True)
            self.assertEqual(len(closed),1)
            with self.assertRaises(sqlite3.ProgrammingError):closed[0].execute('SELECT 1')
            store=DailyJobStore(path,['001-2026-000001'],automatic=True);store.close()


if __name__=='__main__':unittest.main()
