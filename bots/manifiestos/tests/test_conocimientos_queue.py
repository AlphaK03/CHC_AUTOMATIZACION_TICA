import asyncio
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from conocimientos import KnowledgeStore, IDENTITY, parse_main_rows, MAX_CONCURRENCY
from conocimientos_flow import ConocimientosFlow


def grid_for(count):
    grid = {'Count': count}
    for i in range(count):
        values = ['1', '0', str(26000000 + i), 'P003', '01/08/26']
        grid[str(i)] = {'Props': [[field + f'_{i + 1:04d}', value]
                                 for field, value in zip(IDENTITY, values)]
                       + [[f'vVCONS_{i + 1:04d}', f'hcgcons.aspx?{i}']]}
    return grid


def flow_for(folder, count=357):
    flow = ConocimientosFlow()
    flow.URL = 'https://example/Tica/hcicgmic.aspx'
    flow.config = {'output_manifest_conocimientos_folder': folder, 'conocimientos_concurrencia': 3}
    flow.init_conoc_output('maritimo', 8, 2026)
    flow.conoc_main_grid = grid_for(count)
    flow.conoc_main_values = [[p[1] for p in flow.conoc_main_grid[str(i)]['Props']] for i in range(count)]
    return flow


def result(info):
    mid = '-'.join(info[k] for k in ('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha'))
    row = [mid, '1', '000123', 'N'] + [''] * 11
    return mid, [row], {'pages': 1, 'read': 1, 'kept': 1}


class ConcurrentQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_357_accounted_concurrent_then_only_failures_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = flow_for(folder)
            flow.config['conocimientos_concurrencia'] = MAX_CONCURRENCY
            active, maximum = 0, 0
            called = []

            async def fetch(href, ordinal, info):
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                called.append(ordinal)
                try:
                    await asyncio.sleep(0.001 * (ordinal % 3))
                    if ordinal % 13 == 0:
                        raise TimeoutError('fallo simulado')
                    return result(info)
                finally:
                    active -= 1

            flow._fetch_conoc_result = fetch
            await flow.process_conocimientos_links()
            p = flow.conoc_progress
            self.assertEqual((p['selected'], p['saved'], p['pending'], p['active'], p['processed_run']),
                             (357, 330, 27, 0, 357))
            self.assertEqual(sorted(called), list(range(1, 358)))
            self.assertEqual(maximum, MAX_CONCURRENCY)
            flow.conoc_store.close()

            flow = flow_for(folder)
            called = []

            async def retry(href, ordinal, info):
                called.append(ordinal)
                return result(info)

            flow._fetch_conoc_result = retry
            await flow.process_conocimientos_links()
            self.assertEqual(sorted(called), list(range(13, 358, 13)))
            self.assertEqual(flow.conoc_progress['saved'], 357)
            self.assertEqual(flow.conoc_progress['processed_run'], 27)
            flow.write_conoc_failures()
            with open(flow.conoc_output_path, encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 357)
            self.assertEqual([r['IDManifiesto'] for r in rows], sorted(r['IDManifiesto'] for r in rows))
            self.assertTrue(all(r['BL original'] == '000123' for r in rows))
            jobs = flow.conoc_store.jobs()
            self.assertTrue(all(j['attempts'] == (2 if j['ordinal'] % 13 == 0 else 1) for j in jobs))
            flow.conoc_store.close()

    async def test_interruption_recovers_active_and_never_started(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = flow_for(folder, 9)
            running = asyncio.Event()
            started = []

            async def fetch(href, ordinal, info):
                started.append(ordinal)
                if len(started) == 3:
                    running.set()
                await asyncio.Event().wait()

            flow._fetch_conoc_result = fetch
            task = asyncio.create_task(flow.process_conocimientos_links())
            await asyncio.wait_for(running.wait(), 3)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(flow.conoc_store.progress()['active'], 0)
            self.assertEqual(flow.conoc_store.progress()['pending'], 9)
            self.assertEqual(sum(j['attempts'] for j in flow.conoc_store.jobs()), 3)
            flow.conoc_store.close()

            flow = flow_for(folder, 9)
            async def success(href, ordinal, info):
                return result(info)
            flow._fetch_conoc_result = success
            await flow.process_conocimientos_links()
            self.assertEqual(flow.conoc_progress['saved'], 9)
            flow.conoc_store.close()

    async def test_resume_missing_link_is_counted_as_pending_not_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = flow_for(folder, 3)
            async def fail(href, ordinal, info):
                raise ValueError('fallo')
            flow._fetch_conoc_result = fail
            await flow.process_conocimientos_links()
            flow.conoc_main_grid = grid_for(2)  # Una fila desapareció de la consulta.
            flow.conoc_main_values = flow.conoc_main_values[:2]
            async def success(href, ordinal, info):
                return result(info)
            flow._fetch_conoc_result = success
            await flow.process_conocimientos_links()
            self.assertEqual(flow.conoc_progress['selected'], 3)
            self.assertEqual(flow.conoc_progress['saved'], 2)
            self.assertEqual(flow.conoc_progress['pending'], 1)
            self.assertEqual(flow.conoc_progress['processed_run'], 3)
            self.assertIn('No hay enlace', flow.conoc_store.jobs()[2]['error'])
            flow.conoc_store.close()

    async def test_next_job_starts_without_waiting_for_slowest(self):
        with tempfile.TemporaryDirectory() as folder:
            flow = flow_for(folder, 4)
            flow.config['conocimientos_concurrencia'] = 2
            third = asyncio.Event()
            async def fetch(href, ordinal, info):
                if ordinal == 1:
                    await asyncio.wait_for(third.wait(), 3)
                    self.assertTrue(flow.conoc_store.completed(result_for_second))
                if ordinal == 3:
                    third.set()
                return result(info)
            result_for_second = '1-0-26000001-P003-01/08/26'
            flow._fetch_conoc_result = fetch
            await flow.process_conocimientos_links()
            self.assertEqual(flow.conoc_progress['saved'], 4)
            flow.conoc_store.close()


class DurableStoreTests(unittest.TestCase):
    def test_values_are_authoritative_and_pending_identity_is_repaired(self):
        grid = grid_for(3)
        actual = [[p[1] for p in grid[str(i)]['Props']] for i in range(3)]
        actual[0][4] = '06/08/26'
        actual[1][4] = '12/08/26'
        actual[2][4] = '06/08/26'
        grid['0']['Props'][4][1] = '06/08/26'
        grid['1']['Props'][4][1] = '12/08/26'
        grid['2']['Props'][4] = ['CGFCHARR_0003']  # No significa heredar el valor previo.
        snapshot = parse_main_rows(grid, json.dumps(actual), 'https://example/Tica/')
        self.assertEqual(snapshot[2][1]['Fecha'], '06/08/26')
        old = snapshot[2][2]
        new = '-'.join(actual[2][:5])
        self.assertTrue(old.endswith('12/08/26'))
        with tempfile.TemporaryDirectory() as folder:
            store = KnowledgeStore(Path(folder) / 'out.csv', {})
            store.prepare_selection([(3, 'url', {}, old)])
            store.start_run()
            store.claim(old)
            store.fail(old, 1, f'Manifiesto inesperado: {new}; esperado {old}')
            store.finish_run(1)
            self.assertEqual(store.reconcile_identities([(old, new, 3)], {new}), [(old, new)])
            job = store.jobs()[0]
            self.assertEqual((job['id'],job['ordinal'],job['attempts'],job['state']), (new,1,1,'Pendiente'))
            self.assertEqual(store.db.execute('SELECT manifest FROM attempts').fetchone()[0], new)
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM identity_changes').fetchone()[0], 1)
            self.assertEqual(store.reconcile_identities([(old, new, 3)], {new}), [])
            store.close()

    def test_lock_prevents_second_writer_and_migration_keeps_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'conocimientos.csv'
            store = KnowledgeStore(path, {})
            mid = '1-0-26000000-P003-01/08/26'
            row = [mid, '1', '001', 'N'] + [''] * 11
            store.save(mid, 1, [row], {'pages': 1, 'read': 1, 'kept': 1})
            with self.assertRaisesRegex(RuntimeError, 'otra ejecución'):
                KnowledgeStore(path, {})
            store.close()
            store = KnowledgeStore(path, {})
            store.prepare_selection([(1, '', {}, mid), (2, '', {}, 'otro')])
            self.assertEqual([j['state'] for j in store.jobs()], ['Guardado', 'Pendiente'])
            store.start_run()
            store.claim('otro')
            store.close()  # Simula salida abrupta antes de terminar el manifiesto.
            store = KnowledgeStore(path, {})
            store.start_run()
            self.assertEqual(store.progress()['active'], 0)
            self.assertEqual(store.progress()['pending'], 1)
            store.close()


if __name__ == '__main__':
    unittest.main()
