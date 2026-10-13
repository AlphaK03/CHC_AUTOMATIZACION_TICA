"""Adaptador Qt para Detalles. Importa metadatos, nunca los paquetes del motor."""
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from remaining_time import RemainingTime

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'bots' / 'detalles'
EMPTY = {key: 0 for key in ('pending', 'running', 'retry', 'succeeded', 'invalid', 'total', 'attempts', 'source_rows', 'retained')}


class DetailsBridge(QObject):
    changed = Signal()
    remainingTimeChanged = Signal()
    toast = Signal(str)
    filePrepared = Signal()
    importPlanReady = Signal()
    detailReady = Signal()
    closed = Signal()
    # QML needs a QVariantMap to read event.command/event.event. A Python object
    # leaves those fields inaccessible and prevents save/start acknowledgements.
    eventReceived = Signal('QVariantMap')

    def __init__(self, enabled=True, storage_root=None, offline_fixture=False):
        super().__init__()
        self._enabled = enabled
        self._storage_root = str(storage_root or BOT)
        self._offline_fixture = offline_fixture
        self._snapshot = {'tables': [], 'activeTable': {}, 'summary': dict(EMPTY), 'config': {}, 'session': {}, 'fields': [], 'outputFolder': ''}
        self._runtime = {'chromiumReady': False, 'captchaEntries': 0}
        self._file_info = {'path': '', 'sheets': []}
        self._plan = {}
        self._detail = {}
        self._view = {'rows': [], 'offset': 0, 'total': 0}
        self._query = {'filter': 'all', 'search': '', 'offset': 0}
        self._events = []
        self._error = ''
        self._ready = False
        self._busy = False
        self._running = False
        self._daily_active = False
        self._daily = {'active': False, 'phase': 'stopped', 'startDate': '', 'month': '', 'monthLabel': '', 'days': [], 'driverReady': False}
        self._remaining = RemainingTime()
        self._remaining_text = ''
        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._update_remaining)
        self._closing = False
        self._status = 'Preparando módulo…' if enabled else 'Demostración'
        self._sequence = 0
        self._last_view_sequence = 0
        self._requests = {}
        self._buffer = b''
        self._stderr = ''
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.readyReadStandardError.connect(self._read_error)
        self._process.started.connect(lambda: self._send('initialize'))
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._process_error)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1500)
        self._refresh_timer.timeout.connect(self._poll_rows)

    @Property(bool, constant=True)
    def enabled(self): return self._enabled
    @Property(bool, notify=changed)
    def ready(self): return self._ready
    @Property(bool, notify=changed)
    def busy(self): return self._busy
    @Property(bool, notify=changed)
    def running(self): return self._running
    @Property(bool, notify=changed)
    def dailyActive(self): return self._daily_active
    @Property('QVariantMap', notify=changed)
    def daily(self): return self._daily
    @Property(str, notify=remainingTimeChanged)
    def remainingTime(self): return self._remaining_text
    @Property(bool, notify=changed)
    def closing(self): return self._closing
    @Property(bool, notify=changed)
    def isClosed(self): return self._process.state() == QProcess.NotRunning
    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(str, notify=changed)
    def error(self): return self._error
    @Property('QVariantMap', notify=changed)
    def summary(self): return self._snapshot['summary']
    @Property('QVariantList', notify=changed)
    def tables(self): return self._snapshot['tables']
    @Property('QVariantMap', notify=changed)
    def activeTable(self): return self._snapshot['activeTable']
    @Property('QVariantMap', notify=changed)
    def config(self): return self._snapshot['config']
    @Property('QVariantMap', notify=changed)
    def runtime(self): return self._runtime
    @Property('QVariantMap', notify=changed)
    def fileInfo(self): return self._file_info
    @Property('QVariantMap', notify=changed)
    def importPlan(self): return self._plan
    @Property('QVariantMap', notify=changed)
    def jobDetail(self): return self._detail
    @Property('QVariantList', notify=changed)
    def rows(self): return self._view['rows']
    @Property(int, notify=changed)
    def rowCount(self): return self._view['total']
    @Property(int, notify=changed)
    def offset(self): return self._view['offset']
    @Property('QVariantList', notify=changed)
    def events(self): return self._events
    @Property(str, notify=changed)
    def outputFolder(self): return self._snapshot['outputFolder']
    @Property(str, notify=changed)
    def storageRoot(self): return self._storage_root

    @Slot()
    def connectModule(self):
        if not self._enabled or self._closing or self._process.state() != QProcess.NotRunning:
            return
        python = BOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.is_file():
            self._error = 'Falta instalar Detalles. Ejecuta Instalar_Detalles.bat desde la raíz del Workbench.'
            self._status = 'Requiere instalación'
            self.changed.emit()
            return
        self._buffer = b''
        self._stderr = ''
        self._error = ''
        self._status = 'Preparando módulo…'
        self._process.setWorkingDirectory(str(BOT))
        arguments = ['-u', str(BOT / 'workbench_worker.py'), '--storage-root', self._storage_root]
        if self._offline_fixture:
            arguments.append('--offline-fixture')
        self._process.start(str(python), arguments)

    def _send(self, command, data=None):
        readonly = command in {'view', 'detail', 'daily_calendar'} and self._busy
        if self._process.state() != QProcess.Running:
            self._error = 'El módulo no está conectado. Pulsa Reconectar o revisa la instalación.'
            self.changed.emit()
            return False
        if self._busy and command not in {'stop', 'shutdown', 'view', 'detail', 'daily_calendar'}:
            self.toast.emit('Espera a que termine la operación o detén las consultas.')
            return False
        self._sequence += 1
        request = {'command': command, 'requestId': self._sequence, 'viewQuery': dict(self._query), **(data or {})}
        if command not in {'stop', 'shutdown'}:
            self._requests[self._sequence] = {'command': command, 'readonly': readonly, 'tableId': self.activeTable.get('id')}
        if command not in {'stop', 'shutdown'} and not readonly:
            self._busy = True
            self._error = ''
            self._status = {'run': 'Consultando el portal…', 'import': 'Guardando tabla…', 'export': 'Exportando resultados…'}.get(command, self._status)
        if command == 'run':
            self._running = True
            self._remaining.reset(self.summary)
            self._eta_timer.start()
            self._update_remaining()
            self._refresh_timer.start()
        elif command == 'daily_run':
            self._daily_active = True
            self._status = 'Preparando ejecución diaria…'
        self._process.write((json.dumps(request, ensure_ascii=False) + '\n').encode('utf-8'))
        self.changed.emit()
        return True

    def _read_output(self):
        self._buffer += bytes(self._process.readAllStandardOutput())
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            if not line.strip():
                continue
            try:
                self._receive(json.loads(line.decode('utf-8')))
            except (ValueError, KeyError) as error:
                self._error = f'No se pudo interpretar la respuesta del módulo: {error}'
                self.changed.emit()

    def _receive(self, event):
        kind = event['event']
        if 'snapshot' in event:
            self._snapshot = event['snapshot']
            if 'daily' in self._snapshot:
                self._daily = self._snapshot['daily']
        if 'daily' in event:
            self._daily = event['daily']
        if 'view' in event:
            request_id = event.get('requestId', 0)
            request = self._requests.get(request_id, {})
            if event.get('command') != 'view' or (request.get('tableId') == self.activeTable.get('id') and request_id >= self._last_view_sequence):
                self._view = event['view']
                self._last_view_sequence = request_id
        if kind == 'daily':
            self._daily_active = self._daily['active']
            processing = self._daily['phase'] == 'processing'
            if processing and not self._running:
                self._remaining.reset(self.summary)
                self._eta_timer.start()
                self._refresh_timer.start()
            elif not processing:
                self._clear_remaining()
                self._refresh_timer.stop()
            self._running = processing
            self._update_remaining()
            if event.get('message'):
                self._status = event['message']
        elif kind == 'progress':
            self._snapshot['summary'] = {**EMPTY, **event['summary']}
            if self._running:
                self._remaining.observe(self.summary)
                self._update_remaining()
        elif kind == 'log':
            self._events.insert(0, event)
            del self._events[2000:]
        elif kind == 'result':
            if 'runtime' in event:
                self._runtime = event['runtime']
                self._ready = True
                self._status = 'Tabla lista para consultar' if self.activeTable else 'Importa o abre una tabla'
            if 'fileInfo' in event:
                self._file_info = event['fileInfo']
                self.filePrepared.emit()
            if 'importPlan' in event:
                self._plan = event['importPlan']
                self.importPlanReady.emit()
            if 'detail' in event:
                self._detail = event['detail']
                self.detailReady.emit()
            if 'importSummary' in event:
                report = event['importSummary']
                self.toast.emit(f"Tabla guardada: {report['added']} nuevos, {report['existing']} existentes, {report['invalid']} para revisar.")
            if event.get('command') == 'run':
                self._running = False
                self._clear_remaining()
                self._refresh_timer.stop()
                self._status = {'completed': 'Completado', 'pending': 'Finalizado con pendientes', 'stopped': 'Detenido; pendientes guardados'}[event['runStatus']]
            elif event.get('command') == 'daily_run':
                self._daily_active = self._running = False
                self._clear_remaining()
                self._refresh_timer.stop()
                self._status = 'Automático detenido; progreso guardado.'
            elif event.get('command') in {'import', 'select', 'refresh'}:
                self._status = 'Todo guardado' if self.summary['total'] and self.summary['total'] == self.summary['succeeded'] else 'Pendientes listos para retomar'
            elif event.get('command') == 'configure':
                self.toast.emit('Configuración guardada.')
            elif event.get('command') == 'export':
                self._status = 'Resultados exportados'
                self.toast.emit('CSV actualizado.')
        elif kind in {'error', 'fatal'}:
            self._error = event['message']
            self._status = 'No se pudo completar la operación'
            if event.get('command') in {'run', 'daily_run'}:
                self._running = False
                self._daily_active = False
                self._clear_remaining()
                self._refresh_timer.stop()
            self.toast.emit(self._error)
        elif kind == 'stopping':
            self._status = 'Deteniendo y guardando…'
            self._clear_remaining()
        elif kind == 'idle':
            self._requests.pop(event.get('requestId'), None)
            if not event.get('readonly'):
                self._busy = False
        self.changed.emit()
        self.eventReceived.emit(event)

    def _read_error(self):
        self._stderr = (self._stderr + bytes(self._process.readAllStandardError()).decode('utf-8', errors='replace'))[-6000:]

    def _update_remaining(self):
        measuring = self._running and self._eta_timer.isActive() and not self._closing
        value = self._remaining.label(self.summary, int(self.config.get('cant_hilos', 1))) if measuring else ''
        if value != self._remaining_text:
            self._remaining_text = value
            self.remainingTimeChanged.emit()

    def _clear_remaining(self):
        self._eta_timer.stop()
        if self._remaining_text:
            self._remaining_text = ''
            self.remainingTimeChanged.emit()

    def _finished(self, exit_code, exit_status):
        self._busy = self._running = self._ready = self._daily_active = False
        self._clear_remaining()
        self._refresh_timer.stop()
        self._requests.clear()
        if self._closing:
            self.closed.emit()
        else:
            self._error = 'El proceso de Detalles se cerró. Los resultados SQLite se conservan. Reconecta para continuar.'
            if self._stderr:
                self._error += '\n' + self._stderr[-1500:]
            self._status = 'Módulo desconectado'
        self.changed.emit()

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self._busy = False
            self._error = self._process.errorString()
            self.changed.emit()
            if self._closing:
                self.closed.emit()

    def _poll_rows(self):
        if self._running and not any(value['command'] == 'view' for value in self._requests.values()):
            self._send('view', self._query)

    @Slot(str)
    def inspectExcel(self, value):
        self._send('inspect_excel', {'path': QUrl(value).toLocalFile() if value.startswith('file:') else value})

    @Slot(str, str)
    def prepareImport(self, sheet, name):
        self._send('prepare_import', {'source': self._file_info['path'], 'sheet': sheet, 'name': name})

    @Slot()
    def confirmImport(self):
        self._query = {'filter': 'all', 'search': '', 'offset': 0}
        self._send('import', self._plan)

    @Slot(str)
    def selectTable(self, table_id):
        self._query = {'filter': 'all', 'search': '', 'offset': 0}
        self._send('select', {'tableId': table_id})

    @Slot('QVariantMap')
    def saveConfig(self, values):
        self._send('configure', {'config': values})

    @Slot(str)
    def setOutput(self, value):
        path = QUrl(value).toLocalFile() if value.startswith('file:') else value
        self._send('configure', {'config': {'output_base_path': path}})

    @Slot()
    def startQueries(self): self._send('run')
    @Slot()
    def startDaily(self): self._send('daily_run')
    @Slot(str)
    def loadCalendar(self, month): self._send('daily_calendar', {'month': month})
    @Slot()
    def stopQueries(self): self._send('stop')
    @Slot()
    def exportResults(self): self._send('export')
    @Slot()
    def refresh(self): self._send('refresh')
    @Slot(str, str, int)
    def searchRows(self, status, search, offset):
        self._query = {'filter': status, 'search': search, 'offset': max(0, offset)}
        self._send('view', self._query)
    @Slot(str)
    def showDetail(self, job_id): self._send('detail', {'jobId': job_id})
    @Slot(str)
    def renameTable(self, name): self._send('rename', {'name': name})
    @Slot('QVariantList', str)
    def removeRows(self, ids, table_id): self._send('remove_rows', {'ids': ids, 'confirmTableId': table_id})
    @Slot(str)
    def cleanCompleted(self, table_id): self._send('clean', {'confirmTableId': table_id})
    @Slot(str)
    def deleteTable(self, table_id): self._send('delete', {'confirmTableId': table_id})
    @Slot()
    def clearActivity(self):
        self._events = []
        self.changed.emit()
    @Slot()
    def openOutput(self):
        if self.outputFolder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.outputFolder))
    @Slot()
    def openLogs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._storage_root) / 'logs')))
    @Slot()
    def openEvidence(self):
        evidence = self._detail.get('evidence', '')
        if evidence and Path(evidence).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(evidence))
        else:
            self.toast.emit('No se encuentra la evidencia HTML; revisa los diagnósticos del lote.')
    @Slot()
    def openBackups(self):
        folder = Path(self._storage_root) / 'data' / 'queues' / 'backups'
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    @Slot()
    def openClassic(self):
        if self._busy or self._running:
            self.toast.emit('Detén la ejecución antes de abrir la interfaz clásica.')
            return
        if Path(self._storage_root).resolve() != BOT.resolve():
            self.toast.emit('La interfaz clásica usa la instalación normal; no está disponible en pruebas aisladas.')
            return
        python = BOT / '.venv' / 'Scripts' / 'pythonw.exe'
        result = QProcess.startDetached(str(python), [str(BOT / 'src' / 'main.py')], str(BOT))
        self.toast.emit('Interfaz clásica abierta: comparte las tablas de esta copia.' if result[0] else 'No se pudo abrir la interfaz clásica.')
    @Slot()
    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        if self._process.state() == QProcess.NotRunning:
            self.closed.emit()
            return
        if self._process.state() == QProcess.Starting:
            self._process.started.connect(lambda: self._send('shutdown'))
        else:
            self._send('shutdown')
        self._status = 'Cerrando y guardando pendientes…'
        self.changed.emit()
