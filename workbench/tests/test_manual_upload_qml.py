"""Elegir, revisar y subir un solo CSV con Graph simulado y QML real."""
import os
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
from chc_cloud.service import CloudService
from chc_cloud.tests.test_service import Account, Graph
from PySide6.QtCore import QObject, QUrl, QMetaObject, QPointF, Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest


class ManualUploadQmlTests(unittest.TestCase):
    def test_real_worker_inspects_local_csv_without_account_and_refuses_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'Contenedores_julio26.csv'
            source.write_bytes(b'Numero\r\n00001\r\n')
            bridge=SharePointBridge(root/'cloud')
            try:
                bridge.inspectUpload(source.as_uri())
                wait_until(lambda:not bridge.busy and bool(bridge.manualUpload or bridge.error))
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.manualUpload['target'],'manifiestos:contenedores')
                self.assertEqual(bridge.manualUpload['period'],'2026-07')
                self.assertFalse(bridge.connected)
                bridge.uploadFile(bridge.manualUpload['token'])
                wait_until(lambda:not bridge.busy)
                self.assertIn('Conecta',bridge.error)
                self.assertEqual(source.read_bytes(),b'Numero\r\n00001\r\n')
                self.assertFalse(list((root/'cloud/spool').glob('*.csv')))
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)

    def test_individual_files_work_without_ready_month_and_review_never_uploads(self):
        class MemoryCloud(SharePointBridge):
            def send(self,command,data=None):
                calls.append((command,data))
                try:
                    result=backend_service.execute({'command':command,**(data or {})})
                    self._snapshot=result['snapshot'];self._error=''
                except ValueError as error:
                    self._error=str(error)
                self.changed.emit()

        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);here=Path(__file__).resolve().parents[1]
            graph=Graph();calls=[]
            backend_service=CloudService(root/'cloud',{},Account(),graph,monthly=lambda:{'rows':[]})
            backend_service.execute({'command':'local_root','path':str(root/'RESULTADOS')})
            backend_service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
            backend_service.save_destination('drive','folder')
            cloud=MemoryCloud(root/'cloud');cloud._snapshot=backend_service.snapshot()
            bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            backend=DemoBackend(here/'modules.json',*bridges)
            if sys.platform=='win32':
                for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
                    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda items:warnings.extend(w.toString() for w in items))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],
                    sharepoint=cloud,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            def find(name):return window.findChild(QObject,name)
            def invoke(name):QMetaObject.invokeMethod(find(name),'clicked',Qt.DirectConnection);APP.processEvents()
            capture=Path(os.environ['CHC_MANUAL_UPLOAD_CAPTURES']) if os.environ.get('CHC_MANUAL_UPLOAD_CAPTURES') else None
            if capture:capture.mkdir(parents=True,exist_ok=True)
            try:
                invoke('sharePointNavigation')
                self.assertTrue(find('chooseIndividualCsv').property('enabled'))
                self.assertEqual(cloud.months,[])
                for width,height,name,period in ((1280,774,'Contenedores_julio26.CSV','JULIO_2026'),
                        (1000,680,'Contenedores_agosto26.CSV','AGOSTO_2026'),
                        (1000,600,'Contenedores_julio26.CSV','JULIO_2026')):
                    window.setMinimumHeight(600);window.resize(width,height)
                    path=root/name;path.write_bytes(b'Numero\r\n00001\r\n')
                    cloud.inspectUpload(path.as_uri())
                    dialog=find('manualUploadDialog');wait_until(lambda:dialog.property('visible'))
                    self.assertIn(period,find('manualUploadPreview').property('text'))
                    self.assertEqual(find('manualUploadSubmit').property('text'),'Subir este CSV')
                    self.assertTrue(find('manualUploadSubmit').property('enabled'))
                    count=len(graph.sent)
                    APP.processEvents();QTest.qWait(60)
                    self.assertEqual(len(graph.sent),count,'Inspeccionar/abrir no sube el CSV.')
                    submit=find('manualUploadSubmit')
                    point=submit.mapToScene(QPointF(submit.width()/2,submit.height()/2))
                    self.assertGreaterEqual(point.x(),0);self.assertLess(point.x(),width)
                    self.assertGreaterEqual(point.y(),0);self.assertLess(point.y(),height)
                    if capture:self.assertTrue(window.grabWindow().save(str(capture/f'{width}x{height}-individual.png')))
                    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point.toPoint())
                    wait_until(lambda:not dialog.property('visible'))
                    self.assertEqual(calls[-1][0],'upload_file')
                    self.assertEqual(graph.sent[-1][1],path.read_bytes())
                    self.assertFalse(cloud.months)
                path=root/'reporte.csv';path.write_bytes(b'Numero\n00002\n')
                cloud.inspectUpload(path.as_uri());wait_until(lambda:find('manualUploadDialog').property('visible'))
                self.assertFalse(find('manualUploadSubmit').property('enabled'))
                find('manualUploadDialog').setProperty('chosenTarget','manifiestos:contenedores')
                find('manualUploadMonth').setProperty('currentIndex',8)
                find('manualUploadYear').setProperty('value',2026)
                APP.processEvents();count=len(graph.sent)
                self.assertEqual(find('manualUploadSubmit').property('text'),'Revisar destino')
                invoke('manualUploadSubmit')
                self.assertEqual(calls[-1][0],'review_upload')
                self.assertEqual(len(graph.sent),count)
                self.assertIn('AGOSTO_2026',find('manualUploadPreview').property('text'))
                invoke('manualUploadSubmit')
                self.assertEqual(calls[-1][0],'upload_file')
                self.assertEqual(len(graph.sent),count+1)
                self.assertFalse(warnings,warnings)
            finally:
                backend_service.db.close()
                window.close();engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
