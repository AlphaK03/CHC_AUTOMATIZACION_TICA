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
                captured=[]
                def capture_send(command,data=None):
                    captured.append((command,data))
                    cloud.changed.emit()  # Igual que el despacho real: puede recrear delegados.
                cloud.send=capture_send
                cloud._snapshot.update(connected=True,account='prueba@chc.example')
                dialog=find('sharePointDialog');dialog.setProperty('picking',True)
                dialog.setProperty('sites',[{'id':'site','name':'Prueba','url':'https://test.sharepoint.com/sites/prueba'}])
                window.setVisible(True);APP.processEvents()
                def visual_find(item,name):
                    if item.objectName()==name:return item
                    for child in item.childItems():
                        found=visual_find(child,name)
                        if found:return found
                location=visual_find(window.contentItem(),'sharePointKnownSite')
                self.assertIsNotNone(location)
                QMetaObject.invokeMethod(location,'clicked',Qt.DirectConnection)
                self.assertTrue(captured,(warnings,dialog.property('selectedSite'),location.property('enabled')))
                self.assertEqual(captured[-1],('site',{'url':'https://test.sharepoint.com/sites/prueba'}))
                cloud._browse={'site':{'id':'site'},'drives':[{'id':'drive','name':'Documentos'}]}
                cloud.changed.emit();APP.processEvents()
                library=visual_find(window.contentItem(),'sharePointLibrary')
                self.assertIsNotNone(library)
                QMetaObject.invokeMethod(library,'clicked',Qt.DirectConnection)
                self.assertEqual(captured[-1],('folders',{'drive':'drive','item':'root'}))
                cloud._browse={'driveId':'drive','drives':[{'id':'drive','name':'Documentos'}],
                              'folder':{'id':'folder','name':'Resultados'},'folders':[{'id':'nested','name':'Descargas'}]}
                cloud.changed.emit();APP.processEvents()
                folder_list=find('sharePointFolderList')
                self.assertEqual(folder_list.property('count'),1)
                nested=visual_find(window.contentItem(),'sharePointFolderRow')
                self.assertIsNotNone(nested)
                QMetaObject.invokeMethod(nested,'clicked',Qt.DirectConnection)
                self.assertEqual(captured[-1],('folders',{'drive':'drive','item':'nested'}))
                self.assertEqual(dialog.property('driveId'),'drive')
                cloud._browse={**cloud._browse,'folder':{'id':'nested','name':'Descargas'},'folders':[]}
                cloud.changed.emit();APP.processEvents()
                self.assertEqual(folder_list.property('count'),0)
                button=find('saveSharePointFolder');self.assertTrue(button.property('enabled'))
                QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
                self.assertEqual(captured[-1],('save',{'drive':'drive','item':'nested'}))
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
