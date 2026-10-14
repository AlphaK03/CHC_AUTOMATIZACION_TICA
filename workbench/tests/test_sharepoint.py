"""Interfaz y proceso online sin cuenta, sin tocar bots ni servicios reales."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import APP, RecordingBridge
from test_details_bridge import wait_until
from demo import DemoBackend
from preferences import Preferences
from sharepoint_bridge import SharePointBridge
from PySide6.QtCore import QMetaObject, QObject, QUrl, Qt
from PySide6.QtQml import QQmlApplicationEngine


class SharePointTests(unittest.TestCase):
    def test_dialog_and_worker_without_account_and_folder_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            here=Path(__file__).resolve().parents[1]
            cloud=SharePointBridge(Path(folder)/'cloud')
            bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            backend=DemoBackend(here/'modules.json',*bridges)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],sharepoint=cloud,preferences=Preferences(Path(folder)/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('detalles');engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            def find(name):
                return window.findChild(QObject,name)
            try:
                QMetaObject.invokeMethod(find('sharePointNavigation'),'clicked',Qt.DirectConnection)
                wait_until(lambda: cloud._ready and not cloud.busy,timeout=8000)
                self.assertFalse(cloud.connected);self.assertEqual(cloud.error,'')
                self.assertTrue(find('connectSharePoint').property('enabled'))
                # Datos de navegación sintéticos; impedir toda llamada de red.
                captured=[];cloud.send=lambda command,data=None:captured.append((command,data))
                cloud._snapshot.update(connected=True,account='prueba@chc.example')
                cloud._browse={'driveId':'drive','drives':[{'id':'drive','name':'Documentos'}],
                              'folder':{'id':'folder','name':'Resultados'},'folders':[]}
                cloud.changed.emit();APP.processEvents()
                dialog=find('sharePointDialog');dialog.setProperty('driveId','drive');dialog.setProperty('picking',True)
                APP.processEvents()
                button=find('saveSharePointFolder');self.assertTrue(button.property('enabled'))
                QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
                self.assertEqual(captured[-1],('save',{'drive':'drive','item':'folder'}))
                self.assertFalse(find('uploadSharePointMonth').property('enabled'))
                cloud._snapshot.update(destination={'folderId':'folder'},months=[{'period':'2026-09','label':'Septiembre 2026','files':1}])
                cloud.changed.emit();APP.processEvents();dialog.setProperty('picking',False)
                button=find('uploadSharePointMonth');self.assertTrue(button.property('enabled'))
                QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
                self.assertEqual(captured[-1],('upload_month',{'month':'2026-09'}))
                self.assertFalse(warnings,warnings)
            finally:
                cloud.shutdown();wait_until(lambda:cloud.isClosed,timeout=8000)
                window.setVisible(False);engine.deleteLater();APP.processEvents()

    def test_tokens_are_encrypted_by_windows(self):
        from msal_extensions import FilePersistenceWithDataProtection
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tokens.dpapi'
            cache=FilePersistenceWithDataProtection(str(path))
            cache.save('non-secret-test-marker')
            self.assertNotIn(b'non-secret-test-marker',path.read_bytes())
            self.assertEqual(cache.load(),'non-secret-test-marker')


if __name__=='__main__':unittest.main()
