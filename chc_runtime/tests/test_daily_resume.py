"""Reanudación sin mover el origen y ciclo continuo hasta las 00:01 de Costa Rica."""
from datetime import date, datetime
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import tempfile
import unittest

from chc_runtime.daily import DailyCoordinator, ZONE


class DailyResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 10, 31, 18, 0, tzinfo=ZONE)
        self.service = SimpleNamespace(root=Path(self.temp.name), stop_event=Event(),
            machine={'daily_mode': True, 'daily_start_date': '2026-10-28', 'daily_end_date': '2026-10-28'},
            protocol=SimpleNamespace(emit=lambda *a, **k: None), snapshot=lambda: {},
            local_root=lambda: Path(self.temp.name) / 'output')
        self.daily = DailyCoordinator(self.service, offline=True, now=lambda: self.now)

    def test_snapshot_after_restart_finds_hole_and_preserves_origin_without_writing(self):
        for day, state in ((28, 'completed'), (29, 'omitted')):
            self.daily.ledger.update(date(2026, 10, day), state=state)
        fresh = DailyCoordinator(self.service, offline=True, now=lambda: self.now)
        before = fresh.ledger.path.read_bytes()
        snapshot = fresh.snapshot()
        self.assertEqual((snapshot['resumeDate'], snapshot['resumeEndDate']), ('2026-10-30', '2026-10-30'))
        self.assertFalse(snapshot['waitingForDay'])
        self.assertEqual(snapshot['startDate'], '2026-10-28')
        self.assertEqual(fresh.ledger.path.read_bytes(), before)
        self.assertFalse(fresh.active)

    def test_continues_past_saved_end_waits_and_crosses_month_at_0001(self):
        self.daily.ledger.update(date(2026, 10, 28), state='completed')
        calls, waits = [], []
        def cycle(day):
            calls.append(day)
            self.daily.ledger.update(day, state='completed')
            return True
        self.daily.cycle = cycle
        def emit(event, **values):
            if event == 'daily' and values['daily']['phase'] == 'waiting':
                waits.append(values['daily'])
                if len(waits) == 1:
                    self.now = datetime(2026, 11, 1, 0, 0, tzinfo=ZONE)
                elif len(waits) == 2:
                    self.now = datetime(2026, 11, 1, 0, 1, tzinfo=ZONE)
                else:
                    self.service.stop_event.set()
        self.service.protocol.emit = emit
        self.service.stop_event.wait = lambda timeout: self.service.stop_event.is_set()
        self.daily.run()
        self.assertEqual(calls, [date(2026, 10, 29), date(2026, 10, 30), date(2026, 10, 31)])
        self.assertEqual([s['wakeAt'] for s in waits],
            ['2026-11-01T00:01:00-06:00', '2026-11-01T00:01:00-06:00', '2026-11-02T00:01:00-06:00'])
        self.assertTrue(all(s['waitingForDay'] for s in waits))
        self.assertEqual(waits[-1]['resumeDate'], '2026-11-01')
        self.assertEqual(self.service.machine['daily_start_date'], '2026-10-28')
        self.assertEqual(self.service.machine['daily_end_date'], '2026-10-28')

    def test_bounded_month_finishes_without_processing_later_available_days(self):
        calls = []
        def cycle(day):
            calls.append(day)
            self.daily.ledger.update(day, state='completed')
            return True
        self.daily.cycle = cycle
        result = self.daily.run(bounded=True)
        self.assertEqual(calls, [date(2026, 10, 28)])
        self.assertEqual(result['runStatus'], 'completed')


if __name__ == '__main__':
    unittest.main()
