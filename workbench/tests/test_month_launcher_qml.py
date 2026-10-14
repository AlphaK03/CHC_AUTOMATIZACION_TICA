"""Botones de Vista general: elegir mes, desmarcar y ajustar trabajadores sin red."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_month_launcher import FakeDetails,fake_batch,APP
from demo import DemoBackend
from preferences import Preferences
from PySide6.QtCore import QObject,QMetaObject,Qt,QUrl,Q_ARG
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtQml import QQmlApplicationEngine

HERE=Path(__file__).resolve().parents[1]


class MonthStartQML(unittest.TestCase):
    def test_select_month_workers_and_start_only_checked_rows(self):
        old=[FakeDetails(m) for m in ('detalles','duas_transito','talon','xmovimientos')]
        manifests,bls=fake_batch(),fake_batch('bls')
        backend=DemoBackend(HERE/'modules.json',*old,manifests,bls)
        backend._timer.stop();backend.navigate('overview')
        engine=QQmlApplicationEngine();warnings=[]
        engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
        prefs=Preferences(HERE/'unused-test-preferences.json',persist=False)
        if sys.platform=='win32':
            fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):QFontDatabase.addApplicationFont(str(fonts/name))
            APP.setFont(QFont('Segoe UI',10))
        for key,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],manifests=manifests,bls=bls,preferences=prefs).items():
            engine.rootContext().setContextProperty(key,value)
        engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
        self.assertTrue(engine.rootObjects(),warnings)
        window=engine.rootObjects()[0]
        try:
            def find(name):
                result=window.findChild(QObject,name)
                if not result:
                    pending=[window.contentItem()]
                    while pending:
                        item=pending.pop()
                        if item.objectName()==name:result=item;break
                        pending.extend(item.childItems())
                self.assertIsNotNone(result,name);return result
            def click(name):self.assertTrue(QMetaObject.invokeMethod(find(name),'clicked',Qt.DirectConnection));APP.processEvents()
            click('monthStartExpand')
            year=find('bulkYear');year.setProperty('value',2026)
            self.assertTrue(QMetaObject.invokeMethod(year,'valueModified',Qt.DirectConnection))
            month=find('bulkMonth');month.setProperty('currentIndex',8)
            self.assertTrue(QMetaObject.invokeMethod(month,'activated',Qt.DirectConnection,Q_ARG(int,8)))
            click('bulkSelectAll')
            talon=find('bulkSelect_talon');talon.setProperty('checked',False);click('bulkSelect_talon')
            worker=find('bulkWorkers_detalles');worker.setProperty('value',7)
            self.assertTrue(QMetaObject.invokeMethod(worker,'valueModified',Qt.DirectConnection))
            self.assertEqual((backend.monthLauncher.year,backend.monthLauncher.month),(2026,9))
            self.assertFalse(next(i for i in backend.monthLauncher.items if i['id']=='talon')['selected'])
            self.assertTrue(find('bulkStart').property('enabled'))
            for width in (1000,1280):window.setWidth(width);APP.processEvents()
            capture=os.environ.get('CHC_MONTH_START_CAPTURE')
            if capture:
                path=Path(capture);path.parent.mkdir(parents=True,exist_ok=True)
                self.assertTrue(window.grabWindow().save(str(path)))
                QMetaObject.invokeMethod(window,'toggleTheme',Qt.DirectConnection);APP.processEvents()
                self.assertTrue(window.grabWindow().save(str(path.with_name(path.stem+'-claro.png'))))
            click('bulkStart')
            self.assertEqual(old[0].requests[0]['config']['cant_hilos'],7)
            self.assertEqual(old[0].requests[0]['config']['daily_end_date'],'2026-09-30')
            self.assertEqual(old[2].requests,[])
            self.assertEqual(backend.monthLauncher.tasks['bls']['stage'],'dependency')
            self.assertFalse(find('bulkStart').property('enabled'))
            click('bulkCancel')
            self.assertFalse(backend.monthLauncher.active)
            self.assertFalse(warnings,warnings)
        finally:
            backend.monthLauncher.cancel();window.setVisible(False);APP.processEvents()


if __name__=='__main__':unittest.main()
