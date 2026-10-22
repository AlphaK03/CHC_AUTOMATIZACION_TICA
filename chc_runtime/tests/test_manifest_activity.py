"""La consola no cambia timeout=0, callbacks, respuestas ni cancelación HTTP."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'bots/manifiestos/src'))
import conocimientos
from chc_runtime.manifest_adapters import WorkbenchManifestScraper
from chc_runtime.manifest_activity import install
from chc_runtime.activity import ActivityReporter


class ManifestActivityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        install(WorkbenchManifestScraper)
        self.events=[]
        self.reporter=ActivityReporter(lambda kind,**data:self.events.append(dict(event=kind,**data)),interval=.01,repeat=.02)

    async def test_response_and_existing_callback_are_preserved(self):
        response=SimpleNamespace(status=200,ok=True,text=AsyncMock(return_value='respuesta completa'),dispose=AsyncMock())
        request=SimpleNamespace(post=AsyncMock(return_value=response))
        callbacks=[]
        with self.reporter.session('DUAs'):
            result=await conocimientos.request_html(request,'http://127.0.0.1',0,{'id':'001'},
                max_attempts=1,activity_callback=callbacks.append,expected_status=200)
        self.assertEqual(result,'respuesta completa')
        request.post.assert_awaited_once_with('http://127.0.0.1',form={'id':'001'},timeout=0)
        response.dispose.assert_awaited_once()
        self.assertEqual([e['stage'] for e in callbacks],['request','response'])
        self.assertTrue(any('sin límite de tiempo' in e.get('message','') for e in self.events))

    async def test_unlimited_wait_can_still_be_cancelled_without_retry(self):
        entered=asyncio.Event()
        async def wait(*args,**kwargs):
            entered.set();await asyncio.Event().wait()
        request=SimpleNamespace(get=AsyncMock(side_effect=wait))
        with self.reporter.session('DUAs'):
            task=asyncio.create_task(conocimientos.request_html(request,'http://127.0.0.1',0,max_attempts=1))
            await entered.wait();await asyncio.sleep(.04)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(request.get.await_count,1)
        self.assertTrue(any(e.get('running') and any('sin límite' in r['label'] for r in e['operations']) for e in self.events if e['event']=='activity_state'))


if __name__=='__main__':unittest.main()
