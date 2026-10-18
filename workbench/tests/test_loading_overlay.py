"""Espera visual real, bloqueo de entrada y salida segura; sin motores ni red."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until,DetailsBridge,DemoBackend,Preferences
from batch_bridge import BatchBridge
from PySide6.QtCore import QObject,QUrl,Qt,QPointF,QMetaObject
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
                self.assertFalse(bridge.loading)
                channel.active_command='retry_empty'
                self.assertFalse(bridge.loading)
            disabled=DetailsBridge(enabled=False,storage_root=root/'demo')
            self.assertFalse(disabled.loading)

    def test_all_bots_block_controls_and_shortcuts_then_release_with_smooth_compact_overlay(self):
        if sys.platform=='win32':
            for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
                QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
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
            for bridge in bridges:ready(bridge,True)
            backend=DemoBackend(here/'modules.json',*details,manifests,bls)
            preferences=Preferences(root/'prefs.json',persist=False)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=details[0],transit=details[1],talon=details[2],movements=details[3],
                                   manifests=manifests,bls=bls,preferences=preferences).items():
                engine.rootContext().setContextProperty(name,value)
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            def find(name):
                target=window.findChild(QObject,name)
                if target:return target
                pending=[window.contentItem()]
                while pending:
                    item=pending.pop()
                    if item.objectName()==name:return item
                    pending.extend(item.childItems())
            try:
                controls=find('workbenchControls');overlay=find('baseLoadingOverlay')
                self.assertTrue(controls.property('enabled'))
                for bridge in bridges:
                    ready(bridge,False);APP.processEvents()
                    self.assertTrue(window.property('loadingBases'))
                    self.assertFalse(controls.property('enabled'))
                    self.assertTrue(overlay.property('visible'))
                    self.assertEqual(len(window.property('loadingModules').toVariant()),1)
                    expanded=window.property('sidebarExpanded')
                    QTest.keyClick(window,Qt.Key_B,Qt.ControlModifier)
                    QTest.keyClick(window,Qt.Key_Escape)
                    self.assertEqual(window.property('sidebarExpanded'),expanded)
                    self.assertTrue(overlay.property('visible'))
                    nav=find('sharePointNavigation')
                    point=nav.mapToScene(QPointF(nav.width()/2,nav.height()/2))
                    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point.toPoint())
                    self.assertFalse(find('sharePointDialog').property('visible'))
                    ready(bridge,True)
                    wait_until(lambda:not overlay.property('visible'),timeout=1500)
                    self.assertTrue(controls.property('enabled'))
                for bridge in bridges:ready(bridge,False)
                wait_until(lambda:overlay.property('opened'),timeout=1500)
                target=here.parent/'runtime/diagnostics/loading';target.mkdir(parents=True,exist_ok=True)
                self.assertTrue(window.grabWindow().save(str(target/'bots-dark.png')))
                window.setMinimumHeight(0);window.resize(1000,600)
                QMetaObject.invokeMethod(window,'toggleTheme',Qt.DirectConnection);APP.processEvents()
                self.assertTrue(window.grabWindow().save(str(target/'bots-light-compact.png')))
                self.assertLessEqual(overlay.property('width'),window.width()-32)
                self.assertLessEqual(overlay.property('height'),window.height()-32)
                for bridge in bridges:ready(bridge,True)
                wait_until(lambda:not overlay.property('visible'),timeout=1500)
                QTest.keyClick(window,Qt.Key_B,Qt.ControlModifier)
                self.assertFalse(window.property('sidebarExpanded'))
                self.assertFalse(warnings,warnings)
            finally:
                window.close();engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
