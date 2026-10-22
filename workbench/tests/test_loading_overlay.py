"""Carga visual independiente por sección; sin motores ni red."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until,DetailsBridge,DemoBackend,Preferences
from batch_bridge import BatchBridge
from PySide6.QtCore import QUrl,Qt,QMetaObject
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest


class MemoryDetails(DetailsBridge):
    def connectModule(self):pass


class MemoryBatch(BatchBridge):
    def connectModule(self):pass
    def refreshKnowledge(self):pass


class LoadingOverlayTests(unittest.TestCase):
    def test_states_follow_loading_until_idle_but_never_mask_downloads_or_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for module in ('detalles','duas_transito','talon','xmovimientos'):
                bridge=MemoryDetails(module_id=module,storage_root=root/module)
                self.assertTrue(bridge.loading)
                bridge._requests={1:dict(command='initialize',readonly=False)}
                bridge._receive(dict(event='result',command='initialize',requestId=1,runtime={}))
                self.assertTrue(bridge.ready)
                self.assertTrue(bridge.loading)
                bridge._receive(dict(event='idle',requestId=1,readonly=False))
                self.assertFalse(bridge.loading)
                bridge._requests={2:dict(command='select',readonly=False)}
                self.assertTrue(bridge.loading)
                bridge._running=True
                self.assertFalse(bridge.loading)
                bridge._running=False;bridge._error='No se pudo abrir la base'
                self.assertFalse(bridge.loading)
            for module in ('manifiestos','bls'):
                bridge=MemoryBatch(module_id=module,storage_root=root/module)
                channel=bridge.current()
                self.assertTrue(bridge.loading)
                channel.ready=True;channel.busy=True;channel.active_command='refresh'
                self.assertTrue(bridge.loading)
                channel.busy=False;channel.active_command=''
                self.assertFalse(bridge.loading)
                channel.busy=True;channel.active_command='select'
                self.assertTrue(bridge.loading)
                channel.ready=False;channel.error='Error de lectura'
                self.assertFalse(bridge.loading)
                channel.error='';channel.ready=True;channel.active_command='run'
                auxiliary=bridge.channels['bls_source' if module=='bls' else 'bases']
                auxiliary.busy=True;auxiliary.active_command='knowledge_catalog' if module=='bls' else 'refresh'
                channel.busy=False;channel.active_command=''
                self.assertFalse(bridge.loading,'Un auxiliar no puede ocultar la sección lista')
                channel.error='Error de lectura'
                self.assertFalse(bridge.loading,'El auxiliar no puede ocultar el error del procedimiento')
                channel.error='';channel.busy=True;channel.active_command='run'
                self.assertFalse(bridge.loading)
                channel.active_command='retry_empty'
                self.assertFalse(bridge.loading)
            disabled=DetailsBridge(enabled=False,storage_root=root/'demo')
            self.assertFalse(disabled.loading)

    def test_sections_load_independently_without_navigation_or_route_changes(self):
        if sys.platform=='win32':
            fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','consola.ttf'):
                QFontDatabase.addApplicationFont(str(fonts/name))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);here=Path(__file__).resolve().parents[1]
            details=[MemoryDetails(module_id=m,storage_root=root/m) for m in ('detalles','duas_transito','talon','xmovimientos')]
            manifests=MemoryBatch(storage_root=root/'manifiestos')
            bls=MemoryBatch(module_id='bls',storage_root=root/'bls')
            bridges=details+[manifests,bls]
            def ready(bridge,value):
                if isinstance(bridge,DetailsBridge):bridge._ready=value
                else:bridge.current().ready=value
                bridge.changed.emit()
            backend=DemoBackend(here/'modules.json',*details,manifests,bls)
            preferences=Preferences(root/'prefs.json',persist=False)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=details[0],transit=details[1],talon=details[2],movements=details[3],
                                   manifests=manifests,bls=bls,preferences=preferences).items():
                engine.rootContext().setContextProperty(name,value)
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            def find(name):
                def scan(item):
                    if item.objectName()==name:return item
                    for child in item.childItems():
                        result=scan(child)
                        if result:return result
                return scan(window.contentItem())
            try:
                # Todos cargando: Vista General ya permite navegar y buscar.
                self.assertEqual(backend.route,'overview')
                self.assertTrue(all(m['status']=='loading' for m in backend.modules))
                self.assertEqual(backend.runningCount,0)
                self.assertIsNotNone(find('dashboardPage'))
                self.assertTrue(find('workbenchControls').property('enabled'))
                self.assertIsNone(find('sectionLoading'))
                QTest.keyClick(window,Qt.Key_B,Qt.ControlModifier)
                self.assertFalse(window.property('sidebarExpanded'))
                routes=['detalles','duas_transito','talon','xmovimientos','manifiestos','bls']
                for route,bridge in zip(routes,bridges):
                    backend.navigate(route);APP.processEvents()
                    loading=find('sectionLoading')
                    self.assertTrue(loading.property('visible'),route)
                    self.assertTrue(find('workbenchControls').property('enabled'))
                    ready(bridge,True);APP.processEvents()
                    self.assertFalse(loading.property('visible'),route)
                    self.assertEqual(backend.route,route)
                    ready(bridge,False)
                    backend.navigate('overview');APP.processEvents()
                    ready(bridge,True);APP.processEvents()
                    self.assertEqual(backend.route,'overview')
                    self.assertIsNotNone(find('dashboardPage'))
                # Se conserva incluso la pestaña de un bot listo al terminar otro.
                backend.navigate('detalles');APP.processEvents()
                page=find('detailsRealPage');page.setProperty('tab',2)
                ready(bls,False);ready(bls,True);APP.processEvents()
                self.assertIs(find('detailsRealPage'),page)
                self.assertEqual(page.property('tab'),2)
                # La navegación entre procedimientos sigue visible durante la carga.
                ready(manifests,False);backend.navigate('manifiestos');APP.processEvents()
                self.assertTrue(find('manifestNav_duas').property('enabled'))
                self.assertTrue(find('sectionLoading').property('visible'))
                capture=os.environ.get('CHC_LOADING_CAPTURE_DIR')
                if capture:
                    target=Path(capture);target.mkdir(parents=True,exist_ok=True)
                    QTest.qWait(200)
                    self.assertTrue(window.grabWindow().save(str(target/'section-dark.png')))
                    window.setMinimumHeight(0);window.resize(1000,600)
                    QMetaObject.invokeMethod(window,'toggleTheme',Qt.DirectConnection);APP.processEvents()
                    QTest.qWait(200)
                    self.assertTrue(window.grabWindow().save(str(target/'section-light.png')))
                self.assertFalse(warnings,warnings)
            finally:
                window.setVisible(False);engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
