"""Accesos TICA y reintento mensual, incluso mientras la descarga está ocupada."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import APP, RecordingBridge
from test_details_bridge import wait_until
from demo import DemoBackend
from preferences import Preferences
from PySide6.QtCore import QMetaObject, QObject, QUrl, Qt
from PySide6.QtQml import QQmlApplicationEngine


class ReviewQMLTests(unittest.TestCase):
    def test_row_opens_its_bot_independently_and_month_button_uses_selected_table_period(self):
        here=Path(__file__).resolve().parents[1]
        bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
        backend=DemoBackend(here/'modules.json',*bridges)
        preferences=Preferences(here/'unused-review-test.json',persist=False)
        engine=QQmlApplicationEngine();warnings=[]
        engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
        for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],preferences=preferences).items():
            engine.rootContext().setContextProperty(name,value)
        captures={}
        commands=[]
        for bridge in bridges:
            captures[bridge.moduleId]=[]
            bridge._review.open=lambda request,m=bridge.moduleId:captures[m].append(request)
            bridge._snapshot['activeTable']['source_path']='daily://2026-09'
            bridge._snapshot['summary'].update(total=1,pending=0,retry=1)
            bridge._view={'rows':[dict(id='001-2026-000001',dua='001-2026-000001',status='retry',attempts=3,
                error_kind='NoRowsException',reason='Omitido del automático',autoOmitted=True)],'offset':0,'total':1}
        backend.navigate('detalles');engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
        self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
        def visual(name):
            def visit(item):
                if item.objectName()==name:return item
                for child in item.childItems():
                    result=visit(child)
                    if result:return result
                return None
            return visit(window.contentItem())
        try:
            for bridge in bridges:
                with self.subTest(module=bridge.moduleId):
                    backend.navigate(bridge.moduleId);APP.processEvents()
                    page=window.findChild(QObject,'detailsRealPage' if bridge.moduleId=='detalles' else 'transitRealPage' if bridge.moduleId=='duas_transito' else bridge.moduleId+'RealPage')
                    button=page.findChild(QObject,'detailsDatabaseButton')
                    QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection);APP.processEvents()
                    bridge._busy=bridge._running=True;bridge.changed.emit();APP.processEvents()
                    wait_until(lambda:visual('duaOpenTica') is not None,timeout=3000)
                    button=visual('duaOpenTica')
                    self.assertIsNotNone(button,warnings);self.assertTrue(button.property('enabled'))
                    QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
                    self.assertEqual(captures[bridge.moduleId],[{'tableId':'test','jobId':'001-2026-000001'}])
                    bridge._busy=bridge._running=False;bridge.changed.emit()
                    dialog=page.findChild(QObject,'detailsDatabaseDialog')
                    if dialog:QMetaObject.invokeMethod(dialog,'close',Qt.DirectConnection)
                    APP.processEvents()
                    bridge._send=lambda command,data=None:commands.append((command,data)) or True
                    button=page.findChild(QObject,'retryMonthButton')
                    self.assertTrue(button.property('visible'));self.assertTrue(button.property('enabled'))
                    QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection)
                    self.assertEqual(commands[-1],('retry_month',{'month':'2026-09'}))
            self.assertFalse(warnings,warnings)
        finally:
            window.setVisible(False);engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()
