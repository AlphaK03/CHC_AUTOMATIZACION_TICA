"""Selección QML de meses/modalidades disponibles e inicio automático de BLs."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until,DetailsBridge,DemoBackend,Preferences
from test_bls_knowledge import sources
from batch_bridge import BatchBridge
from PySide6.QtCore import QObject,QMetaObject,QUrl,Qt
from PySide6.QtQml import QQmlApplicationEngine


class KnowledgeQML(unittest.TestCase):
    def test_choose_modes_and_generate_from_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            sources(root/'manifiestos')
            bls=BatchBridge(module_id='bls',storage_root=root/'bls',knowledge_root=root/'manifiestos',offline_fixture=True)
            manifests=BatchBridge(enabled=False,storage_root=root/'manifiestos')
            old=[DetailsBridge(enabled=False,module_id=m) for m in ('detalles','duas_transito','talon','xmovimientos')]
            here=Path(__file__).resolve().parents[1]
            backend=DemoBackend(here/'modules.json',*old,manifests,bls)
            preferences=Preferences(root/'prefs.json',persist=False)
            engine=QQmlApplicationEngine()
            warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],
                                   manifests=manifests,bls=bls,preferences=preferences).items():
                engine.rootContext().setContextProperty(name,value)
            window=None
            def find(name):
                target=window.findChild(QObject,name)
                if target: return target
                pending=[window.contentItem()]
                while pending:
                    item=pending.pop()
                    if item.objectName()==name: return item
                    pending.extend(item.childItems())
            def click(name):
                target=find(name)
                self.assertIsNotNone(target,name)
                wait_until(lambda:target.property('enabled'),timeout=3000)
                self.assertTrue(QMetaObject.invokeMethod(target,'clicked',Qt.DirectConnection))
            try:
                bls.connectModule()
                wait_until(lambda:bls.ready and not bls.busy)
                backend.navigate('bls')
                engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
                self.assertTrue(engine.rootObjects(),warnings)
                window=engine.rootObjects()[0]
                APP.processEvents()
                self.assertFalse(window.findChild(QObject,'manifestStart').property('enabled'))
                click('blsChooseKnowledge')
                wait_until(lambda:not bls.knowledgeBusy)
                APP.processEvents()
                for key in ('2026-09|maritimo','2026-09|aereo'):
                    wait_until(lambda:find('knowledgeChoice_'+key) is not None,timeout=3000)
                    checkbox=find('knowledgeChoice_'+key)
                    self.assertIsNotNone(checkbox,key)
                    checkbox.setProperty('checked',True)
                    self.assertTrue(QMetaObject.invokeMethod(checkbox,'clicked',Qt.DirectConnection))
                click('blsKnowledgeAccept')
                click('manifestStart')
                wait_until(lambda:not bls.busy,timeout=15000)
                self.assertFalse(bls.error,bls.error)
                self.assertEqual(bls.summary['succeeded'],2)
                self.assertEqual(bls.config['name'],'')
                self.assertEqual(set(bls.config['knowledgePeriods']),{'2026-09|maritimo','2026-09|aereo'})
                self.assertFalse(warnings,warnings)
            finally:
                bls.shutdown(); wait_until(lambda:bls.isClosed)
                if window: window.close()
                engine.deleteLater(); APP.processEvents()


if __name__=='__main__': unittest.main()
