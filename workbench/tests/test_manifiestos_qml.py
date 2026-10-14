"""Botones QML reales: iniciar, generar base y enviarla a BLs sin archivos manuales."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until, DetailsBridge, DemoBackend, Preferences
from batch_bridge import BatchBridge
from PySide6.QtCore import QObject,QMetaObject,QUrl,Qt
from PySide6.QtQml import QQmlApplicationEngine


class ManifestQMLTests(unittest.TestCase):
    def test_buttons_connect_download_to_bls(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            manifests=BatchBridge(storage_root=root/'manifiestos',offline_fixture=True)
            bls=BatchBridge(module_id='bls',storage_root=root/'bls',offline_fixture=True)
            old=[DetailsBridge(enabled=False,module_id=module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            here=Path(__file__).resolve().parents[1]
            backend=DemoBackend(here/'modules.json',*old,manifests,bls)
            preferences=Preferences(root/'prefs.json',persist=False)
            engine=QQmlApplicationEngine()
            warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],
                                   manifests=manifests,bls=bls,preferences=preferences).items():
                engine.rootContext().setContextProperty(name,value)
            window=None
            def click(name):
                button=window.findChild(QObject,name)
                self.assertIsNotNone(button,name)
                wait_until(lambda:button.property('enabled'),timeout=2000)
                self.assertTrue(button.property('enabled'),name)
                self.assertTrue(QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection))
            try:
                manifests.command('configure',{'config':{'year':2026,'month':10,'headless':True,'timeout':5,'workers':1}})
                wait_until(lambda:manifests.ready and not manifests.busy)
                backend.navigate('manifiestos')
                engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
                self.assertTrue(engine.rootObjects(),warnings)
                window=engine.rootObjects()[0]
                wait_until(lambda:manifests.ready and not manifests.busy)
                name=window.findChild(QObject,'manifestTableName')
                self.assertTrue(name.property('readOnly'))
                self.assertEqual(name.property('text'),'octubre26')
                self.assertTrue(manifests.command('configure',{'config':{'year':2027,'month':1}}))
                wait_until(lambda:not manifests.busy)
                self.assertEqual(manifests.config['year'],2027,manifests.error)
                self.assertEqual(window.findChild(QObject,'manifestYear').property('value'),2027,warnings)
                wait_until(lambda:name.property('text')=='enero27',timeout=2000)
                self.assertEqual(name.property('text'),'enero27')
                self.assertTrue(manifests.command('configure',{'config':{'year':2026,'month':10}}))
                wait_until(lambda:not manifests.busy)
                wait_until(lambda:name.property('text')=='octubre26',timeout=2000)
                click('manifestStart')
                wait_until(lambda:not manifests.busy,timeout=15000)
                self.assertEqual(manifests.summary['succeeded'],2,manifests.error)
                dialog=window.findChild(QObject,'manifestBaseDialog')
                self.assertTrue(QMetaObject.invokeMethod(dialog,'open',Qt.DirectConnection))
                APP.processEvents()
                click('baseLoad')
                wait_until(lambda:not manifests.baseBusy,timeout=10000)
                self.assertFalse(manifests.baseError,manifests.baseError)
                click('baseBuild')
                wait_until(lambda:not manifests.baseBusy,timeout=10000)
                self.assertFalse(manifests.baseError,manifests.baseError)
                self.assertTrue(Path(manifests.lastBase).is_file())
                click('baseTransfer')
                wait_until(lambda:backend.route=='bls' and bls.ready and not bls.busy)
                self.assertEqual(bls.config['input'],manifests.lastBase)
                click('manifestStart')
                wait_until(lambda:not bls.busy,timeout=10000)
                self.assertEqual(bls.summary['succeeded'],2,bls.error)
                self.assertFalse(warnings,warnings)
            finally:
                manifests.shutdown(); bls.shutdown()
                wait_until(lambda:manifests.isClosed and bls.isClosed)
                if window: window.close()
                engine.deleteLater()
                APP.processEvents()


if __name__=='__main__': unittest.main()
