"""Pruebas de integración Qt → proceso → SQLite; portal sustituido por HTML local."""
import csv
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, QMetaObject, Q_ARG, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from demo import DemoBackend
from details_bridge import DetailsBridge
from preferences import Preferences

APP = QGuiApplication.instance() or QGuiApplication([])
APP.setQuitOnLastWindowClosed(False)
QQuickStyle.setStyle('Basic')


def wait_until(predicate, timeout=45000):
    if predicate():
        return
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(25)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    timer.start()
    deadline.start(timeout)
    loop.exec()
    timer.stop()
    deadline.stop()
    if not predicate():
        raise AssertionError('La operación no terminó dentro del límite de la prueba.')


class BridgeTests(unittest.TestCase):
    def test_manual_all_regenerates_deleted_csvs_and_keeps_selection(self):
        self.import_table('Primera');self.call('run')
        self.import_table('Segunda');self.call('run')
        active=self.bridge.activeTable['id']
        self.assertFalse(list((self.root/'output').rglob('*.CSV')))
        result=self.call('export_all',{'exportToken':'manual'})['exportReport']
        self.assertEqual(result,{'token':'manual','exported':2,'errors':[]})
        self.assertEqual(self.bridge.activeTable['id'],active)
        files=list((self.root/'output').rglob('*.CSV'));self.assertEqual(len(files),2)
        contents={p:p.read_bytes() for p in files}
        for path in files:path.unlink()
        self.call('export_all',{'exportToken':'again'})
        self.assertEqual({p:p.read_bytes() for p in files},contents)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bridges = []
        self.bridge = self.connect()
        self.events = []
        self.bridge.eventReceived.connect(self.events.append)
        self.call('configure', {'config': {'output_base_path': str(self.root / 'output'), 'cant_hilos': 1, 'max_retries': 1}})

    def connect(self):
        bridge = DetailsBridge(storage_root=self.root, offline_fixture=True)
        self.bridges.append(bridge)
        bridge.connectModule()
        wait_until(lambda: bridge.ready or bool(bridge.error))
        self.assertTrue(bridge.ready, bridge.error)
        wait_until(lambda: not bridge.busy)
        return bridge

    def tearDown(self):
        for bridge in self.bridges:
            bridge.shutdown()
            wait_until(lambda: bridge.isClosed)
        self.temp.cleanup()

    def call(self, command, data=None, error=False):
        start = len(self.events)
        self.assertTrue(self.bridge._send(command, data))
        wait_until(lambda: not self.bridge.busy)
        responses = [event for event in self.events[start:] if event['event'] in {'result', 'error'}]
        self.assertTrue(responses, self.bridge.error)
        self.assertEqual(responses[-1]['event'], 'error' if error else 'result', self.bridge.error)
        return responses[-1]

    def source(self):
        # Entrada sintética temporal: la prueba offline no depende de OneDrive.
        copy = self.root / 'sample.xlsx'
        subprocess.run([str(HERE.parent/'bots/detalles/.venv/Scripts/python.exe'),'-c',
            "from openpyxl import Workbook; import sys; b=Workbook(); b.active.title='muestra_original'; "
            "b.active.append(['NroDUA']); b.active.append(['001-2026-000001']); "
            "b.active.append(['001-2026-000002']); b.save(sys.argv[1]); b.close()",str(copy)],check=True)
        return copy

    def import_table(self, name='Prueba original'):
        source = self.source()
        prepared = self.call('prepare_import', {'source': str(source), 'sheet': 'muestra_original', 'name': name})['importPlan']
        imported = self.call('import', prepared)
        self.assertEqual(imported['importSummary']['rows'], 2)
        return source, prepared

    def test_import_append_restore_without_excel_and_confirm_target(self):
        source, prepared = self.import_table()
        self.assertEqual(self.bridge.summary['total'], 2)
        repeated = self.call('prepare_import', {'source': str(source), 'sheet': 'muestra_original', 'name': ' prueba ORIGINAL '})['importPlan']
        response = self.call('import', repeated)
        self.assertEqual(response['importSummary']['added'], 0)
        self.assertEqual(response['importSummary']['existing'], 2)
        self.assertEqual(self.bridge.summary['total'], 2)
        self.call('import', prepared, error=True)  # El destino cambió tras confirmar.
        self.call('rename', {'name': 'Nombre independiente'})
        table_id = self.bridge.activeTable['id']
        source.unlink()
        self.bridge.shutdown()
        wait_until(lambda: self.bridge.isClosed)
        restored = self.connect()
        self.assertEqual(restored.activeTable['id'], table_id)
        self.assertEqual(restored.activeTable['name'], 'Nombre independiente')
        self.assertEqual(restored.summary['total'], 2)
        self.assertEqual(len(restored.rows), 2)

    def test_real_processor_local_html_export_details_cleanup_backup(self):
        self.import_table()
        self.call('run')
        self.assertEqual(self.bridge.summary['succeeded'], 2)
        self.assertEqual(self.bridge.status, 'Completado')
        self.assertEqual(self.bridge.summary['attempts'], 2)
        folder = Path(self.bridge.outputFolder)
        self.assertFalse(list(self.root.rglob('*.csv')))
        self.call('export')
        csv_path = next(folder.glob('DETALLES_*.CSV'))
        with csv_path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(len(reader.fieldnames), 38)
            self.assertEqual(len(list(reader)), 2)
        row = self.bridge.rows[0]
        detail = self.call('detail', {'jobId': row['id']})['detail']
        self.assertEqual(len(detail['values']), 38)
        self.assertEqual(detail['result']['numero_del_dua'], row['dua'])
        self.assertEqual(len(detail['attemptHistory']), 1)
        self.call('run')
        self.assertEqual(self.bridge.summary['attempts'], 2)  # No consulta guardados.
        self.call('clean', {'confirmTableId': self.bridge.activeTable['id'], 'confirmation': 'BORRAR'})
        self.assertEqual(self.bridge.summary['total'], 0)
        self.assertEqual(self.bridge.summary['retained'], 2)
        self.call('export')
        with csv_path.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 2)
        self.assertTrue(list((self.root / 'data' / 'queues' / 'backups').glob('*.sqlite3')))
        source = self.source()
        plan = self.call('prepare_import', {'source': str(source), 'sheet': 'muestra_original', 'name': 'Prueba original'})['importPlan']
        response = self.call('import', plan)
        self.assertEqual(response['importSummary']['existing'], 2)
        self.assertEqual(self.bridge.summary['total'], 0)

    def test_cancel_restore_locks_filters_and_delete_backup(self):
        self.import_table()
        self.assertTrue(self.bridge._send('run'))
        wait_until(lambda: self.bridge.summary['running'] > 0)
        self.bridge.searchRows('pending', '', 0)
        wait_until(lambda: not any(value['command'] == 'view' for value in self.bridge._requests.values()))
        self.assertTrue(self.bridge.busy)
        self.assertFalse(self.bridge._send('rename', {'name': 'No autorizado durante ejecución'}))
        self.bridge.stopQueries()
        wait_until(lambda: not self.bridge.busy)
        self.assertEqual(self.bridge.summary['running'], 0)
        self.assertLess(self.bridge.summary['succeeded'], 2)
        self.call('run')
        self.assertEqual(self.bridge.summary['succeeded'], 2)
        self.call('view', {'filter': 'succeeded', 'search': '', 'offset': 0})
        self.assertEqual(self.bridge.rowCount, 2)
        old_id = self.bridge.activeTable['id']
        self.call('export')
        self.call('delete', {'confirmTableId': 'wrong'}, error=True)
        for confirmation in (None, '', 'borrar', ' BORRAR', 'BORRAR '):
            self.call('delete', {'confirmTableId': old_id, 'confirmation': confirmation}, error=True)
            self.assertEqual(self.bridge.activeTable['id'], old_id)
            self.assertEqual(self.bridge.summary['succeeded'], 2)
        self.call('delete', {'confirmTableId': old_id, 'confirmation': 'BORRAR'})
        self.assertEqual(self.bridge.tables, [])
        self.assertTrue(list((self.root / 'data' / 'queues' / 'backups').glob('*.sqlite3')))
        self.assertTrue(list((self.root / 'output').rglob('*.CSV')))

    def test_qml_real_page_and_shutdown_preserves_sqlite(self):
        self.import_table()
        shell = DemoBackend(HERE / 'modules.json', self.bridge)
        shell.navigate('detalles')
        prefs = Preferences(self.root / 'prefs.json', persist=False)
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
        engine.rootContext().setContextProperty('demo', shell)
        engine.rootContext().setContextProperty('details', self.bridge)
        engine.rootContext().setContextProperty('preferences', prefs)
        engine.load(QUrl.fromLocalFile(str(HERE / 'qml' / 'Main.qml')))
        self.assertTrue(engine.rootObjects(), warnings)
        window = engine.rootObjects()[0]
        wait_until(lambda: window.findChild(QObject, 'detailsRealPage') is not None)
        button = window.findChild(QObject, 'detailsStartButton')
        self.assertTrue(button.property('enabled'))
        page = window.findChild(QObject, 'detailsRealPage')
        QMetaObject.invokeMethod(page,'requestDelete',Qt.DirectConnection,Q_ARG('QVariant','table'))
        APP.processEvents()
        dialog = window.findChild(QObject,'detailsDeleteDialog')
        field = dialog.findChild(QObject,'deleteConfirmationInput')
        confirm = dialog.findChild(QObject,'deleteConfirm')
        self.assertFalse(confirm.property('enabled'))
        field.setProperty('text','BORRAR'); APP.processEvents()
        self.assertTrue(confirm.property('enabled'))
        QMetaObject.invokeMethod(dialog.findChild(QObject,'deleteCancel'),'clicked',Qt.DirectConnection)
        self.assertTrue(self.bridge.activeTable['id'])
        page.setProperty('tab', 1)
        self.bridge.showDetail(self.bridge.rows[0]['id'])
        wait_until(lambda: not self.bridge.busy)
        self.assertEqual(len(self.bridge.jobDetail['values']), 38)
        self.assertEqual(warnings, [])
        self.bridge.startQueries()
        wait_until(lambda: self.bridge.summary['running'] > 0)
        window.close()  # Cierre real de QML solicita cancelación y espera al proceso.
        wait_until(lambda: self.bridge.isClosed)
        self.assertEqual(warnings, [])
        restored = self.connect()
        self.assertEqual(restored.summary['total'], 2)
        self.assertEqual(restored.summary['running'], 0)

    def test_second_instance_cannot_mutate_a_running_table(self):
        self.import_table()
        second = self.connect()
        self.assertTrue(self.bridge._send('run'))
        wait_until(lambda: self.bridge.summary['running'] > 0)
        self.assertTrue(second._send('clean', {'confirmTableId': second.activeTable['id'], 'confirmation': 'BORRAR'}))
        wait_until(lambda: not second.busy)
        self.assertIn('otra instancia', second.error)
        self.bridge.stopQueries()
        wait_until(lambda: not self.bridge.busy)
        self.assertEqual(self.bridge.summary['total'], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
