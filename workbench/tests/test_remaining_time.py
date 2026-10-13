"""Comprobación puntual del cálculo; reloj simulado, sin consultas ni esperas."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remaining_time import RemainingTime


class RemainingTimeTest(unittest.TestCase):
    def test_real_rate_excludes_previously_saved_results_and_invalid_inputs(self):
        now = [0]
        eta = RemainingTime(lambda: now[0])
        summary = dict(succeeded=500, pending=100, running=0, retry=0, invalid=7)
        eta.reset(summary)
        self.assertIsNone(eta.seconds(summary, workers=5))
        now[0] = 20
        summary.update(succeeded=510, pending=90)
        self.assertAlmostEqual(eta.seconds(summary, workers=5), 180)
        now[0] = 40
        summary.update(succeeded=512, pending=88)
        self.assertGreater(eta.seconds(summary, workers=5), 180)
        now[0] = 105  # No further confirmations: suppress stale estimates.
        self.assertIsNone(eta.seconds(summary, workers=5))
        eta.reset(summary)  # Resume must measure its own elapsed time.
        self.assertIsNone(eta.seconds(summary, workers=5))
        summary.update(pending=0, running=0, retry=0)
        self.assertEqual(eta.label(summary), 'Finalizando…')


if __name__ == '__main__':
    unittest.main()
