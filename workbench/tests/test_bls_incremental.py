"""Conocimientos ampliado → mismo lote BLs y los mismos CSV por mes/modalidad."""
from contextlib import closing
import csv
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until
from batch_bridge import BatchBridge

ROOT=Path(__file__).resolve().parents[2]


def add_source(root,tag,mode='maritimo',month=9,number='20260001',empty=False):
    code=('import sys; from pathlib import Path; '
          "sys.path.insert(0,str(Path('bots/manifiestos/src').resolve())); "
          'from chc_runtime.knowledge_fixture import create; '
          'create(Path(sys.argv[1]),sys.argv[2],mode=sys.argv[3],month=int(sys.argv[4]),number=sys.argv[5],rows=sys.argv[6]=="1")')
    subprocess.run([str(ROOT/'bots/manifiestos/.venv/Scripts/python.exe'),'-c',code,str(root),tag,mode,str(month),number,'0' if empty else '1'],
                   cwd=ROOT,check=True)


class IncrementalConnectionTests(unittest.TestCase):
    def test_growing_same_modes_and_month_keeps_one_batch_one_database_and_existing_csvs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=root/'manifiestos'
            add_source(sources,'sea');add_source(sources,'air',mode='aereo')
            bridge=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=sources,offline_fixture=True)
            config=dict(inputMode='knowledge',knowledgePeriods=['2026-09|maritimo','2026-09|aereo'],workers=1,
                        headless=True,timeout=5,max_retries=1,name='')
            def run():
                self.assertTrue(bridge.command('run',{'config':config}))
                wait_until(lambda:not bridge.busy,timeout=20000)
                self.assertFalse(bridge.error,bridge.error)
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                run();identity=bridge.activeId
                self.assertFalse(list((root/'bls').rglob('*.csv')))
                bridge.command('export',{});wait_until(lambda:not bridge.busy)
                self.assertFalse(bridge.error,bridge.error)
                database=next((root/'bls/data/jobs/bls').glob('**/SQLite/bls.sqlite3'))
                with closing(sqlite3.connect(database)) as db:
                    saved=db.execute('SELECT * FROM jobs ORDER BY ordinal').fetchall()
                    signature=db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0]
                public=list((root/'bls/resultados/BLS').rglob('*.CSV'))
                self.assertEqual(len(public),2)
                # Simular exactamente el progreso anterior al adaptador y reabrirlo.
                bridge.shutdown();wait_until(lambda:bridge.isClosed)
                index=root/'bls/data/workbench/bls/session.json'
                saved_index=json.loads(index.read_text(encoding='utf-8'))
                for record in saved_index['history']:
                    for field in ('knowledgeFamily','knowledgeAnchor','knowledgeScope'):record.pop(field,None)
                index.write_text(json.dumps(saved_index),encoding='utf-8')
                with closing(sqlite3.connect(database)) as db:
                    db.execute("DELETE FROM metadata WHERE key LIKE 'workbench_bls_%'")
                    db.execute('DROP TABLE workbench_bls_queries');db.execute('DROP TABLE workbench_bls_query_jobs');db.commit()
                bridge=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=sources,offline_fixture=True)
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                add_source(sources,'sea-new',number='20260002')
                run()
                self.assertEqual(bridge.activeId,identity)
                self.assertEqual(len(bridge.history),1)
                self.assertEqual(len(list((root/'bls/data/jobs/bls').glob('**/SQLite/bls.sqlite3'))),1)
                bridge.command('export',{});wait_until(lambda:not bridge.busy)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual((bridge.summary['total'],bridge.summary['succeeded'],bridge.summary['rows']),(3,3,3))
                self.assertEqual(set((root/'bls/resultados/BLS').rglob('*.CSV')),set(public))
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('SELECT * FROM jobs WHERE ordinal<=2 ORDER BY ordinal').fetchall(),saved)
                    self.assertEqual(db.execute('SELECT attempts FROM jobs ORDER BY ordinal').fetchall(),[(1,),(1,),(1,)])
                    self.assertEqual(db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0],signature)
                    self.assertEqual(db.execute('SELECT added FROM workbench_bls_queries ORDER BY rowid').fetchall(),[(1,)])
                for path in public:
                    with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
                    self.assertEqual(len(rows)-1,2 if 'MARITIMO' in path.name else 1)
                run()
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('SELECT sum(attempts) FROM jobs').fetchone()[0],3)
                self.assertEqual(len(bridge.history),1)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)

    def test_new_empty_snapshot_preserves_existing_batch_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=root/'manifiestos'
            add_source(sources,'sea')
            bridge=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=sources,offline_fixture=True)
            config=dict(inputMode='knowledge',knowledgePeriods=['2026-09|maritimo'],workers=1,headless=True,timeout=5,max_retries=1,name='')
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                bridge.command('run',{'config':config});wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                identity=bridge.activeId
                # Sustituir solo la fuente temporal por un rango terminado sin BLs.
                for path in sources.glob('data/jobs/**/*.sqlite3'):
                    self.assertTrue(path.resolve().is_relative_to(sources.resolve()));path.unlink()
                add_source(sources,'empty',empty=True)
                bridge.command('run',{'config':config});wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.activeId,identity)
                self.assertEqual((bridge.summary['succeeded'],bridge.summary['rows']),(1,1))
                self.assertIn('anteriores conservados',bridge.status)
                self.assertEqual(len(bridge.history),1)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)

    def test_a_different_month_or_mode_never_inherits_completed_bls(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=root/'manifiestos'
            add_source(sources,'sea');add_source(sources,'air',mode='aereo');add_source(sources,'august',mode='aereo',month=8)
            bridge=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=sources,offline_fixture=True)
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                ids=[]
                for period in ('2026-09|maritimo','2026-09|aereo','2026-08|aereo'):
                    config=dict(inputMode='knowledge',knowledgePeriods=[period],workers=1,headless=True,timeout=5,max_retries=1,name='')
                    bridge.command('run',{'config':config});wait_until(lambda:not bridge.busy,timeout=15000)
                    self.assertFalse(bridge.error,bridge.error)
                    ids.append(bridge.activeId)
                    self.assertEqual((bridge.summary['total'],bridge.summary['succeeded']),(1,1))
                self.assertEqual(len(set(ids)),3)
                self.assertEqual(len(bridge.history),3)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)


if __name__=='__main__':unittest.main()
