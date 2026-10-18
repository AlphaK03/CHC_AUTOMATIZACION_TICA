"""Paginación y reanudación BLs con navegador y HTTP exclusivamente locales."""
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'bots/bls/src'))
import pandas as pd
from config_manager import DEFAULTS
from core.tica import TicaSession
from core.inputs import input_job
from playwright.async_api import async_playwright
from chc_runtime.bls_page_fixture import BLSPagePortal
from chc_runtime.bls_session import WorkbenchBLSProcessor, PagedTicaSession
from chc_runtime.bls_pages import PageStore


def frame():
    return pd.DataFrame([{'IDManifiesto':'1-0-00001-A01-01/09/26','Secuencia Tica':'1',
        'BL original':'00001234567890123456789','Fecha Manifiesto':'01/09/2026','Mes':'2026-09'}])


class BLSPagesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.pw=await async_playwright().start()
        self.browser=await self.pw.chromium.launch(headless=True)
        self.portal=BLSPagePortal(fail_offset=6)
        self.events=[]
        self.stop=Event()
        self.config={**DEFAULTS,'target_url':self.portal.url,'sheet_name':'BLS',
            'output_base_path':str(self.root),'cant_hilos':1,'max_retries':1,'timeout':5,
            'event_callback':self.events.append}

    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop()
        self.portal.close();self.temp.cleanup()

    async def run_bot(self, data=None):
        processor=WorkbenchBLSProcessor(dict(self.config),self.stop)
        return await processor.run_async(frame() if data is None else data,session_factory=lambda worker:
            TicaSession(self.browser,processor.config,processor.stats))

    def counts(self,database):
        with closing(sqlite3.connect(database)) as db:
            return db.execute('SELECT state,attempts,result_count FROM jobs').fetchone(),db.execute('SELECT count(*) FROM results').fetchone()[0]

    async def test_partial_pages_resume_from_anchor_and_keep_original_signature(self):
        first=await self.run_bot()
        self.assertEqual((first['saved'],first['pending'],first['result_rows']),(0,1,0))
        self.assertEqual(self.counts(first['database']),(('Pendiente',1,0),0))
        pages=Path(first['database']).with_name('bls_pages.sqlite3')
        with closing(sqlite3.connect(pages)) as db:
            self.assertEqual(db.execute('SELECT page,offset,count FROM pages ORDER BY page').fetchall(),
                             [(1,0,2),(2,2,2),(3,4,2)])
        updates=[e['job'] for e in self.events if e.get('job',{}).get('checkpointPage')]
        self.assertTrue(any(j['page']==4 and j['checkpointPage']==3 and j['collectedRows']==6 for j in updates))
        self.portal.fail_offset=None
        self.portal.offsets.clear()
        second=await self.run_bot()
        self.assertEqual(second['database'],first['database'])
        self.assertEqual(self.portal.offsets,[0,4,6])
        self.assertEqual(self.counts(second['database']),(('Guardado',2,7),7))
        self.assertEqual((second['saved'],second['result_rows']),(1,7))
        self.portal.offsets.clear()
        await self.run_bot()
        self.assertEqual(self.portal.offsets,[])
        self.assertEqual(self.counts(second['database']),(('Guardado',2,7),7))

    async def test_changed_anchor_keeps_partial_pages_and_never_confirms(self):
        first=await self.run_bot()
        self.portal.fail_offset=None
        self.portal.changed_offset=4
        second=await self.run_bot()
        self.assertEqual(self.counts(second['database']),(('Pendiente',2,0),0))
        pages=Path(first['database']).with_name('bls_pages.sqlite3')
        with closing(sqlite3.connect(pages)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*),SUM(count) FROM pages').fetchone(),(3,6))
        self.assertTrue(any('reanudación cambió' in e.get('job',{}).get('error','') for e in self.events))

    async def test_stop_preserves_verified_pages_and_reopens_without_duplicate_lines(self):
        self.portal.fail_offset=None
        def progress(event):
            self.events.append(event)
            if event.get('job',{}).get('checkpointPage')==2: self.stop.set()
        self.config['event_callback']=progress
        first=await self.run_bot()
        self.assertEqual(self.counts(first['database'])[1],0)
        self.stop.clear()
        self.config['event_callback']=self.events.append
        self.portal.offsets.clear()
        result=await self.run_bot()
        self.assertEqual(result['result_rows'],7)
        self.assertEqual(self.portal.offsets,[0,2,4,6])
        with closing(sqlite3.connect(result['database'])) as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT data FROM results ORDER BY position')]
        self.assertEqual([r[5] for r in rows],[f'{n:03d}' for n in range(1,8)])

    async def test_repeated_last_page_requires_confirmed_eof(self):
        self.portal.fail_offset=None
        self.portal.repeated_last=True
        result=await self.run_bot()
        self.assertEqual(result['result_rows'],6)
        with closing(sqlite3.connect(Path(result['database']).with_name('bls_pages.sqlite3'))) as db:
            self.assertEqual(db.execute('SELECT count(*),sum(count),max(eof) FROM pages').fetchone(),(3,6,1))

    async def test_suffix_manifest_resumes_verified_pages_and_preserves_full_identity(self):
        mid = '4-1-0002601287L-P001-13/10/26'
        self.portal.manifest = mid
        self.portal.search_get = True
        data = frame()
        data.loc[0, ['IDManifiesto', 'Fecha Manifiesto', 'Mes']] = [mid, '13/10/2026', '2026-10']
        first = await self.run_bot(data)
        self.assertEqual(self.counts(first['database']), (('Pendiente',1,0),0))
        self.portal.fail_offset = None
        self.portal.offsets.clear()
        second = await self.run_bot(data)
        self.assertEqual(first['database'], second['database'])
        self.assertEqual(self.portal.offsets, [0,4,6])
        self.assertEqual(self.counts(second['database']), (('Guardado',2,7),7))
        with closing(sqlite3.connect(second['database'])) as db:
            payload = json.loads(db.execute('SELECT payload FROM jobs').fetchone()[0])
            rows = [json.loads(r[0]) for r in db.execute('SELECT data FROM results')]
        self.assertEqual(payload['ID3'], '0002601287L')
        self.assertEqual(payload['IDManifiesto'], mid)
        self.assertTrue(all(row[-2:] == [mid, data.iloc[0]['BL original']] for row in rows))
        self.portal.offsets.clear()
        await self.run_bot(data)
        self.assertEqual(self.portal.offsets, [])
        self.assertEqual(self.counts(second['database']), (('Guardado',2,7),7))

    async def test_empty_bl_is_confirmed_with_one_verified_page(self):
        self.portal.fail_offset=None
        self.portal.empty=True
        result=await self.run_bot()
        self.assertEqual(self.counts(result['database']),(('Guardado',1,0),0))
        with closing(sqlite3.connect(Path(result['database']).with_name('bls_pages.sqlite3'))) as db:
            self.assertEqual(db.execute('SELECT page,count,eof FROM pages').fetchall(),[(1,0,1)])

    def empty_retry(self, database):
        backups = tempfile.TemporaryDirectory()
        self.addCleanup(backups.cleanup)
        self.config['workbench_empty_retry'] = {'database':str(database),'backups':backups.name}

    async def test_requery_empty_fetches_new_pages_and_keeps_the_old_empty_checkpoint(self):
        self.portal.empty = True
        first = await self.run_bot()
        self.empty_retry(first['database'])
        self.portal.empty = False
        self.portal.fail_offset = None
        self.portal.offsets.clear()
        second = await self.run_bot()
        self.assertEqual(second['database'],first['database'])
        self.assertEqual(self.portal.offsets,[0,2,4,6])
        self.assertEqual(self.counts(second['database']),(('Guardado',2,7),7))
        with closing(sqlite3.connect(Path(second['database']).with_name('bls_pages.sqlite3'))) as db:
            self.assertEqual(db.execute('SELECT count(*),sum(count) FROM pages').fetchone(),(5,7))
            self.assertEqual(db.execute("SELECT count,eof FROM pages WHERE instr(job,'@')=0").fetchone(),(0,1))
        with closing(sqlite3.connect(second['database'])) as db:
            self.assertEqual(db.execute('SELECT previous_attempts FROM workbench_empty_requery_jobs').fetchall(),[(1,)])
            self.assertEqual(db.execute('SELECT count(*) FROM attempts').fetchone()[0],2)
        self.config.pop('workbench_empty_retry')
        self.portal.offsets.clear()
        await self.run_bot()
        self.assertFalse(self.portal.offsets)

    async def test_requery_still_empty_can_be_requested_again_with_fresh_history(self):
        self.portal.empty = True
        first = await self.run_bot()
        self.empty_retry(first['database'])
        for _ in range(2):
            self.portal.offsets.clear()
            await self.run_bot()
            self.assertEqual(self.portal.offsets,[0])
        self.assertEqual(self.counts(first['database']),(('Guardado',3,0),0))
        with closing(sqlite3.connect(first['database'])) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM workbench_empty_requeries').fetchone()[0],2)
        with closing(sqlite3.connect(Path(first['database']).with_name('bls_pages.sqlite3'))) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM pages').fetchone()[0],3)

    async def test_requery_partial_failure_resumes_its_new_generation_on_normal_start(self):
        self.portal.empty = True
        first = await self.run_bot()
        self.empty_retry(first['database'])
        self.portal.empty = False
        second = await self.run_bot()
        self.assertEqual(self.counts(second['database']),(('Pendiente',2,0),0))
        self.config.pop('workbench_empty_retry')
        self.portal.fail_offset = None
        self.portal.offsets.clear()
        third = await self.run_bot()
        self.assertEqual(self.portal.offsets,[0,4,6])
        self.assertEqual(self.counts(third['database']),(('Guardado',3,7),7))

    async def test_get_refresh_before_confirm_does_not_timeout_or_repeat_lookup(self):
        self.portal.fail_offset=None
        self.portal.search_get=True
        result=await self.run_bot()
        self.assertEqual(self.counts(result['database']),(('Guardado',1,7),7))
        self.assertEqual(self.portal.searches,[frame().iloc[0]['BL original']])

    async def test_stop_after_eof_reopens_verified_checkpoint_before_confirming(self):
        self.portal.fail_offset=None
        self.portal.repeated_last=True
        def progress(event):
            self.events.append(event)
            # La confirmación EOF repetida anuncia nuevamente la página 3.
            if event.get('job',{}).get('checkpointPage')==3 and len(self.portal.offsets)>=4:
                self.stop.set()
        self.config['event_callback']=progress
        first=await self.run_bot()
        self.assertEqual(self.counts(first['database']),(('Pendiente',1,0),0))
        self.stop.clear()
        self.config['event_callback']=self.events.append
        self.portal.offsets.clear()
        result=await self.run_bot()
        self.assertEqual(self.portal.offsets,[0,4,6])
        self.assertEqual(self.counts(result['database']),(('Guardado',2,6),6))

    async def test_workers_keep_bl_pages_independent(self):
        self.config['cant_hilos']=2
        data=pd.concat([frame(),frame().assign(**{'BL original':'00002'})],ignore_index=True)
        first=await self.run_bot(data)
        self.assertEqual((first['saved'],first['pending'],first['result_rows']),(0,2,0))
        with closing(sqlite3.connect(Path(first['database']).with_name('bls_pages.sqlite3'))) as db:
            self.assertEqual(db.execute('SELECT ordinal,count(*),sum(count) FROM pages GROUP BY ordinal ORDER BY ordinal').fetchall(),
                             [(1,3,6),(2,3,6)])
        self.portal.fail_offset=None
        second=await self.run_bot(data)
        self.assertEqual((second['saved'],second['result_rows']),(2,14))
        with closing(sqlite3.connect(second['database'])) as db:
            counts=db.execute('SELECT job,count(*) FROM results GROUP BY job').fetchall()
        self.assertEqual(sorted(c for _,c in counts),[7,7])

    async def test_damaged_checkpoint_remains_pending_without_overwriting_it(self):
        first=await self.run_bot()
        path=Path(first['database']).with_name('bls_pages.sqlite3')
        with closing(sqlite3.connect(path)) as db:
            db.execute("UPDATE pages SET rows_json='[]' WHERE page=2")
            db.commit()
        self.portal.fail_offset=None
        second=await self.run_bot()
        self.assertEqual(self.counts(second['database']),(('Pendiente',2,0),0))
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT rows_json FROM pages WHERE page=2').fetchone()[0],'[]')
            self.assertEqual(db.execute('SELECT count(*) FROM pages').fetchone()[0],3)

    async def test_response_arriving_after_stop_cannot_save_a_page(self):
        original=frame().iloc[0].to_dict()
        query={'mid':[original['IDManifiesto']],'bl':[original['BL original']],'seq':['1']}
        href='/Tica/hcglineas.aspx?'+urlencode({k:v[0] for k,v in query.items()})
        target=self.portal.url.replace('/Tica/hcgconocimientos.aspx',href)
        _,_,html=self.portal.response('/Tica/hcglineas.aspx',query,{},False)
        response=SimpleNamespace(status=200,url=target,text=AsyncMock(return_value=html),dispose=AsyncMock())
        async def late_reply(*args,**kwargs):
            self.stop.set()
            return response
        def active(key):
            if self.stop.is_set():raise asyncio.CancelledError()
            return 1
        pages=PageStore(self.root/'late.sqlite3','fixture')
        try:
            session=PagedTicaSession(self.browser,self.config,{'http_requests':0},pages,lambda *args:None,active)
            session.page=SimpleNamespace(url=self.portal.url)
            session.context=SimpleNamespace(request=SimpleNamespace(get=late_reply))
            with self.assertRaises(asyncio.CancelledError):
                await session.browser_detail({'href':href,'sequence':'1'},original)
            self.assertEqual(pages.load(input_job(original,0)['key']),[])
            response.dispose.assert_awaited_once()
        finally:pages.close()


if __name__=='__main__':unittest.main()
