"""Bitácora QML: lectura asíncrona, actualización y navegación con datos aislados."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until,DetailsBridge,DemoBackend,Preferences
import test_monthly_progress as fixtures
from monthly_bridge import MonthlyProgress
from monthly_progress import MonthlyReader,month_days
from PySide6.QtCore import QObject,QMetaObject,QUrl,Qt
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtGui import QFontDatabase


class MonthlyQMLTests(unittest.TestCase):
    def test_async_refresh_expansion_navigation_and_responsive_display(self):
        data=fixtures.MonthlyTests();data.setUp()
        monthly=None
        window=None
        try:
            data.dua_table();data.ledger()
            monthly=MonthlyProgress({'detalles':data.root})
            old=[DetailsBridge(enabled=False,module_id=m) for m in ('detalles','duas_transito','talon','xmovimientos')]
            here=Path(__file__).resolve().parents[1]
            if sys.platform=='win32':
                fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
                for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
                    QFontDatabase.addApplicationFont(str(fonts/name))
            backend=DemoBackend(here/'modules.json',*old,monthly=monthly)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            preferences=Preferences(data.root/'prefs.json',persist=False)
            for name,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],preferences=preferences).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('overview')
            engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            wait_until(lambda:monthly.rows and not monthly.busy)
            self.assertEqual(backend.monthlyRows[0]['cells'][0]['label'],'Completado')
            log=window.findChild(QObject,'monthlyLog')
            self.assertIsNotNone(log)
            log.setProperty('expandedMonth','2026-09')
            APP.processEvents()
            self.assertFalse(warnings,warnings)
            with fixtures.write(data.root/'data/queues/month.sqlite3') as db:
                db.execute("UPDATE jobs SET status='retry',result=NULL WHERE dua='30'")
            refresh=window.findChild(QObject,'refreshMonthly')
            self.assertTrue(QMetaObject.invokeMethod(refresh,'clicked',Qt.DirectConnection))
            wait_until(lambda:not monthly.busy and backend.monthlyRows[0]['cells'][0]['status']=='partial')
            reader=MonthlyReader({},data.today)
            reader.add('2026-09','detalles','','septiembre26',1000,1000,days=month_days('2026-09'),scope='1,000 / 1,000 DUAs confirmados · 30 / 30 días verificados')
            reader.add('2026-09','talon','','septiembre26',1000,650,scope='650 / 1,000 DUAs confirmados')
            reader.add('2026-09','bls','','BLs septiembre',2500,1400,running=2,scope='1,400 / 2,500 BL confirmados')
            reader.add('2026-09','manifiestos','conocimientos','Conocimientos',500,500,days=month_days('2026-09'),scope='Marítimo · 500 / 500 confirmados')
            reader.add('2026-10','detalles','','octubre26',350,350,scope='350 / 350 DUAs confirmados · 12 / 31 días verificados',status='partial')
            monthly.rows=reader.read()['rows'];monthly.changed.emit()
            log.setProperty('expandedMonth','2026-09')
            for width in (1000,1280):
                window.setWidth(width);APP.processEvents()
            capture=os.environ.get('CHC_MONTHLY_CAPTURE')
            if capture:
                path=Path(capture);path.parent.mkdir(parents=True,exist_ok=True)
                wait_until(lambda:window.grabWindow().width()>0)
                self.assertTrue(window.grabWindow().save(str(path)))
            self.assertTrue(QMetaObject.invokeMethod(window,'toggleTheme',Qt.DirectConnection))
            APP.processEvents()
            if capture:
                self.assertTrue(window.grabWindow().save(str(path.with_name(path.stem+'-claro.png'))))
            self.assertFalse(warnings,warnings)
            backend.navigate('bls');self.assertEqual(backend.route,'bls')
            self.assertTrue(all(not b.enabled for b in old))
            self.assertFalse(any('bots' in str(getattr(m,'__file__','')).replace('\\','/').split('/') for m in sys.modules.values()))
        finally:
            if monthly:monthly.timer.stop();monthly.debounce.stop()
            if window:window.close();APP.processEvents()
            data.tearDown()


if __name__=='__main__':unittest.main()
