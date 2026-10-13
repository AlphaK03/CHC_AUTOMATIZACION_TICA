import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from conocimientos import extract_table, request_html, SessionExpired, IncompleteTable
from conocimientos_flow import ConocimientosFlow
from tablas_flow import IsolatedTableRequest, ManifestTablesFlow
from tablas_manifiesto import ManifestTableStore, LINK_FIELDS, parse_table
from test_conocimientos_queue import grid_for
from test_tablas_manifiesto import table_html, MID


class TrackedFlow(ManifestTablesFlow, ConocimientosFlow):
    pass


def response(source='', status=200):
    return SimpleNamespace(status=status, ok=200 <= status < 300,
                           text=AsyncMock(return_value=source), dispose=AsyncMock())


class IndependentRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_html_parser_does_not_block_other_async_workers(self):
        entered, release = threading.Event(), threading.Event()
        def parser(source, mid):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('El event loop no pudo liberar al lector')
            return parse_table(source, mid, 'duas')
        request = SimpleNamespace(get=AsyncMock(return_value=response(table_html('duas', []))))
        task = asyncio.create_task(extract_table(request, 'url', MID, 0, parse_html=parser,
                                                parse_in_thread=True, request_attempts=1, recover_errors=False))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 1))
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            release.set()
            rows, stats = await asyncio.wait_for(task, 2)
            self.assertEqual(rows, [])
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    async def test_only_asp_session_cookie_removed_and_client_kept_for_paging(self):
        cookies = [{'name': name, 'value': name, 'domain': 'example', 'path': '/'}
                   for name in ['ASP.NET_SessionId', 'GX_SESSION_ID', 'CONTEXTCOOKIE', 'access']]
        browser = SimpleNamespace(cookies=AsyncMock(return_value=cookies))
        first = SimpleNamespace(get=AsyncMock(), post=AsyncMock(), dispose=AsyncMock())
        second = SimpleNamespace(get=AsyncMock(), post=AsyncMock(), dispose=AsyncMock())
        factory = SimpleNamespace(new_context=AsyncMock(side_effect=[first, second]))
        a = IsolatedTableRequest(factory, browser, 'user-agent')
        b = IsolatedTableRequest(factory, browser, 'user-agent')
        await a.get('url', timeout=0)
        await a.post('url', form={'NEXT': '1'}, timeout=0)
        await b.get('other', timeout=0)
        self.assertIsNot(a.client, b.client)
        self.assertEqual(factory.new_context.await_count, 2)
        supplied = factory.new_context.call_args.kwargs
        self.assertEqual([c['name'] for c in supplied['storage_state']['cookies']],
                         ['GX_SESSION_ID', 'CONTEXTCOOKIE', 'access'])
        self.assertEqual(supplied['user_agent'], 'user-agent')
        self.assertEqual(cookies[0]['name'], 'ASP.NET_SessionId')
        first.post.assert_awaited_once()
        await a.close()
        await a.close()
        await b.close()
        first.dispose.assert_awaited_once()
        second.dispose.assert_awaited_once()

    async def test_refresh_disposes_old_session_and_reads_updated_access_cookies(self):
        browser = SimpleNamespace(cookies=AsyncMock(side_effect=[[], [{'name': 'GX_SESSION_ID', 'value': 'new'}]]))
        clients = [SimpleNamespace(dispose=AsyncMock()) for _ in range(2)]
        factory = SimpleNamespace(new_context=AsyncMock(side_effect=clients))
        request = IsolatedTableRequest(factory, browser, 'ua')
        await request.refresh()
        await request.refresh()
        clients[0].dispose.assert_awaited_once()
        self.assertEqual(factory.new_context.call_args.kwargs['storage_state']['cookies'][0]['value'], 'new')
        await request.close()

    async def test_unlimited_wait_has_activity_and_cancellation_cleans_heartbeat(self):
        started, beat, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        events = []
        async def get(*args, **kwargs):
            self.assertEqual(kwargs['timeout'], 0)
            started.set()
            await release.wait()
        def activity(event):
            events.append(event)
            if event['stage'] == 'waiting':
                beat.set()
        client = SimpleNamespace(get=AsyncMock(side_effect=get))
        task = asyncio.create_task(request_html(client, 'url', 0, max_attempts=1,
                                               activity_callback=activity, heartbeat_seconds=0.01))
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(beat.wait(), 1)
        self.assertFalse(task.done())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        count = len(events)
        await asyncio.sleep(0.03)
        self.assertEqual(len(events), count)
        client.get.assert_awaited_once()

    async def test_http_error_is_not_retried_and_response_disposed(self):
        for status in (204, 429, 503):
            with self.subTest(status=status):
                result = response('error', status)
                request = SimpleNamespace(get=AsyncMock(return_value=result))
                with self.assertRaisesRegex(SessionExpired, f'HTTP {status}'):
                    await request_html(request, 'url', 0, max_attempts=1, expected_status=200)
                request.get.assert_awaited_once_with('url', timeout=0)
                result.text.assert_not_awaited()
                result.dispose.assert_awaited_once()

    async def test_http_200_error_page_is_rejected_without_recovery(self):
        result = response('<html>Error en el servidor</html>')
        request = SimpleNamespace(get=AsyncMock(return_value=result))
        with self.assertRaises(IncompleteTable):
            await extract_table(request, 'url', MID, 0, request_attempts=1, recover_errors=False,
                                expected_status=200, parse_html=lambda text, mid: parse_table(text, mid, 'duas'))
        request.get.assert_awaited_once()
        result.dispose.assert_awaited_once()

    async def test_duas_timeout_zero_and_other_flow_retains_operation_limits(self):
        info = dict(zip(('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha'), MID.split('-')))
        for name, timeout in [('duas', 0), ('movimientos', 120)]:
            with self.subTest(flow=name):
                flow = TrackedFlow()
                flow.table_flow, flow.timeout = name, 120
                flow.config = {'conocimientos_refresco_segundos': 600}
                flow.request_factory = SimpleNamespace(new_context=AsyncMock())
                flow.context = SimpleNamespace(cookies=AsyncMock(return_value=[]))
                flow.table_user_agent, flow.conoc_store = 'ua', object()
                with patch('tablas_flow.extract_table', AsyncMock(return_value=([], {}))) as extract:
                    await flow._fetch_tracked_result('url', 20, info)
                self.assertEqual(extract.call_args.args[3], timeout)
                self.assertEqual(extract.call_args.kwargs['recover_errors'], name != 'duas')
                self.assertEqual(extract.call_args.kwargs['request_attempts'], 1 if name == 'duas' else 3)


class IndependentQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_duas_ignores_total_deadline_and_movements_keeps_its_setting(self):
        for name in ('duas', 'movimientos'):
            with self.subTest(flow=name), tempfile.TemporaryDirectory() as folder:
                flow = TrackedFlow()
                flow.URL = 'https://example/main'
                flow.config = {f'output_manifest_{name}_folder': folder, f'{name}_timeout_total': 1}
                flow.context = SimpleNamespace(close=AsyncMock())
                flow.page = SimpleNamespace(evaluate=AsyncMock(return_value='ua'))
                flow.open_page = AsyncMock()
                flow._query_conoc_main = AsyncMock()
                flow.process_conocimientos_links = AsyncMock()
                flow.write_conoc_failures = MagicMock()
                await flow.run_tracked_table(name, 'aereo', 9, 2026)
                self.assertEqual(flow.config['conocimientos_timeout_total'], 0 if name == 'duas' else 1)

    async def test_cli_provides_independent_request_factory(self):
        import conocimientos_cli
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(exportar_db=None, salida=Path(folder), procedimiento='duas',
                                   desde=None, hasta=None, manifiesto=None, limite=1, concurrencia=2,
                                   solo_sqlite=True, modalidad='aereo', mes=9, ano=2026, visible=False)
            browser = SimpleNamespace(close=AsyncMock())
            pw = SimpleNamespace(request=object(), chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))
            manager = MagicMock()
            manager.__aenter__ = AsyncMock(return_value=pw)
            manager.__aexit__ = AsyncMock(return_value=False)
            scraper = SimpleNamespace(run_tracked_table=AsyncMock(), conoc_summary={}, conoc_progress={}, conoc_stats=[])
            with patch.object(conocimientos_cli, 'load_config', return_value={}), \
                 patch.object(conocimientos_cli, 'async_playwright', return_value=manager), \
                 patch.object(conocimientos_cli, 'ManifestScraper', return_value=scraper) as constructor, \
                 patch.object(conocimientos_cli.logging, 'basicConfig'), \
                 patch.object(conocimientos_cli.logging, 'FileHandler'), \
                 patch('builtins.print'):
                await conocimientos_cli.run(args)
            self.assertIs(constructor.call_args.kwargs['request_factory'], pw.request)
            scraper.run_tracked_table.assert_awaited_once_with('duas', 'aereo', 9, 2026)

    async def test_slow_manifest_stays_active_fast_and_error_jobs_continue_then_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = TrackedFlow()
            flow.URL, flow.table_flow, flow.timeout = 'https://example/main', 'duas', 120
            flow.config = {'conocimientos_concurrencia': 2, 'conocimientos_refresco_segundos': 600}
            flow.conoc_failed_rows, flow.conoc_stats = [], []
            flow.conoc_store = ManifestTableStore(Path(folder)/'duas.csv', {'flow': 'duas'})
            flow.conoc_main_grid = grid_for(4)
            for i in range(4):
                flow.conoc_main_grid[str(i)]['Props'][-1][0] = f'vVDUAS_{i+1:04d}'
            flow.conoc_main_values = [[p[1] for p in flow.conoc_main_grid[str(i)]['Props']] for i in range(4)]
            ids = ['-'.join(values[:5]) for values in flow.conoc_main_values]
            flow.context = SimpleNamespace(cookies=AsyncMock(return_value=[{'name': 'ASP.NET_SessionId', 'value': 'shared'}]))
            flow.table_user_agent = 'ua'
            started, release, finished_fast = asyncio.Event(), asyncio.Event(), asyncio.Event()
            called, clients = [], []
            async def new_context(**kwargs):
                self.assertEqual(kwargs['storage_state']['cookies'], [])
                async def get(url, **kwargs):
                    index = int(url.split('?')[-1])
                    called.append(index)
                    self.assertEqual(kwargs['timeout'], 0)
                    if index == 0:
                        started.set()
                        await release.wait()
                    if index == 1:
                        return response('server failed', 503)
                    mid = ids[index]
                    source = table_html('duas', [])
                    for before, after in zip(MID.split('-'), mid.split('-')):
                        source = source.replace(f'&quot;{before}&quot;', f'&quot;{after}&quot;')
                    return response(source)
                client = SimpleNamespace(get=AsyncMock(side_effect=get), dispose=AsyncMock())
                clients.append(client)
                return client
            flow.request_factory = SimpleNamespace(new_context=AsyncMock(side_effect=new_context))
            def notify(event):
                job = event.get('job')
                if job and job['id'] == ids[3] and job['state'] == 'Guardado':
                    finished_fast.set()
            flow.config['conocimientos_progress_callback'] = notify
            task = asyncio.create_task(flow.process_conocimientos_links(
                link_field=LINK_FIELDS['duas'], fetch_result=flow._fetch_tracked_result))
            try:
                await asyncio.wait_for(started.wait(), 2)
                await asyncio.wait_for(finished_fast.wait(), 2)
                self.assertFalse(task.done())
                self.assertEqual(flow.conoc_store.job(ids[0])['state'], 'Descargando')
                self.assertEqual(flow.conoc_store.job(ids[1])['state'], 'Pendiente')
                self.assertIn('HTTP 503', flow.conoc_store.job(ids[1])['error'])
                self.assertEqual(flow.conoc_store.progress()['saved'], 2)
                release.set()
                await asyncio.wait_for(task, 2)
                self.assertEqual(called, [0, 1, 2, 3])
                self.assertEqual(flow.conoc_progress['saved'], 3)
                for client in clients:
                    client.dispose.assert_awaited_once()
                called.clear()
                await flow.process_conocimientos_links(link_field=LINK_FIELDS['duas'], fetch_result=flow._fetch_tracked_result)
                self.assertEqual(called, [1])  # Reintentar exclusivamente el HTTP fallido.
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                flow.conoc_store.close()

    async def test_stop_returns_slow_job_to_pending_and_closes_client(self):
        # Cancelar una espera infinita debe liberar el cliente y mantener el trabajo recuperable.
        with tempfile.TemporaryDirectory() as folder:
            flow = TrackedFlow()
            flow.table_flow, flow.timeout, flow.table_user_agent = 'duas', 120, 'ua'
            flow.config = {'conocimientos_refresco_segundos': 600}
            flow.context = SimpleNamespace(cookies=AsyncMock(return_value=[]))
            started = asyncio.Event()
            async def get(*args, **kwargs):
                started.set()
                await asyncio.Event().wait()
            client = SimpleNamespace(get=AsyncMock(side_effect=get), dispose=AsyncMock())
            flow.request_factory = SimpleNamespace(new_context=AsyncMock(return_value=client))
            flow.conoc_store = ManifestTableStore(Path(folder)/'duas.csv', {'flow': 'duas'})
            info = dict(zip(('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha'), MID.split('-')))
            flow.conoc_store.prepare_selection([(20, 'url', info, MID)])
            flow.conoc_store.start_run()
            flow.conoc_store.claim(MID)
            task = asyncio.create_task(flow._fetch_tracked_result('url', 20, info))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            client.dispose.assert_awaited_once()
            flow.conoc_store.interrupt('Detenido por el usuario')
            self.assertEqual(flow.conoc_store.job(MID)['state'], 'Pendiente')
            flow.conoc_store.close()
