"""Botón visible real → proceso propio → portal local → actualización SQLite."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until,DetailsBridge,DemoBackend,Preferences
from batch_bridge import BatchBridge
from PySide6.QtCore import QObject,QMetaObject,QUrl,Qt
from PySide6.QtQml import QQmlApplicationEngine


class RefreshSavedQMLTests(unittest.TestCase):
    def test_purple_button_two_flows_progress_and_manual_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            bridge=BatchBridge(storage_root=root/'manifiestos',offline_fixture=True)
            bls=BatchBridge(module_id='bls',enabled=False,storage_root=root/'bls',offline_fixture=True)
            details=[DetailsBridge(enabled=False,module_id=m,storage_root=root/m)
                     for m in ('detalles','duas_transito','talon','xmovimientos')]
            here=Path(__file__).resolve().parents[1]
            backend=DemoBackend(here/'modules.json',*details,bridge,bls)
            engine=QQmlApplicationEngine(); warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=details[0],transit=details[1],talon=details[2],movements=details[3],
                    manifests=bridge,bls=bls,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('manifiestos')
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            events=[]
            bridge.eventReceived.connect(events.append)
            try:
                for flow in ('conocimientos','duas'):
                    bridge.setFlow(flow)
                    wait_until(lambda:bridge.ready and not bridge.busy)
                    self.assertTrue(bridge.command('run',dict(config=dict(year=2026,month=9,modes=['maritimo'],
                        headless=True,workers=2,timeout=5))))
                    wait_until(lambda:not bridge.busy)
                    self.assertFalse(bridge.error,bridge.error)
                    self.assertFalse(bridge.refreshSaved)
                    button=window.findChild(QObject,'manifestRefreshSaved')
                    self.assertTrue(button.property('visible'))
                    self.assertTrue(button.property('enabled'))
                    self.assertEqual(button.property('background').property('color').name(),'#7c3aed')
                    before=bridge.summary['rows']
                    self.assertTrue(QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection))
                    self.assertTrue(bridge.busy)
                    self.assertFalse(button.property('enabled'))
                    wait_until(lambda:not bridge.busy,timeout=30000)
                    self.assertFalse(bridge.error,bridge.error+'\n'+bridge.current().stderr)
                    self.assertEqual(bridge.summary['rows'],before+1)
                    self.assertEqual(bridge.refreshSaved['updated'],1)
                    self.assertEqual(bridge.refreshSaved['processed'],2)
                    self.assertIn('min',window.findChild(QObject,'manifestRefreshSavedProgress').property('text'))
                self.assertTrue(any(e.get('snapshot',{}).get('activeJobs') for e in events))
                self.assertFalse(list(root.rglob('*.CSV')))
                self.assertFalse(warnings,warnings)
            finally:
                window.close();engine.deleteLater();APP.processEvents()
                bridge.shutdown();bls.shutdown()
                wait_until(lambda:bridge.isClosed and bls.isClosed)


if __name__=='__main__':unittest.main()
