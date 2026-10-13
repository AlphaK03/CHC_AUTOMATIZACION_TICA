"""Calendario y append diario sin navegador, Excel ni datos originales."""
from datetime import date, datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from daily import ZONE, DailyJobStore, eligible_day, next_midnight
from workbench_worker import DetailsService, JobStore


class SilentProtocol:
    def emit(self, *args, **kwargs): pass


class DailyCalendarTest(unittest.TestCase):
    def test_range_includes_earlier_days_and_stops_at_end_without_reprocessing(self):
        with tempfile.TemporaryDirectory() as folder:
            service = DetailsService(folder, SilentProtocol(), offline=True)
            self.addCleanup(logging_cleanup)
            now = datetime(2026, 10, 12, 12, tzinfo=ZONE)
            service.daily.now = lambda: now
            with patch('workbench_worker.local_now', return_value=now):
                service.configure({'daily_start_date': '2026-09-29', 'daily_end_date': '2026-10-01', 'output_base_path': folder})
                with self.assertRaises(ValueError):
                    service.configure({'daily_end_date': '2026-09-28'})
                with self.assertRaises(ValueError):
                    service.configure({'daily_end_date': '2026-10-12'})
            cells = service.daily.ledger.month('2026-09', date(2026, 10, 11), now)
            early = next(cell for cell in cells if cell.get('date') == '2026-09-01')
            self.assertEqual(early['state'], 'outside')
            self.assertTrue(early['available'])
            calls = []
            def complete(day):
                calls.append(day)
                service.daily.ledger.update(day, state='completed')
                return True
            with patch.object(service.daily, 'cycle', side_effect=complete):
                self.assertEqual(service.daily.run()['runStatus'], 'completed')
                self.assertEqual(service.daily.run()['runStatus'], 'completed')
            self.assertEqual(calls, [date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)])
            self.assertFalse(service.daily.active)
            self.assertEqual(service.daily.ledger.get(date(2026, 10, 2)), {})
            logging_cleanup()

    def test_daily_scope_never_reserves_other_monthly_pending_duas(self):
        with tempfile.TemporaryDirectory() as folder:
            service = DetailsService(folder, SilentProtocol(), offline=True)
            self.addCleanup(logging_cleanup)
            record = service.daily.append_day(date(2026, 10, 1), ['001-2026-000001'])
            service.daily.append_day(date(2026, 10, 2), ['001-2026-000002'])
            store = DailyJobStore(service.catalog.database(record), ['001-2026-000002'])
            try:
                store.begin_run()
                self.assertEqual(store.summary()['total'], 1)
                job = store.claim(1)
                self.assertEqual(job['dua'], '001-2026-000002')
                self.assertIsNone(store.claim(1))
                store.retry(job, 'Prueba sin navegador', cancelled=True)
                outside = store.db.execute("SELECT status,attempts FROM jobs WHERE dua='001-2026-000001'").fetchone()
                self.assertEqual(tuple(outside), ('pending', 0))
            finally:
                store.close()
            empty = DailyJobStore(service.catalog.database(record), [])
            try:
                self.assertEqual(empty.summary()['total'], 0)
                self.assertIsNone(empty.claim(1))
            finally:
                empty.close()
            logging_cleanup()

    def test_midnight_eligibility_and_catchup(self):
        before = datetime(2026, 10, 1, 0, 0, tzinfo=ZONE)
        after = datetime(2026, 10, 1, 0, 1, tzinfo=ZONE)
        self.assertEqual(eligible_day(before), date(2026, 9, 29))
        self.assertEqual(eligible_day(after), date(2026, 9, 30))
        self.assertEqual(next_midnight(before), after)
        self.assertEqual(next_midnight(after), datetime(2026, 10, 2, 0, 1, tzinfo=ZONE))
        with tempfile.TemporaryDirectory() as folder:
            service = DetailsService(folder, SilentProtocol(), offline=True)
            ledger = service.daily.ledger
            ledger.update(date(2026, 9, 28), state='completed')
            ledger.update(date(2026, 9, 29), state='pending')
            self.assertEqual(ledger.next_day(date(2026, 9, 28), date(2026, 10, 1)), date(2026, 9, 29))
            logging_cleanup()

    def test_monthly_append_is_idempotent_and_empty_days_are_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            service = DetailsService(folder, SilentProtocol(), offline=True)
            first = date(2026, 9, 30)
            second = date(2026, 10, 1)
            service.daily.append_day(date(2026, 9, 29), [])
            record = service.daily.append_day(first, ['001-2026-000001'])
            service.daily.append_day(first, ['001-2026-000001'])
            self.assertEqual(record['name'], 'septiembre26')
            store = JobStore(service.catalog.database(record))
            try:
                self.assertEqual(store.summary()['total'], 1)
                self.assertEqual(store.meta('source_rows'), 1)
            finally:
                store.close()
            other = service.daily.append_day(second, ['001-2026-000002'])
            self.assertEqual(other['name'], 'octubre26')
            self.assertNotEqual(record['id'], other['id'])
            self.assertEqual(len(service.catalog.list_tables()), 2)
            logging_cleanup()


def logging_cleanup():
    import logging
    for handler in list(logging.getLogger().handlers):
        handler.close()
        logging.getLogger().removeHandler(handler)


if __name__ == '__main__':
    unittest.main()
