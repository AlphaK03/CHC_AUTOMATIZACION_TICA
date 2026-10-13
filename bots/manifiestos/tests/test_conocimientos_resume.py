import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_conocimientos import MID, page
from conocimientos import KnowledgeStore, IncompleteTable, extract_table, parse_page


class PageResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_interruption_reopen_resume_without_redownloading_prefix(self):
        first = page([(1, '001', 'N')], eof=False)
        second = page([(2, '002', 'S')], offset=1, eof=False)
        last = page([(3, '003', 'N')], offset=2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.csv'
            store = KnowledgeStore(path, {})
            def stop(stats):
                if stats['pages'] == 2:
                    raise asyncio.CancelledError()
            with patch('conocimientos.request_html', AsyncMock(side_effect=[first, second])):
                with self.assertRaises(asyncio.CancelledError):
                    await extract_table(None, 'url', MID, checkpoint=store, progress_callback=stop)
            self.assertFalse(store.completed(MID))
            self.assertEqual(store.summary()['rows'], 0)
            store.close()
            store = KnowledgeStore.open_existing(path.with_suffix('.sqlite3'))
            with patch('conocimientos.request_html', AsyncMock(side_effect=[first, second, last])) as fetch:
                rows, stats = await extract_table(None, 'new-url', MID, courier='N', checkpoint=store)
            self.assertEqual([r[2] for r in rows], ['001', '003'])
            self.assertEqual(stats, {'pages': 3, 'read': 3, 'kept': 2})
            self.assertEqual(fetch.await_count, 3)  # Primera página, ancla y única página pendiente.
            self.assertEqual(json.loads(fetch.call_args_list[1].args[3]['GXState'])['GRID1_nFirstRecordOnPage'], '0')
            store.save(MID, 1, rows, stats)
            self.assertTrue(store.completed(MID))
            self.assertEqual(store.load_checkpoint(MID), [])
            store.close()

    async def test_network_failure_reconnects_without_duplicating_rows(self):
        first = page([(1, '001', 'N')], eof=False)
        last = page([(2, '002', 'N')], offset=1)
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'test.csv', {})
            with patch('conocimientos.request_html', AsyncMock(side_effect=[first, TimeoutError('red'), first, last])):
                rows, stats = await extract_table(None, 'url', MID, checkpoint=store)
            self.assertEqual(len(rows), 2)
            self.assertEqual(stats['pages'], 2)
            self.assertEqual(len(store.load_checkpoint(MID)), 2)
            store.close()

    async def test_periodic_refresh_preserves_pages_and_filter(self):
        first = page([(1, '001', 'S')], eof=False)
        last = page([(2, '002', 'N')], offset=1)
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'test.csv', {})
            with patch('conocimientos.time.monotonic', side_effect=[0, 601, 601]), \
                 patch('conocimientos.request_html', AsyncMock(side_effect=[first, first, last])) as fetch:
                rows, stats = await extract_table(None, 'url', MID, courier='N', checkpoint=store)
            self.assertEqual(fetch.await_count, 3)
            self.assertEqual([r[2] for r in rows], ['002'])
            self.assertEqual(stats['read'], 2)
            store.close()

    async def test_changed_anchor_is_rejected_and_checkpoint_kept(self):
        first = page([(1, '001', 'N')], eof=False)
        second = page([(2, '002', 'N')], offset=1, eof=False)
        changed = page([(2, 'CHANGED', 'N')], offset=1, eof=False)
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'test.csv', {})
            for html in (first, second):
                store.save_checkpoint(MID, parse_page(html, MID))
            with patch('conocimientos.request_html', AsyncMock(side_effect=[first, changed])):
                with self.assertRaisesRegex(IncompleteTable, 'reanudación cambió'):
                    await extract_table(None, 'url', MID, checkpoint=store)
            self.assertEqual(store.load_checkpoint(MID)[1].rows[0][2], '002')
            self.assertFalse(store.completed(MID))
            store.close()

    async def test_expired_form_renews_link_then_continues(self):
        first = page([(1, '001', 'N')], eof=False)
        last = page([(2, '002', 'N')], offset=1)
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'test.csv', {})
            renew = AsyncMock(return_value='fresh-url')
            with patch('conocimientos.asyncio.sleep', AsyncMock()), \
                 patch('conocimientos.request_html', AsyncMock(side_effect=[
                     first, '<html>Expired</html>', '<html>Expired</html>', first, last])) as fetch:
                rows, _ = await extract_table(None, 'url', MID, checkpoint=store, renew_link=renew)
            renew.assert_awaited_once()
            self.assertEqual(fetch.call_args.args[1], 'fresh-url')
            self.assertEqual(len(rows), 2)
            store.close()

    async def test_persistent_disconnect_has_bounded_retries_and_keeps_progress(self):
        first = page([(1, '001', 'N')], eof=False)
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'test.csv', {})
            with patch('conocimientos.asyncio.sleep', AsyncMock()), \
                 patch('conocimientos.request_html', AsyncMock(side_effect=[first] + [TimeoutError('offline')] * 4)) as fetch:
                with self.assertRaises(TimeoutError):
                    await extract_table(None, 'url', MID, checkpoint=store)
            self.assertEqual(fetch.await_count, 5)
            self.assertEqual(len(store.load_checkpoint(MID)), 1)
            self.assertFalse(store.completed(MID))
            store.close()

    async def test_confirmed_final_checkpoint_can_finish_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'test.csv', {})
            store.save_checkpoint(MID, parse_page(page([(1, '001', 'N')]), MID))
            with patch('conocimientos.request_html', AsyncMock()) as fetch:
                rows, stats = await extract_table(None, 'url', MID, checkpoint=store)
            fetch.assert_not_awaited()
            self.assertEqual(stats['read'], 1)
            store.save(MID, 1, rows, stats)
            self.assertTrue(store.completed(MID))
            store.close()
