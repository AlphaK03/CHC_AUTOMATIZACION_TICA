"""Aceptación de días/meses: cobertura manual global y CSV sin perder pendientes."""
from datetime import date
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_monthly_progress as fixtures
from test_monthly_progress import write
from daily_marks import DailyMarks
from monthly_progress import MonthlyReader, MODULES, FLOWS, month_days
from chc_cloud.service import CloudService
from chc_cloud.tests.test_service import Account, Graph
from chc_runtime import output_layout

DUA_MODULES = ('detalles', 'duas_transito', 'talon', 'xmovimientos')


class ManualDayCompletionTests(unittest.TestCase):
    def setUp(self):
        self.data = fixtures.MonthlyTests()
        self.data.setUp()
        self.addCleanup(self.data.tearDown)
        self.root, self.today = self.data.root, self.data.today

    def fixture(self):
        path = self.data.dua_table(done=False)
        self.data.ledger()
        return path

    def read(self, module='detalles', today=None):
        reader = MonthlyReader({module: self.root}, today or self.today)
        result = reader.read()
        return reader, self.data.cell(result, module)

    def test_manual_day_counts_and_closes_each_dua_bot_without_changing_sqlite(self):
        self.fixture()
        files = list(self.root.rglob('*.sqlite3'))
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        marks = DailyMarks(self.root)
        for module in DUA_MODULES:
            with self.subTest(module=module):
                self.assertEqual(self.read(module)[1]['status'], 'partial')
                marks.set_completed('2026-09-30', True)
                reader, cell = self.read(module)
                self.assertEqual((cell['status'], cell['label']), ('completed', 'Completado manual'))
                self.assertEqual((cell['coveredDays'], cell['verifiedDays'], cell['manualDays']), (30, 29, 1))
                self.assertIn('30 / 30 días completos (29 verificados · 1 manuales)', cell['detail'])
                self.assertEqual((reader.entries[0]['saved'], reader.entries[0]['omitted']), (29, 1))
                marks.set_completed('2026-09-30', False)
                self.assertEqual(self.read(module)[1]['status'], 'partial')
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, hashes)

    def test_manual_does_not_hide_unselected_pending_jobs_or_unaccepted_days(self):
        path = self.fixture()
        marks = DailyMarks(self.root)
        marks.set_completed('2026-09-30', True)
        with write(path) as db:
            db.execute("INSERT INTO jobs VALUES ('extra', 'pending', NULL)")
        self.assertEqual(self.read()[1]['status'], 'partial')
        with write(path) as db:
            db.execute("DELETE FROM jobs WHERE dua='extra'")
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("DELETE FROM days WHERE day='2026-09-29'")
        self.assertNotEqual(self.read()[1]['status'], 'completed')
        marks.set_completed('2026-09-29', True)
        cell = self.read()[1]
        self.assertEqual(cell['status'], 'completed')
        self.assertEqual(cell['manualDays'], 2)

    def test_missing_bases_accept_manual_days_and_marks_without_ledger_count(self):
        self.fixture()
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET base_ready=0,table_id='',state='pending' WHERE day='2026-09-30'")
        with write(self.root/'data/queues/month.sqlite3') as db:
            db.execute("UPDATE jobs SET status='succeeded',result='[]'")
        self.assertNotEqual(self.read()[1]['status'], 'completed')
        DailyMarks(self.root).set_completed('2026-09-30', True)
        self.assertEqual(self.read()[1]['status'], 'completed')
        # No crear bases ni resultados para un mes que solo tiene aceptación manual.
        marks = DailyMarks(self.root)
        for day in month_days('2026-08'):
            marks.set_completed(day, True)
        reader = MonthlyReader({'talon': self.root}, self.today)
        reader.read()
        self.assertEqual(reader.cell('2026-08', 'talon')['status'], 'completed')
        self.assertFalse(list((self.root/'data/queues').glob('*2026-08*')))

    def test_current_month_needs_all_eligible_days_and_does_not_accept_future_marks(self):
        self.data.dua_table(source='daily://2026-10')
        self.data.ledger(count=12)
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET day=replace(day,'2026-09','2026-10')")
            db.execute("UPDATE daily_duas SET day=replace(day,'2026-09','2026-10')")
        with write(self.root/'data/queues/month.sqlite3') as db:
            db.execute("UPDATE jobs SET status='retry',result=NULL WHERE dua='12'")
        marks = DailyMarks(self.root)
        marks.set_completed('2026-10-12', True)
        marks.set_completed('2026-10-13', True)
        cell = self.read()[1]
        self.assertEqual((cell['status'], cell['label']), ('up_to_date', 'Al día (manual)'))
        self.assertEqual((cell['coveredDays'], cell['manualDays']), (12, 1))
        marks.set_completed('2026-10-13', False)
        self.assertNotEqual(self.read(today=date(2026,10,14))[1]['status'], 'up_to_date')

    def test_active_and_unreadable_results_do_not_become_ready_to_upload(self):
        path = self.fixture()
        DailyMarks(self.root).set_completed('2026-09-30', True)
        with write(path) as db:
            db.execute("UPDATE jobs SET status='running' WHERE dua='30'")
        self.assertEqual(self.read()[1]['status'], 'running')
        with write(path) as db:
            db.execute("UPDATE jobs SET status='retry' WHERE dua='30'")
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET state='processing' WHERE day='2026-09-30'")
        self.assertEqual(self.read()[1]['status'], 'running')
        path.unlink()
        self.assertEqual(self.read()[1]['status'], 'unknown')

    def test_cloud_uses_real_day_acceptance_for_four_bots_and_refreshes_on_removal(self):
        path = self.fixture()
        monthly = lambda: MonthlyReader({m:self.root for m in DUA_MODULES}, self.today).read()
        graph = Graph()
        service = CloudService(self.root/'cloud', {}, Account(), graph, monthly=monthly)
        self.addCleanup(service.db.close)
        service.execute({'command':'local_root', 'path':str(self.root/'RESULTADOS')})
        service.execute({'command':'site', 'url':'https://test.sharepoint.com/sites/reportes'})
        service.save_destination('drive', 'folder')
        source = self.root/'sample.csv'
        source.write_bytes(b'DUA,Valor\r\n001-2026-000001,123\r\n')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for module in DUA_MODULES:
            output_layout.publish(source, self.root/'RESULTADOS', output_layout.specification(module,'2026-09'),
                                  module, service.exports_registry)
        with self.assertRaises(ValueError):
            service.upload_month('2026-09')
        DailyMarks(self.root).set_completed('2026-09-30', True)
        service.execute({'command':'status'})
        self.assertEqual(service.months()[0]['bots'], 4)
        self.assertEqual(service.snapshot()['pending'], 0)
        self.assertFalse(graph.sent, 'La marca y Actualizar nunca deben iniciar subidas.')
        service.upload_month('2026-09')
        self.assertEqual(len(graph.sent), 4)
        self.assertTrue(all(sent[1] == source.read_bytes() for sent in graph.sent))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        DailyMarks(self.root).set_completed('2026-09-30', False)
        with self.assertRaises(ValueError):
            service.upload_month('2026-09')
        self.assertFalse(service.months())

    def test_explicit_month_close_for_all_bots_and_five_procedures_enables_only_explicit_upload(self):
        reader = MonthlyReader({}, self.today, overrides_file=self.root/'overrides.json')
        targets = [module for module,_ in MODULES if module!='manifiestos'] + ['manifiestos:'+flow for flow,_ in FLOWS]
        for target in targets:
            module,_,flow = target.partition(':')
            reader.add('2026-09', module, flow, target, 2, 1, status='partial')
            reader.mark_complete('2026-09', target, True)
            self.assertEqual(reader.cell('2026-09', module, flow or None)['status'], 'completed')
        graph = Graph()
        service = CloudService(self.root/'cloud', {}, Account(), graph, monthly=reader.read)
        self.addCleanup(service.db.close)
        service.execute({'command':'local_root', 'path':str(self.root/'RESULTADOS')})
        service.execute({'command':'site', 'url':'https://test.sharepoint.com/sites/reportes'})
        service.save_destination('drive','folder')
        source = self.root/'sample.csv'; source.write_bytes(b'DUA\r\n001-2026-000001\r\n')
        for target in targets:
            output_layout.publish(source, self.root/'RESULTADOS', output_layout.specification(target,'2026-09'),
                                  target, service.exports_registry)
        service.execute({'command':'status'})
        self.assertEqual(service.months()[0]['bots'], 10)
        self.assertFalse(graph.sent)
        service.upload_month('2026-09')
        self.assertEqual(len(graph.sent), 10)
        reader.mark_complete('2026-09','detalles',False)
        self.assertNotEqual(reader.cell('2026-09','detalles')['status'],'completed')


if __name__ == '__main__':
    unittest.main()
