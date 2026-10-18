"""Vista por modalidad y selección TICA exacta, sin iniciar procesos ni consultas."""
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_active_jobs_qml import APP, MemoryBatch
from details_bridge import DetailsBridge
from demo import DemoBackend
from preferences import Preferences
from chc_runtime.manifest_service import BatchService
from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_ARG, Qt
from PySide6.QtQml import QQmlApplicationEngine


class ManifestModesQMLTests(unittest.TestCase):
    def test_two_listados_labels_counts_filter_and_tica_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            here=Path(__file__).resolve().parents[1]
            old=[DetailsBridge(enabled=False,module_id=m,storage_root=root/m) for m in
                 ('detalles','duas_transito','talon','xmovimientos')]
            bridge=MemoryBatch(storage_root=root)
            service=BatchService(root,'tabla',lambda *a,**k:None,Event())
            service.index['history']=[dict(id='test',name='octubre26',summary={},databases=[])]
            service.index['active']='test'
            for mode,rows in (('maritimo',1833),('aereo',257)):
                service.progress(dict(database=str(root/(mode+'.sqlite3')),mode=mode,
                    progress=dict(selected=1,saved=1,pending=0,active=0,excluded=0),
                    job=dict(id='listado',ordinal=1,state='Guardado',attempts=1,kept=rows)))
            bridge._flow='tabla'
            bridge.current().snapshot=service.snapshot()
            bridge.current().ready=True
            backend=DemoBackend(here/'modules.json',*old,bridge)
            engine=QQmlApplicationEngine(); warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],
                                   manifests=bridge,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('manifiestos')
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            def find_all(name):
                result=[]
                def scan(item):
                    if item.objectName()==name:result.append(item)
                    for child in item.childItems():scan(child)
                scan(window.contentItem())
                return result
            try:
                APP.processEvents()
                self.assertEqual([item.property('text') for item in find_all('manifestJobMode')],['Marítimo','Aéreo'])
                summaries=[item.property('text') for item in find_all('manifestModeSummary')]
                self.assertTrue(any('Marítimo' in text and '1833 filas' in text for text in summaries),summaries)
                self.assertTrue(any('Aéreo' in text and '257 filas' in text for text in summaries),summaries)
                captured=[]
                bridge._review.open=lambda request:captured.append(request)
                buttons=find_all('batchOpenTica')
                self.assertEqual(len(buttons),2)
                QMetaObject.invokeMethod(buttons[1],'clicked',Qt.DirectConnection)
                self.assertEqual(captured,[dict(flow='tabla',recordId='test',jobId='listado',ordinal=1,
                                               database=str(root/'aereo.sqlite3'))])
                commands=[]
                bridge.current().send=lambda command,data=None:commands.append((command,data)) or True
                select=window.findChild(QObject,'manifestModeFilter')
                select.setProperty('currentIndex',2)
                QMetaObject.invokeMethod(select,'activated',Qt.DirectConnection,Q_ARG(int,2))
                self.assertEqual(commands[-1],('view',dict(search='',offset=0,mode='aereo')))
                # Filtrar resultados no debe reemplazar una configuración aún sin guardar.
                year=window.findChild(QObject,'manifestYear')
                year.setProperty('value',2027)
                bridge.current().snapshot['viewMode']='aereo'
                bridge.eventReceived.emit(dict(flow='tabla',event='result',command='view'))
                APP.processEvents()
                self.assertEqual(year.property('value'),2027)
                self.assertFalse(warnings,warnings)
            finally:
                window.close();engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
