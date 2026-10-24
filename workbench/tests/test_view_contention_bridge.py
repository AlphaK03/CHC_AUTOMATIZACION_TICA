"""Un fallo de lectura no convierte la descarga activa en una operación fallida."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import APP, RecordingBridge


class ViewContentionBridgeTests(unittest.TestCase):
    def active_bridge(self, module):
        bridge = RecordingBridge(module)
        bridge._busy = bridge._running = bridge._daily_active = True
        bridge._status = 'Procesando el 14/10/2026'
        bridge._view = {'rows':[{'id':'uno'}],'offset':100,'total':500}
        bridge._requests[2] = {'command':'view','tableId':'test','readonly':True}
        bridge._refresh_timer.start()
        self.addCleanup(lambda bridge=bridge: bridge._refresh_timer.stop())
        return bridge

    def test_four_profiles_keep_rows_offset_status_and_retry_after_deferred_view(self):
        for module in ('detalles','duas_transito','talon','xmovimientos'):
            with self.subTest(module=module):
                bridge = self.active_bridge(module)
                before = dict(bridge._view)
                bridge._receive(dict(event='view_deferred',command='view',requestId=2))
                bridge._receive(dict(event='idle',requestId=2,readonly=True))
                self.assertEqual(bridge._view,before)
                self.assertTrue(bridge.busy and bridge.running and bridge.dailyActive)
                self.assertTrue(bridge._refresh_timer.isActive())
                self.assertEqual(bridge.status,'Procesando el 14/10/2026')
                self.assertFalse(bridge.error)
                bridge._poll_rows()
                self.assertEqual(bridge.commands,['view'])

    def test_read_error_clears_after_success_but_real_engine_error_survives_reads(self):
        bridge = self.active_bridge('detalles')
        bridge._receive(dict(event='error',command='view',requestId=2,message='Error al leer'))
        self.assertEqual(bridge.status,'Procesando el 14/10/2026')
        self.assertTrue(bridge.running)
        reply = dict(event='result',command='view',requestId=2,view={'rows':[],'offset':100,'total':0})
        bridge._receive(reply)
        self.assertFalse(bridge.error)
        bridge._receive(dict(event='error',command='daily_run',message='Fallo real de escritura'))
        self.assertFalse(bridge.running)
        bridge._receive(dict(event='error',command='view',requestId=2,message='Otro error de lectura'))
        bridge._receive(reply)
        self.assertEqual(bridge.error,'Fallo real de escritura')
        self.assertEqual(bridge.status,'No se pudo completar la operación')


if __name__ == '__main__': unittest.main()
