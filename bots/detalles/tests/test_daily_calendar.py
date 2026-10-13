"""Calendario y append diario sin navegador, Excel ni datos originales."""
from datetime import date, datetime
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from daily import ZONE, eligible_day, next_midnight
from workbench_worker import DetailsService, JobStore


class SilentProtocol:
    def emit(self, *args, **kwargs): pass


class DailyCalendarTest(unittest.TestCase):
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
