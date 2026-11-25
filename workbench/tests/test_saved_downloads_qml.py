"""Filtrar y seleccionar varios lotes, generar y subir sin buscar archivos."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import APP,RecordingBridge
from test_details_bridge import wait_until
from test_csv_exports import Endpoint
from csv_exports import CsvExports
from demo import DemoBackend
from preferences import Preferences
from sharepoint_bridge import SharePointBridge
from chc_cloud.service import CloudService,TARGETS
from chc_cloud.tests.test_service import Account,Graph
from chc_cloud.tests.test_download_catalog import manifest_history
from chc_runtime import output_layout
from PySide6.QtCore import QObject,QUrl,QMetaObject,QPointF,Qt,QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest


class SavedDownloadsQmlTests(unittest.TestCase):
    def test_filters_multiselection_generation_and_separate_month_routes(self):
        class MemoryCloud(SharePointBridge):
            def send(self,command,data=None):
                calls.append((command,data))
                try:self._snapshot=service.execute({'command':command,**(data or {})})['snapshot'];self._error=''
                except ValueError as error:self._error=str(error)
                self.changed.emit()

        class ExportEndpoint(Endpoint):
            def send(self,command,data):
                self.calls.append((command,data));self.busy=True
                def done():
                    for key in data['recordIds']:
                        record=next(record for record in history if record['id']==key)
                        spec=output_layout.manifest_spec('contenedores',record,'maritimo')
                        output_layout.publish(source,root/'RESULTADOS',spec,'contenedores:'+key,service.exports_registry)
                    self.busy=False
                    self.eventReceived.emit({'event':'result','command':command,'exportReport':{
                        'token':data['exportToken'],'exported':len(data['recordIds']),'errors':[]}})
                QTimer.singleShot(0,done)
                return True

        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);here=Path(__file__).resolve().parents[1]
            bot=root/'bots/manifiestos';history,session=manifest_history(bot);before=session.read_bytes()
            graph=Graph();calls=[]
            service=CloudService(root/'cloud',{},Account(),graph,monthly=lambda:{'rows':[]},roots={'manifiestos':bot})
            service.execute({'command':'local_root','path':str(root/'RESULTADOS')})
            service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
            service.save_destination('drive','folder')
            source=root/'data.csv';source.write_bytes(b'DUA\r\n00001\r\n')
            cloud=MemoryCloud(root/'cloud');cloud._snapshot=service.snapshot()
            endpoint=ExportEndpoint()
            exporter=CsvExports({'manifiestos':SimpleNamespace(enabled=True,channels={'contenedores':endpoint},closing=False)})
            cloud.setCsvExporter(exporter)
            bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            backend=DemoBackend(here/'modules.json',*bridges)
            if sys.platform=='win32':
                for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
                    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda items:warnings.extend(w.toString() for w in items))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],
                    sharepoint=cloud,preferences=Preferences(root/'prefs',persist=False)).items():engine.rootContext().setContextProperty(name,value)
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            def find(name):return window.findChild(QObject,name)
            def click(name):QMetaObject.invokeMethod(find(name),'clicked',Qt.DirectConnection);APP.processEvents()
            captures=Path(os.environ['CHC_SAVED_DOWNLOADS_CAPTURES']) if os.environ.get('CHC_SAVED_DOWNLOADS_CAPTURES') else None
            if captures:captures.mkdir(parents=True,exist_ok=True)
            try:
                click('sharePointNavigation');click('chooseSavedDownloads')
                dialog=find('savedDownloadsDialog');self.assertTrue(dialog.property('visible'))
                self.assertEqual(find('savedDownloadsList').property('count'),3)
                self.assertFalse(endpoint.calls);self.assertFalse(graph.sent)
                find('savedDownloadsTarget').setProperty('currentIndex',1+next(i for i,v in enumerate(TARGETS) if v[0]=='manifiestos:contenedores'))
                find('savedDownloadsYear').setProperty('text','2026')
                for month in (7,8):
                    find('savedDownloadsMonth').setProperty('currentIndex',month);APP.processEvents()
                    self.assertEqual(find('savedDownloadsList').property('count'),1)
                    click('selectVisibleDownloads')
                self.assertEqual(len(dialog.property('selected').toVariant()),2)
                self.assertFalse(find('uploadSelectedDownloads').property('enabled'))
                self.assertTrue(find('generateSelectedDownloads').property('enabled'))
                click('generateSelectedDownloads')
                wait_until(lambda:not exporter.busy)
                self.assertEqual(endpoint.calls[0][0],'export_selected')
                self.assertEqual(endpoint.calls[0][1]['recordIds'],['record-7','record-8'])
                self.assertEqual(len(dialog.property('selected').toVariant()),2)
                self.assertFalse(graph.sent,'Generar CSV nunca inicia subidas.')
                self.assertTrue(find('uploadSelectedDownloads').property('enabled'),cloud.error)
                find('savedDownloadsMonth').setProperty('currentIndex',0);APP.processEvents()
                for width,height in ((1280,774),(1000,680),(1000,600)):
                    window.setMinimumHeight(600);window.resize(width,height);QTest.qWait(60)
                    view=find('savedDownloadsList')
                    self.assertGreaterEqual(view.height(),172,'Deben caber dos filas.')
                    for name in ('generateSelectedDownloads','uploadSelectedDownloads'):
                        button=find(name);point=button.mapToScene(QPointF(button.width()/2,button.height()/2))
                        self.assertGreaterEqual(point.x(),0);self.assertLess(point.x(),width)
                        self.assertGreaterEqual(point.y(),0);self.assertLess(point.y(),height)
                    if captures:self.assertTrue(window.grabWindow().save(str(captures/f'{width}x{height}-descargas.png')))
                button=find('uploadSelectedDownloads');point=button.mapToScene(QPointF(button.width()/2,button.height()/2))
                QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point.toPoint());APP.processEvents()
                self.assertEqual(calls[-1][0],'upload_downloads')
                self.assertEqual({item[0] for item in graph.sent},{'MANIFIESTOS_CONTENEDORES_MARITIMO_JULIO_2026.CSV','MANIFIESTOS_CONTENEDORES_MARITIMO_AGOSTO_2026.CSV'})
                self.assertEqual(session.read_bytes(),before)
                self.assertFalse(warnings,warnings)
            finally:
                exporter.cancel();service.db.close()
                window.close();engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
