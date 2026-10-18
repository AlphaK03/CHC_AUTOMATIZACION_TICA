"""Vista por modalidad y selección TICA exacta, sin iniciar procesos ni consultas."""
from pathlib import Path
import os
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
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine


class ManifestModesQMLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform=='win32' and os.environ.get('QT_QPA_PLATFORM')=='offscreen':
            fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','segoeuil.ttf'):
                QFontDatabase.addApplicationFont(str(fonts/name))
        APP.setFont(QFont('Segoe UI',10))

    def test_bls_modes_show_completed_and_running_at_compact_size(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);here=Path(__file__).resolve().parents[1]
            old=[DetailsBridge(enabled=False,module_id=m,storage_root=root/m) for m in
                 ('detalles','duas_transito','talon','xmovimientos')]
            bridge=MemoryBatch(module_id='bls',storage_root=root)
            service=BatchService(root,'bls',lambda *a,**k:None,Event())
            modes=[dict(mode='maritimo',label='Marítimo',total=250,succeeded=250,pending=0,running=0,rows=1833,empty=10,invalid=0),
                   dict(mode='aereo',label='Aéreo',total=120,succeeded=80,pending=39,running=1,rows=257,empty=0,invalid=0)]
            service.index.update(active='test',history=[dict(id='test',name='BLs octubre',summary=dict(
                total=370,succeeded=330,pending=39,running=1,rows=2090),modeSummaries=modes,databases=[])])
            service.processing=True
            from chc_runtime.manifest_service import bls_job
            service._jobs[331]=bls_job(331,{'IDManifiesto':'4-1-000123-P001-13/10/26','BL original':'0000123'},'Descargando',1,0,'')
            bridge.current().snapshot=service.snapshot()
            bridge.current().ready=True;bridge.current().busy=True;bridge.current().active_command='run'
            backend=DemoBackend(here/'modules.json',*old,None,bridge)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],
                                   bls=bridge,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('bls');engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            def find_all(name):
                found=[]
                def scan(item):
                    if item.objectName()==name:found.append(item)
                    for child in item.childItems():scan(child)
                scan(window.contentItem());return found
            try:
                for width,height in ((1280,820),(1000,600)):
                    window.setProperty('minimumHeight',600);window.setWidth(width);window.setHeight(height)
                    for _ in range(5):APP.processEvents()
                    summaries=find_all('manifestModeSummary')
                    self.assertEqual(len(summaries),2)
                    self.assertIn('Marítimo   ·   250/250 BLs   ·   Completado',summaries[0].property('text'))
                    self.assertIn('Aéreo   ·   80/120 BLs   ·   Descargando',summaries[1].property('text'))
                    self.assertIn('39 pendientes',summaries[1].property('text'))
                    for item in summaries:
                        self.assertTrue(item.property('visible'))
                        self.assertLessEqual(item.width(),width)
                        self.assertGreaterEqual(item.height(),item.property('implicitHeight'))
                    self.assertTrue(find_all('batchActiveJob')[0].property('text').startswith('Aéreo'))
                capture=os.environ.get('CHC_CAPTURE_BLS_MODES')
                if capture:
                    path=Path(capture);path.parent.mkdir(parents=True,exist_ok=True)
                    self.assertTrue(window.grabWindow().save(str(path)))
                modes[1].update(succeeded=120,pending=0,running=0)
                bridge.changed.emit();APP.processEvents()
                self.assertIn('120/120 BLs   ·   Completado',find_all('manifestModeSummary')[1].property('text'))
                self.assertFalse(warnings,warnings)
            finally:
                bridge.current().busy=False
                window.close();engine.deleteLater();APP.processEvents()

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
