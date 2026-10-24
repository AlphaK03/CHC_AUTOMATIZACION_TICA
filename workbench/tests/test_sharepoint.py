"""Interfaz y proceso online sin cuenta, sin tocar bots ni servicios reales."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import APP, RecordingBridge
from test_details_bridge import wait_until
from demo import DemoBackend
from preferences import Preferences
from sharepoint_bridge import SharePointBridge
from PySide6.QtCore import QMetaObject, QObject, QUrl, Qt, QPointF
from PySide6.QtGui import QImage, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtQml import QQmlApplicationEngine


class SharePointTests(unittest.TestCase):
    def test_profile_photo_explorer_creation_and_activity_without_implicit_upload(self):
        class MemoryCloud(SharePointBridge):
            def send(self,command,data=None):calls.append((command,data))
            def openOnline(self,url):calls.append(('open_online',url))
        with tempfile.TemporaryDirectory() as folder:
            here=Path(__file__).resolve().parents[1];root=Path(folder);calls=[]
            if sys.platform=='win32':
                for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
                    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
            photo=root/'photo.png';picture=QImage(96,96,QImage.Format_RGB32);picture.fill(Qt.blue);picture.save(str(photo))
            cloud=MemoryCloud(root/'cloud')
            cloud._snapshot.update(connected=True,account='persona@chc.example',profile=dict(displayName='Persona de Prueba',email='persona@chc.example',photoUrl=photo.as_uri()),
                destination=dict(driveId='drive',folderId='folder',folderName='Resultados CHC',webUrl='https://test.sharepoint.com/sites/reportes/resultados'),
                localRoot=str(root/'RESULTADOS'),months=[dict(period='2026-10',label='Octubre 2026',files=12,bots=6)],queueCounts=dict(synced=10,error=1,pending=1),
                tasks=[dict(filename='BLS_MARITIMO_OCTUBRE_2026.CSV',state='synced',name='Octubre 2026',updated='2026-10-18T15:30:00Z',error=''),
                       dict(filename='TALON_OCTUBRE_2026.CSV',state='error',name='Octubre 2026',updated='2026-10-18T15:31:00Z',error='Sin acceso al destino. La copia local se conserva.')])
            bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            backend=DemoBackend(here/'modules.json',*bridges)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],sharepoint=cloud,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('detalles');engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            def find(name):return window.findChild(QObject,name)
            def click(name):QMetaObject.invokeMethod(find(name),'clicked',Qt.DirectConnection);APP.processEvents()
            def visual_all(name):
                found=[]
                def scan(item):
                    if item.objectName()==name:found.append(item)
                    for child in item.childItems():scan(child)
                scan(window.contentItem());return found
            capture=Path(os.environ['CHC_SHAREPOINT_CAPTURES']) if os.environ.get('CHC_SHAREPOINT_CAPTURES') else None
            if capture:capture.mkdir(parents=True,exist_ok=True)
            try:
                self.assertEqual(find('sharePointNavigation').property('label'),'SharePoint')
                wait_until(lambda:find('headerAccountAvatar').property('photoReady'),timeout=3000)
                click('accountProfileButton');self.assertTrue(find('accountProfileMenu').property('visible'))
                QMetaObject.invokeMethod(find('accountProfileMenu'),'close',Qt.DirectConnection)
                click('sharePointNavigation');QTest.qWait(150)
                dialog=find('sharePointDialog');self.assertEqual(dialog.property('title'),'SharePoint')
                self.assertEqual(find('sharePointDisplayName').property('text'),'Persona de Prueba')
                self.assertFalse(any(command=='upload_month' for command,_ in calls))
                for light,width,height in ((False,1280,820),(True,1000,600)):
                    window.setMinimumHeight(600);window.resize(width,height)
                    if light:QMetaObject.invokeMethod(window,'toggleTheme',Qt.DirectConnection)
                    QTest.qWait(80)
                    for item in (dialog.property('contentItem'),dialog.property('footer')):
                        origin=item.mapToScene(QPointF(0,0))
                        self.assertGreaterEqual(origin.x(),0);self.assertLessEqual(origin.x()+item.width(),width+1)
                        self.assertLessEqual(origin.y()+item.height(),height+1)
                    if capture:self.assertTrue(window.grabWindow().save(str(capture/('resultados-claro.png' if light else 'resultados-oscuro.png'))))
                click('exploreSharePoint');self.assertEqual(calls[-1],('destination_contents',None))
                cloud._browse=dict(driveId='drive',folder=dict(id='folder',name='Resultados CHC',webUrl='https://test.sharepoint.com/sites/reportes/resultados'),
                    drives=[dict(id='drive',name='Documentos')],folders=[dict(id='nested',name='BLS',folder={})],files=[dict(id='csv',name='BLS_MARITIMO_OCTUBRE_2026.CSV',file=dict(mimeType='text/csv'),size=2048,lastModifiedDateTime='2026-10-18T15:30:00Z',webUrl='https://test.sharepoint.com/sites/reportes/resultado.csv')])
                cloud.changed.emit();QTest.qWait(50)
                self.assertEqual(find('sharePointFolderList').property('count'),2)
                entry=visual_all('sharePointFileRow')[0]
                QMetaObject.invokeMethod(entry,'clicked',Qt.DirectConnection)
                self.assertEqual(calls[-1],('open_online','https://test.sharepoint.com/sites/reportes/resultado.csv'))
                if capture:self.assertTrue(window.grabWindow().save(str(capture/'archivos-claro.png')))
                click('newSharePointFolder');find('sharePointNewFolderName').setProperty('text','Nueva carpeta')
                click('createSharePointFolder')
                self.assertEqual(calls[-1],('create_folder',dict(drive='drive',item='folder',name='Nueva carpeta')))
                find('sharePointSiteSearch').setProperty('text','Reportes');click('searchSharePointSites')
                self.assertEqual(calls[-1],('sites',dict(url='https://chcconsultorescr.sharepoint.com',search='Reportes')))
                self.assertEqual(dialog.property('selectedSite'),'')
                self.assertEqual(dialog.property('driveId'),'')
                click('sharePointActivityTab');QTest.qWait(40)
                self.assertEqual(len(visual_all('sharePointTaskRow')),2)
                find('sharePointActivityFilter').setProperty('currentIndex',2);APP.processEvents()
                self.assertEqual(len(visual_all('sharePointTaskRow')),1)
                if capture:self.assertTrue(window.grabWindow().save(str(capture/'actividad-claro.png')))
                self.assertFalse(any(command in ('upload_month','retry') for command,_ in calls))
                cloud._snapshot.update(connected=False,profile={},account='');cloud.changed.emit();QTest.qWait(40)
                self.assertFalse(find('headerAccountAvatar').property('photoReady'))
                self.assertFalse(find('uploadSharePointMonth').property('enabled'))
                self.assertFalse(warnings,warnings)
            finally:
                window.setVisible(False);engine.deleteLater();APP.processEvents()

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
