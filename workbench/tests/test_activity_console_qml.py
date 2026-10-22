"""Consola común en seis bots y cinco procedimientos, sin iniciar motores."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import APP, RecordingBridge
from test_details_bridge import wait_until
from test_active_jobs_qml import MemoryBatch
from batch_bridge import EMPTY
from demo import DemoBackend
from preferences import Preferences
from PySide6.QtCore import QObject,QUrl,QPointF,QMetaObject,Qt
from PySide6.QtGui import QFont,QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine


class ActivityConsoleQMLTests(unittest.TestCase):
    def test_all_profiles_fit_and_updates_preserve_scrolled_operations(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);here=Path(__file__).resolve().parents[1]
            if sys.platform=='win32':
                fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
                for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','consola.ttf'):
                    QFontDatabase.addApplicationFont(str(fonts/name))
            APP.setFont(QFont('Segoe UI',10))
            bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
            manifests=MemoryBatch(storage_root=root/'manifiestos')
            bls=MemoryBatch(module_id='bls',storage_root=root/'bls')
            for bridge in (manifests,bls):
                for channel in bridge.channels.values():
                    channel.snapshot=deepcopy(EMPTY);channel.ready=True
            backend=DemoBackend(here/'modules.json',*bridges,manifests,bls)
            prefs=Preferences(root/'prefs',persist=False)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],manifests=manifests,bls=bls,preferences=prefs).items():
                engine.rootContext().setContextProperty(name,value)
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            def find(name):
                def scan(item):
                    if item.objectName()==name:return item
                    for child in item.childItems():
                        found=scan(child)
                        if found:return found
                return scan(window.contentItem())
            try:
                profiles=[(b.moduleId,b) for b in bridges]+[('bls',bls)]+[('manifiestos',manifests)]*5
                flows=iter(('tabla','conocimientos','duas','movimientos','contenedores'))
                for module,bridge in profiles:
                    if module=='manifiestos':
                        backend.navigate('overview');APP.processEvents()
                        bridge._flow=next(flows);bridge.changed.emit()
                    monitor=bridge.consoleMonitor
                    model=bridge.activityModel
                    for index in range(40):model.prepend(dict(time='12:34:56',level='INFO',message=f'Página {index} · Validando respuesta completa y exportando resultados'))
                    operations=[dict(key=str(i),label='Esperando respuesta HTTP sin límite de tiempo',subject=f'Aéreo · 1-0-00001-A01-01/10/26 · BL 00000{i}',elapsed=25+i) for i in range(8)]
                    monitor.accept(dict(event='activity_state',running=True,operations=operations))
                    backend.navigate(module);APP.processEvents()
                    panel=find('activityConsole');self.assertIsNotNone(panel,module)
                    for dark in (True,False):
                        if prefs.dark!=dark:QMetaObject.invokeMethod(window,'toggleTheme',Qt.DirectConnection)
                        for width,height in ((1000,600),(1440,900)):
                            window.setProperty('minimumHeight',600);window.setWidth(width);window.setHeight(height)
                            for _ in range(4):APP.processEvents()
                            wait_until(lambda:panel.width()<=width,timeout=2000)
                            self.assertGreater(panel.width(),300)
                            self.assertLessEqual(panel.width(),width)
                            self.assertGreaterEqual(panel.height(),270)
                            view=panel.findChild(QObject,'activityView')
                            self.assertEqual(view.property('count'),40)
                            self.assertGreater(view.height(),40)
                            active=panel.findChild(QObject,'activityOperations')
                            self.assertEqual(active.property('count'),8)
                            active.setProperty('contentY',30.0)
                            monitor.tick();APP.processEvents()
                            self.assertEqual(active.property('contentY'),30.0)
                    capture=os.environ.get('CHC_ACTIVITY_CAPTURE_DIR')
                    if capture and (module!='manifiestos' or bridge.flow=='conocimientos'):
                        page=find('batchRealPage' if module in ('bls','manifiestos') else 'detailsRealPage' if module=='detalles' else 'transitRealPage' if module=='duas_transito' else module+'RealPage')
                        flick=page.property('contentItem')
                        y=panel.mapToItem(flick.property('contentItem'),QPointF(0,0)).y()
                        flick.setProperty('contentY',max(0,y-20));APP.processEvents()
                        path=Path(capture)/(module+'.png');path.parent.mkdir(parents=True,exist_ok=True)
                        self.assertTrue(window.grabWindow().save(str(path)))
                    monitor.finish()
                self.assertFalse(warnings,warnings)
            finally:
                window.setVisible(False);engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
