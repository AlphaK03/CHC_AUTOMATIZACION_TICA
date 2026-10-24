"""Marca visual persistente: no cambia el progreso ni envía órdenes al worker."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_bridge import APP, DetailsBridge
from daily_marks import DailyMarks
from PySide6.QtCore import QObject, QMetaObject, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from demo import DemoBackend
from preferences import Preferences

HERE = Path(__file__).resolve().parents[1]
DAY = '2026-09-01'


class DailyMarksTests(unittest.TestCase):
    def test_failed_write_keeps_previous_marks_and_failed_read_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            marks = DailyMarks(folder)
            marks.set_completed(DAY, True)
            before = marks.path.read_bytes()
            with patch('daily_marks.os.replace', side_effect=OSError('disco ocupado')):
                with self.assertRaises(OSError):
                    marks.set_completed(DAY, False)
            self.assertEqual(marks.path.read_bytes(), before)
            self.assertIn(DAY, marks.values)
            self.assertFalse(list(marks.path.parent.glob('*.tmp')))
            marks.path.write_text('{JSON incompleto', encoding='utf-8')
            unreadable = DailyMarks(folder)
            with self.assertRaises(ValueError):
                unreadable.set_completed('2026-09-02', True)
            self.assertEqual(marks.path.read_text(encoding='utf-8'), '{JSON incompleto')

    def test_four_bots_persist_separately_keep_worker_state_and_accept_busy_mark(self):
        with tempfile.TemporaryDirectory() as folder:
            for module in ('detalles', 'duas_transito', 'talon', 'xmovimientos'):
                with self.subTest(module=module):
                    root = Path(folder) / module
                    bridge = DetailsBridge(storage_root=root, module_id=module)
                    bridge._ready = bridge._busy = bridge._running = bridge._daily_active = True
                    bridge._status = 'Procesando el 02/09/2026'
                    bridge._daily.update(days=[dict(day=1, date=DAY, available=True, state='omitted',
                        total=100, succeeded=98, error='Quedan pendientes')])
                    before = copy.deepcopy(bridge._daily)
                    with patch.object(bridge, '_send', side_effect=AssertionError('No enviar órdenes')):
                        bridge.markCalendarDay(DAY, True)
                    self.assertEqual(bridge._daily, before)
                    self.assertTrue(bridge.busy and bridge.running and bridge.dailyActive)
                    self.assertEqual(bridge.status, 'Procesando el 02/09/2026')
                    self.assertTrue(bridge.daily['days'][0]['manualCompleted'])
                    # Una respuesta del worker no elimina la decisión manual.
                    bridge._receive({'event': 'result', 'command': 'daily_calendar', 'daily': before})
                    self.assertTrue(bridge.daily['days'][0]['manualCompleted'])
                    restored = DetailsBridge(storage_root=root, module_id=module)
                    restored._daily = copy.deepcopy(before)
                    restored._ready = True
                    self.assertTrue(restored.daily['days'][0]['manualCompleted'])
                    other = DetailsBridge(storage_root=Path(folder)/('other-'+module), module_id=module)
                    other._daily = copy.deepcopy(before)
                    self.assertFalse(other.daily['days'][0]['manualCompleted'])
                    restored.markCalendarDay(DAY, False)
                    self.assertFalse(restored.daily['days'][0]['manualCompleted'])
                    self.assertEqual(restored._daily, before)
                    self.assertEqual(list(root.rglob('*.*')), [root/'data/daily/manual_completed_days.json'])

    def test_unavailable_and_demo_days_do_not_write_marks(self):
        with tempfile.TemporaryDirectory() as folder:
            bridge = DetailsBridge(storage_root=folder)
            bridge._ready = True
            bridge._daily['days'] = [dict(date=DAY, available=False)]
            bridge.markCalendarDay(DAY, True)
            bridge.markCalendarDay('invalid', True)
            self.assertFalse(list(Path(folder).rglob('*.json')))
            bridge._enabled = False
            bridge._daily['days'][0]['available'] = True
            bridge.markCalendarDay(DAY, True)
            self.assertFalse(list(Path(folder).rglob('*.json')))

    def test_qml_mark_and_remove_during_processing_keep_retry_and_green_after_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            bridges = [DetailsBridge(storage_root=Path(folder)/module, module_id=module)
                for module in ('detalles', 'duas_transito', 'talon', 'xmovimientos')]
            for bridge in bridges:
                bridge.connectModule = lambda: None
                bridge._ready = True
                bridge._daily.update(month='2026-09', monthLabel='Septiembre 2026',
                    startDate=DAY, days=[dict(day=1, date=DAY, available=True, state='omitted',
                    total=100, succeeded=98, error='Quedan 2 pendientes')])
            backend = DemoBackend(HERE/'modules.json', *bridges)
            backend.navigate('talon')
            prefs = Preferences(Path(folder)/'preferences.json', persist=False)
            if sys.platform == 'win32':
                fonts = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
                for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
                    QFontDatabase.addApplicationFont(str(fonts/name))
            engine = QQmlApplicationEngine()
            warnings = []
            engine.warnings.connect(lambda items: warnings.extend(x.toString() for x in items))
            context = engine.rootContext()
            for name, value in dict(demo=backend, details=bridges[0], transit=bridges[1],
                talon=bridges[2], movements=bridges[3], preferences=prefs).items():
                context.setContextProperty(name, value)
            engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(), warnings)
            window = engine.rootObjects()[0]
            try:
                page = window.findChild(QObject, 'talonRealPage')
                calendar = page.findChild(QObject, 'detailsDailyCalendar')
                context.setContextProperty('testCalendar', calendar)
                QMetaObject.invokeMethod(calendar, 'open', Qt.DirectConnection)
                expression = QQmlExpression(context, page, 'testCalendar.chooseDay(testCalendar.worker.daily.days[0])')
                expression.evaluate()
                self.assertFalse(expression.hasError(), expression.error().toString())
                bridge = bridges[2]
                bridge._busy = bridge._running = bridge._daily_active = True
                bridge.changed.emit(); APP.processEvents()
                mark = calendar.findChild(QObject, 'markCalendarDay')
                retry = calendar.findChild(QObject, 'retryCalendarMonth')
                self.assertTrue(mark.property('enabled'))
                self.assertFalse(retry.property('enabled'))
                QMetaObject.invokeMethod(mark, 'clicked', Qt.DirectConnection)
                APP.processEvents()
                self.assertEqual(mark.property('text'), 'Quitar marca manual')
                summary = calendar.findChild(QObject, 'calendarDaySummary').property('text')
                self.assertIn('Completado manual', summary)
                self.assertIn('98 / 100 guardados', summary)
                self.assertIn('Omitido', summary)
                # Repeater items are visual children rather than QObject children.
                green = QQmlExpression(context, page, '''
                    function find(item) {
                        if(item.objectName === "calendarDay2026-09-01") return item;
                        for(let child of (item.children || [])) { let found = find(child); if(found) return found; }
                        return null;
                    }
                    find(testCalendar.contentItem).completed
                ''')
                self.assertTrue(green.evaluate()[0])
                self.assertFalse(green.hasError(), green.error().toString())
                bridge._busy = bridge._running = bridge._daily_active = False
                bridge.changed.emit(); APP.processEvents()
                self.assertTrue(retry.property('enabled'))
                with patch.object(bridge, '_send', return_value=True) as send:
                    QMetaObject.invokeMethod(retry, 'clicked', Qt.DirectConnection)
                    send.assert_called_once_with('retry_month', {'month': '2026-09'})
                capture = os.environ.get('CHC_DAILY_MARKS_CAPTURE')
                if capture:
                    path = Path(capture); path.parent.mkdir(parents=True, exist_ok=True)
                    APP.processEvents()
                    self.assertTrue(window.grabWindow().save(str(path)))
                QMetaObject.invokeMethod(mark, 'clicked', Qt.DirectConnection)
                APP.processEvents()
                self.assertEqual(mark.property('text'), 'Marcar completado')
                self.assertFalse(bridge.daily['days'][0]['manualCompleted'])
                self.assertFalse(warnings, warnings)
            finally:
                window.close(); APP.processEvents()


if __name__ == '__main__':
    unittest.main()
