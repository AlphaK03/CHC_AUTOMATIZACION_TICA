"""Los trabajos activos se ven fuera del historial sin iniciar motores."""
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_qml_events import APP, RecordingBridge
from batch_bridge import BatchBridge
from demo import DemoBackend
from preferences import Preferences
from PySide6.QtCore import QObject, QUrl, QMetaObject, Qt
from PySide6.QtQml import QQmlApplicationEngine
from chc_runtime.manifest_service import BatchService, bls_job


class MemoryBatch(BatchBridge):
    def connectModule(self):
        pass

    def refreshKnowledge(self):
        pass


class ActiveQMLTests(unittest.TestCase):
    def test_bls_pages_rows_and_dua_current_jobs_are_visible_and_empty_has_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            here=Path(__file__).resolve().parents[1]
            bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            bls=MemoryBatch(module_id='bls',storage_root=root)
            service=BatchService(root,'bls',lambda *a,**k:None,Event())
            service.index['active']='one'
            service.index['history']=[{'id':'one','name':'Prueba','summary':{'total':1000,'running':1},'databases':[]}]
            service.processing=True
            job=bls_job(900,{'IDManifiesto':'1-0-00001-A01-01/09/26','BL original':'0000123'},'Descargando',2,0,'')
            job.update(page=3,checkpointPage=2,collectedRows=100)
            service._jobs[900]=job
            bls.current().snapshot=service.snapshot()
            bls.current().ready=bls.current().busy=True
            backend=DemoBackend(here/'modules.json',*bridges,None,bls)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],bls=bls,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('bls')
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            def find(name):
                def scan(item):
                    if item.objectName()==name:return item
                    for child in item.childItems():
                        result=scan(child)
                        if result:return result
                    return None
                return scan(window.contentItem())
            try:
                APP.processEvents()
                text=find('batchActiveJob')
                self.assertIsNotNone(text,warnings)
                self.assertTrue(text.property('visible'))
                self.assertIn('0000123',text.property('text'))
                self.assertIn('Página 3',text.property('text'))
                self.assertIn('100 filas',text.property('text'))
                captured=[]
                bls._review.open=lambda request:captured.append(request)
                button=find('batchOpenTica')
                self.assertTrue(button.property('enabled'))
                QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
                self.assertEqual(captured,[{'flow':'bls','recordId':'one','jobId':job['id'],'ordinal':900}])
                movements=bridges[3]
                movements._running=True
                movements._snapshot['summary'].update(active_duas=['001-2026-000001'],empty=1,succeeded=0,total=2)
                backend.navigate('xmovimientos'); APP.processEvents()
                text=window.findChild(QObject,'detailsActiveJobs')
                self.assertIn('001-2026-000001',text.property('text'))
                self.assertTrue(text.property('visible'))
                button=window.findChild(QObject,'retryEmptyButton')
                self.assertIsNotNone(button)
                self.assertFalse(warnings,warnings)
            finally:
                window.close();engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
