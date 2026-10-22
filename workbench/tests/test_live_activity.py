"""El reloj distingue espera de señal real y no reconstruye las etapas activas."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP
from live_activity import LiveActivity


class LiveTests(unittest.TestCase):
    def test_elapsed_stale_signal_and_incremental_model(self):
        now=[100.0];monitor=LiveActivity(clock=lambda:now[0]);resets=[];changes=[]
        monitor.model.modelReset.connect(lambda:resets.append(1))
        monitor.model.dataChanged.connect(lambda *args:changes.append(1))
        monitor.begin();self.assertEqual(monitor.status,'Esperando al motor')
        monitor.accept(dict(event='activity_state',running=True,operations=[dict(key='1',label='Esperando HTTP',subject='001',elapsed=3)]))
        now[0]+=12;monitor.tick()
        self.assertEqual(monitor.operations[0]['elapsed'],15)
        self.assertIn('Sin señales',monitor.status)
        self.assertTrue(changes);self.assertFalse(resets)
        monitor.accept(dict(event='log',message='Se recibió respuesta'))
        self.assertIn('hace 0 s',monitor.status)
        monitor.accept(dict(event='activity_state',running=False,operations=[]))
        self.assertFalse(monitor.running);self.assertEqual(monitor.model.rowCount(),0)
        self.assertFalse(monitor.timer.isActive())

    def test_readonly_idle_cannot_hide_dua_operation(self):
        from details_bridge import DetailsBridge
        bridge=DetailsBridge(enabled=False)
        bridge._receive(dict(event='activity_state',running=True,operations=[dict(key='1',label='Consultando DUA',elapsed=1)]))
        bridge._receive(dict(event='idle',readonly=True))
        self.assertTrue(bridge.consoleMonitor.running)
        bridge._receive(dict(event='idle',readonly=False))
        self.assertFalse(bridge.consoleMonitor.running)


if __name__=='__main__':unittest.main()
