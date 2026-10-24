"""Referencias aisladas y portal local: nunca toca los lotes del usuario."""
import asyncio
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from chc_runtime.manifest_refresh_audit import (freeze, open_audit, report, run,
                                               compare, unpacked, fingerprints, differences)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'bots/manifiestos/src'))
from chc_runtime.manifest_fixture import FixturePortal


class RefreshAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'bot'
        self.audit = Path(self.temp.name) / 'experiment/reference.sqlite3'
        self.spec = dict(year=2026, month=10, start='2026-10-01', end='2026-10-31')
        self.mid = '1-0-20260001-P027-01/10/26'
        self.empty = '1-0-20260002-P027-01/10/26'
        self.new = '1-0-20260003-P027-01/10/26'
        self.sources = []
        for flow in ('conocimientos', 'duas'):
            p = self.root / 'data/jobs' / flow / 'batch/test.sqlite3'
            p.parent.mkdir(parents=True)
            scope = dict(mode='maritimo', year=2026, month=10, desde=self.spec['start'],
                         hasta=self.spec['end'], courier=None)
            if flow == 'duas':
                scope['flow'] = flow
            with closing(sqlite3.connect(p)) as db:
                db.executescript('''CREATE TABLE metadata(scope TEXT);
                    CREATE TABLE jobs(id TEXT,ordinal INTEGER,updated TEXT,kept_count INTEGER,state TEXT);
                    CREATE TABLE manifests(id TEXT,stats TEXT);
                    CREATE TABLE rows(manifest TEXT,sequence INTEGER,data TEXT);''')
                db.execute('INSERT INTO metadata VALUES (?)', (json.dumps(scope),))
                for n, mid, state in ((1,self.mid,'Guardado'), (2,self.empty,'Guardado'), (3,self.new,'Pendiente')):
                    rows = [self.knowledge_row()] if n == 1 and flow == 'conocimientos' else []
                    db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (mid,n,'2026-10-23',len(rows),state))
                    if state == 'Guardado':
                        db.execute('INSERT INTO manifests VALUES (?,?)', (mid,json.dumps(dict(kept=len(rows),seconds=2))))
                    for i, row in enumerate(rows):
                        db.execute('INSERT INTO rows VALUES (?,?,?)', (mid,i,json.dumps(row)))
                db.commit()
            self.sources.append(p)
            session = self.root / 'data/workbench' / flow / 'session.json'
            session.parent.mkdir(parents=True)
            session.write_text(json.dumps(dict(history=[dict(id='batch',spec=self.spec,databases=[str(p)])])),encoding='utf-8')
        self.hashes = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.sources}

    def knowledge_row(self):
        return [self.mid,'1','00001234567890123456789','N','','HWB','00123','Empresa','188AJU','','','840MIA','','CER','']

    def capture(self):
        return freeze(self.root, self.audit, 2026, 10, 'maritimo')

    def target(self, db, flow='conocimientos', mid=None):
        return db.execute('''SELECT t.*,s.flow FROM targets t JOIN sources s ON s.id=t.source
            WHERE s.flow=? AND t.manifest=?''', (flow, mid or self.mid)).fetchone()

    def assert_sources_unchanged(self):
        self.assertEqual(self.hashes,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.sources})

    def test_freeze_only_confirmed_and_refuses_overwrite(self):
        value = self.capture()
        self.assertEqual(value['totals'], {'pendiente':4})
        self.assertEqual(sum(g['old_rows'] for g in value['groups']),1)
        self.assertNotIn(self.new,[r['manifest'] for r in value['manifests']])
        before = self.audit.read_bytes()
        with self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual(self.audit.read_bytes(),before)
        self.assert_sources_unchanged()

    def test_multiset_duplicates_order_and_equal_count_change(self):
        self.capture()
        row = self.knowledge_row()
        with closing(open_audit(self.audit)) as db:
            target = self.target(db)
            compare(db,target,[row,row],dict(kept=2),1)
            first = report(self.audit)['manifests'][0]
            self.assertEqual((first['status'],first['added'],first['removed']),('aumento',1,0))
            self.assertEqual(differences(self.audit)[0]['fresh_versions'],[row])
            changed = list(row)
            changed[2] = '0000002'
            compare(db,target,[changed],dict(kept=1),1)
            result = report(self.audit)['manifests'][0]
            self.assertEqual((result['status'],result['added'],result['removed']),('cambio',1,1))
            detail = differences(self.audit)[0]
            self.assertEqual(detail['fresh_versions'],[changed])
            self.assertEqual(detail['removed_versions'],1)
            compare(db,target,[],dict(kept=0),1)
            self.assertEqual(report(self.audit)['manifests'][0]['status'],'disminucion')
            compare(db,target,[row],dict(kept=1),1)
            self.assertEqual(report(self.audit)['manifests'][0]['status'],'sin_cambios')
            self.assertEqual(fingerprints([row,changed,row],'conocimientos',self.mid),
                             fingerprints([changed,row,row],'conocimientos',self.mid))
        self.assert_sources_unchanged()

    def test_incomplete_or_wrong_identity_cannot_confirm(self):
        self.capture()
        with closing(open_audit(self.audit)) as db:
            target = self.target(db)
            for rows, stats in (([['bad']],dict(kept=1)), ([self.knowledge_row()],dict(kept=2))):
                with self.assertRaises(ValueError):
                    compare(db,target,rows,stats,1)
            self.assertEqual(db.execute('SELECT count(*) FROM observations').fetchone()[0],0)

    def test_local_portal_fresh_pages_no_new_manifest_and_resume(self):
        self.capture()
        requests = []
        details = []
        def factory(scraper, source):
            portal = FixturePortal('maritimo',self.spec)
            original = portal.response
            def response(path,query,post,form):
                if path != '/hcicgmic.aspx':
                    details.append(query['id'][0])
                return original(path,query,post,form)
            portal.response = response
            scraper.URL = portal.url
            requests.append(portal.requests)
            return portal
        value = asyncio.run(run(self.audit,workers=2,fixture_factory=factory))
        self.assertEqual(value['totals'],{'aumento':2,'sin_cambios':2})
        self.assertEqual(sum(r['delta'] for r in value['manifests']),3)
        self.assertNotIn(self.new,details)
        self.assertEqual(set(details),{self.mid,self.empty})
        self.assertTrue(any(path=='/hcgcons.aspx' and post for path,post in requests[0]))
        with closing(open_audit(self.audit)) as db:
            row = db.execute('SELECT rows FROM observations o JOIN targets t ON t.id=o.target WHERE t.manifest=? LIMIT 1',
                             (self.mid,)).fetchone()
            self.assertEqual(len(unpacked(row[0])),3)
        before = len(requests)
        repeated = asyncio.run(run(self.audit,fixture_factory=factory))
        self.assertEqual(before,len(requests))
        self.assertEqual(repeated['totals'],value['totals'])
        self.assert_sources_unchanged()

    def test_cancellation_keeps_reference_and_does_not_confirm_partial(self):
        self.capture()
        entered = None
        async def slow(*args, **kwargs):
            entered.set()
            await asyncio.sleep(30)
            raise AssertionError('Una cancelación no debe confirmar filas después')
        def factory(scraper, source):
            portal = FixturePortal('maritimo',self.spec)
            scraper.URL = portal.url
            return portal
        async def cancel():
            nonlocal entered
            entered = asyncio.Event()
            task = asyncio.create_task(run(self.audit,fixture_factory=factory))
            await asyncio.wait_for(entered.wait(),10)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task,10)
        with patch('conocimientos.extract_table',slow):
            asyncio.run(cancel())
        value = report(self.audit)
        self.assertEqual(value['totals'],{'pendiente':4})
        self.assert_sources_unchanged()

    def test_missing_and_invalid_are_not_zero_and_can_retry(self):
        self.capture()
        requests = []
        def factory(scraper, source):
            portal = FixturePortal('maritimo',self.spec)
            original_main, original_response = portal.main, portal.response
            def main():
                grid, rows = original_main()
                # El manifiesto vacío desaparece; el resto no se incorpora a la cohorte.
                rows = [rows[0],rows[2]]
                return dict(GridName='Grid1',Count=2,**{'0':grid['0'],'1':grid['2']}), rows
            def response(path,query,post,form):
                if path != '/hcicgmic.aspx':
                    return '<html>Respuesta incompleta</html>','text/html'
                return original_response(path,query,post,form)
            portal.main, portal.response = main, response
            scraper.URL = portal.url
            requests.append(portal.requests)
            return portal
        value = asyncio.run(run(self.audit,fixture_factory=factory))
        self.assertEqual(value['totals'],{'error':2,'sin_enlace':2})
        self.assertTrue(all(r['new_count'] is None for r in value['manifests']))
        asyncio.run(run(self.audit,retry_errors=True,fixture_factory=factory))
        self.assertEqual(len(requests),4)
        self.assert_sources_unchanged()


if __name__ == '__main__':
    unittest.main()
