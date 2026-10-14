"""Trabajo activo visible aunque exceda 200 filas o falle el historial auxiliar."""
from pathlib import Path
import sys
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime.manifest_service import BatchService, bls_job


class ActiveJobsTests(unittest.TestCase):
    def test_new_claims_are_emitted_immediately_and_active_jobs_always_fit_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            events = []
            service = BatchService(folder, 'bls', lambda kind, **data: events.append(data), Event())
            service.index['history'] = [{'id': 'one', 'name': 'Prueba', 'summary': {}, 'databases': []}]
            service.index['active'] = 'one'
            service.processing = True
            for n in range(1, 501):
                service._jobs[n] = bls_job(n, {'IDManifiesto': 'M', 'BL original': str(n)}, 'Guardado', 1, 1, '')
            service._last_event = service._last_save = time.monotonic()
            for n in (9001, 9002):
                service.progress({'total': 10000, 'saved': 500, 'pending': 9498, 'running': 2,
                                  'job': {'ordinal': n, 'manifest': 'M', 'bl': str(n), 'state': 'Descargando',
                                          'attempts': 1, 'page': 3, 'checkpointPage': 2, 'collectedRows': 100}})
            self.assertEqual(len(events), 2)
            snapshot = events[-1]['snapshot']
            self.assertEqual([j['ordinal'] for j in snapshot['jobs'][:2]], [9001, 9002])
            self.assertEqual([j['collectedRows'] for j in snapshot['activeJobs']], [100, 100])
            service.processing = False
            self.assertEqual(service.snapshot()['activeJobs'], [])

    def test_auxiliary_history_lock_does_not_abort_progress_or_lose_current_job(self):
        with tempfile.TemporaryDirectory() as folder:
            events = []
            service = BatchService(folder, 'bls', lambda kind, **data: events.append(data), Event())
            service.index['history'] = [{'id': 'one', 'name': 'Prueba', 'summary': {}, 'databases': []}]
            service.index['active'] = 'one'
            service.processing = True
            with patch.object(service, 'save', side_effect=PermissionError('Archivo abierto por otro lector')):
                with self.assertLogs(level='ERROR'):
                    service.progress({'total': 1, 'saved': 0, 'pending': 0, 'running': 1,
                                      'job': {'ordinal': 1, 'manifest': 'M', 'bl': '0001', 'state': 'Descargando'}})
            self.assertEqual(events[-1]['snapshot']['activeJobs'][0]['bl'], '0001')
            service.progress({'phase': 'internet_wait', 'message': 'Esperando conexión'})
            self.assertEqual(service.snapshot()['message'], 'Esperando conexión')


if __name__ == '__main__':
    unittest.main()
