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

    def __init__(self):
        super().__init__()
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
    def test_save_acknowledgement_and_start_after_save(self):
        bridge = RecordingBridge()
        backend = DemoBackend(HERE / 'modules.json', bridge)
        backend.navigate('detalles')
        prefs = Preferences(HERE / 'unused-test-preferences.json', persist=False)
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda items: warnings.extend(x.toString() for x in items))
        context = engine.rootContext()
        context.setContextProperty('demo', backend)
        context.setContextProperty('details', bridge)
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
        self.assertEqual(warnings, [])
        window.setVisible(False)


if __name__ == '__main__':
    unittest.main()
