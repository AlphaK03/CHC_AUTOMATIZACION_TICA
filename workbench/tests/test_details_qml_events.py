"""Regresión rápida de guardar e iniciar en QML; sin worker ni consultas."""
import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from PySide6.QtQuickControls2 import QQuickStyle
from details_bridge import DetailsBridge
from demo import DemoBackend
from preferences import Preferences

APP = QGuiApplication.instance() or QGuiApplication([])
APP.setQuitOnLastWindowClosed(False)
QQuickStyle.setStyle('Basic')


class RecordingBridge(DetailsBridge):
    def connectModule(self):
        # DemoBackend.navigate calls this; this unit check must stay in-memory.
        pass

    def __init__(self, module_id='detalles'):
        super().__init__(module_id=module_id)
        self.commands = []
        self._ready = True
        self._runtime['chromiumReady'] = True
        self._snapshot['config'] = {
            'cant_hilos': 1, 'timeout': 30, 'max_retries': 3,
            'output_base_path': 'test-output',
        }
        self._snapshot['activeTable'] = {'id': 'test', 'name': 'Prueba'}
        self._snapshot['tables'] = [self._snapshot['activeTable']]
        self._snapshot['summary'].update(total=1, pending=1)

    def _send(self, command, data=None):
        self.commands.append(command)
        self._busy = command not in {'stop', 'shutdown'}
        self.changed.emit()
        return True


class ConfigurationEventsTest(unittest.TestCase):
    def test_four_daily_ranges_follow_progress_keep_origin_and_preserve_manual_edits(self):
        from test_details_bridge import wait_until
        bridges = [RecordingBridge(module) for module in ('detalles', 'duas_transito', 'talon', 'xmovimientos')]
        backend = DemoBackend(HERE / 'modules.json', *bridges)
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda items: warnings.extend(x.toString() for x in items))
        context = engine.rootContext()
        for name, value in dict(demo=backend, details=bridges[0], transit=bridges[1], talon=bridges[2],
                                movements=bridges[3], preferences=Preferences(HERE/'unused-test-preferences.json', persist=False)).items():
            context.setContextProperty(name, value)
        for bridge in bridges:
            bridge._snapshot['config'].update(daily_mode=True, daily_start_date='2026-10-01', daily_end_date='2026-10-05')
            bridge._daily.update(startDate='2026-10-01', resumeDate='2026-10-08', resumeEndDate='2026-10-15',
                                 waitingForDay=False, month='2026-10', monthLabel='Octubre 2026')
        backend.navigate('detalles')
        engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
        self.assertTrue(engine.rootObjects(), warnings)
        window = engine.rootObjects()[0]
        try:
            for bridge in bridges:
                backend.navigate(bridge.moduleId)
                name = {'detalles':'detailsRealPage','duas_transito':'transitRealPage'}.get(bridge.moduleId, bridge.moduleId+'RealPage')
                wait_until(lambda: window.findChild(QObject, name) is not None)
                page = window.findChild(QObject, name)
                start = page.findChild(QObject, 'detailsDailyStart')
                end = page.findChild(QObject, 'detailsDailyEnd')
                calendar = page.findChild(QObject, 'detailsDailyCalendar')
                self.assertEqual((start.property('text'), end.property('text')), ('2026-10-08','2026-10-15'))
                QMetaObject.invokeMethod(page, 'startQueries', Qt.DirectConnection)
                self.assertEqual(bridge.commands, ['daily_run'])
                bridge._busy = False
                bridge._daily.update(resumeDate='2026-10-09')
                bridge.changed.emit()
                APP.processEvents()
                self.assertEqual(start.property('text'), '2026-10-09')
                self.assertEqual(calendar.property('rangeStart'), '2026-10-09')
                # Guardar otros parámetros no convierte la vista móvil en el origen.
                expression = QQmlExpression(context, page, 'currentConfig().daily_start_date + "|" + currentConfig().daily_end_date')
                self.assertEqual(expression.evaluate()[0], '2026-10-01|2026-10-05')
                context.setContextProperty('testCalendar', calendar)
                choose = QQmlExpression(context, page, '''
                    testCalendar.chooseDay({date:"2026-09-29",available:true});
                    testCalendar.chooseDay({date:"2026-10-02",available:true});
                    testCalendar.applyRange();
                ''')
                choose.evaluate()
                self.assertFalse(choose.hasError(), choose.error().toString())
                bridge._daily.update(resumeDate='2026-10-10')
                bridge.changed.emit()
                APP.processEvents()
                self.assertEqual((start.property('text'), end.property('text')), ('2026-09-29','2026-10-02'))
                self.assertEqual(calendar.property('rangeStart'), '2026-09-29')
                self.assertEqual(expression.evaluate()[0], '2026-09-29|2026-10-02')
            self.assertFalse(warnings, warnings)
        finally:
            window.setVisible(False)

    def test_save_acknowledgement_and_start_after_save(self):
        bridge = RecordingBridge()
        transit = RecordingBridge('duas_transito')
        backend = DemoBackend(HERE / 'modules.json', bridge, transit)
        backend.navigate('detalles')
        prefs = Preferences(HERE / 'unused-test-preferences.json', persist=False)
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda items: warnings.extend(x.toString() for x in items))
        context = engine.rootContext()
        context.setContextProperty('demo', backend)
        context.setContextProperty('details', bridge)
        context.setContextProperty('transit', transit)
        context.setContextProperty('preferences', prefs)
        engine.load(QUrl.fromLocalFile(str(HERE / 'qml' / 'Main.qml')))
        self.assertTrue(engine.rootObjects(), warnings)
        window = engine.rootObjects()[0]
        page = window.findChild(QObject, 'detailsRealPage')
        self.assertIsNotNone(page)
        page.setProperty('configDirty', True)
        bridge.saveConfig(bridge.config)
        bridge._receive({'event': 'result', 'command': 'configure'})
        self.assertFalse(page.property('configDirty'))
        bridge._receive({'event': 'idle'})

        page.setProperty('configDirty', True)
        QMetaObject.invokeMethod(page, 'startQueries', Qt.DirectConnection)
        self.assertTrue(page.property('startAfterSave'))
        self.assertEqual(bridge.commands[-1], 'configure')
        bridge._receive({'event': 'result', 'command': 'configure'})
        bridge._receive({'event': 'idle'})
        APP.processEvents()
        self.assertFalse(page.property('configDirty'))
        self.assertFalse(page.property('startAfterSave'))
        self.assertEqual(bridge.commands[-1], 'run')
        self.assertEqual(bridge.commands.count('run'), 1)
        bridge._busy = False
        bridge.changed.emit()
        calendar = window.findChild(QObject, 'detailsDailyCalendar')
        self.assertIsNotNone(calendar)
        context.setContextProperty('testCalendar', calendar)
        expression = QQmlExpression(context, page, '''
            testCalendar.chooseDay({date:"2026-10-02",available:true,state:"outside"});
            testCalendar.chooseDay({date:"2026-09-29",available:true,state:"outside"});
            testCalendar.applyRange();
        ''')
        expression.evaluate()
        self.assertFalse(expression.hasError(), expression.error().toString())
        self.assertEqual(page.findChild(QObject, 'detailsDailyStart').property('text'), '2026-09-29')
        self.assertEqual(page.findChild(QObject, 'detailsDailyEnd').property('text'), '2026-10-02')
        self.assertTrue(page.property('configDirty'))
        self.assertTrue(page.property('dailyMode'))
        previous = list(bridge.commands)
        backend.navigate('duas_transito')
        APP.processEvents()
        transit_page = window.findChild(QObject, 'transitRealPage')
        self.assertIsNotNone(transit_page)
        self.assertEqual(transit_page.property('worker'), transit)
        QMetaObject.invokeMethod(transit_page, 'startQueries', Qt.DirectConnection)
        self.assertEqual(transit.commands[-1], 'run')
        self.assertEqual(bridge.commands, previous, 'Tránsito no envía órdenes a Detalles.')
        self.assertEqual(warnings, [])
        window.setVisible(False)


if __name__ == '__main__':
    unittest.main()
