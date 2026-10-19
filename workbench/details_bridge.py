"""Adaptador Qt común por módulo; nunca importa los paquetes del motor."""
import json
import os
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from remaining_time import RemainingTime
from process_guard import ProcessTreeGuard
from activity_model import ActivityModel
from live_activity import LiveActivity
from manual_review import ManualReview
from daily_marks import DailyMarks

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'bots' / 'detalles'
EMPTY = {key: 0 for key in ('pending', 'running', 'retry', 'succeeded', 'invalid', 'empty', 'total', 'attempts', 'source_rows', 'retained')}


class DetailsBridge(QObject):
    changed = Signal()
    calendarMarksChanged = Signal()
    remainingTimeChanged = Signal()
    toast = Signal(str)
    filePrepared = Signal()
    importPlanReady = Signal()
    detailReady = Signal()
    closed = Signal()
    # QML needs a QVariantMap to read event.command/event.event. A Python object
    # leaves those fields inaccessible and prevents save/start acknowledgements.
    eventReceived = Signal('QVariantMap')

    def __init__(self, enabled=True, storage_root=None, offline_fixture=False, module_id='detalles'):
        super().__init__()
        if module_id not in ('detalles', 'duas_transito', 'talon', 'xmovimientos'):
            raise ValueError('Módulo sin integración operativa.')
        self._module_id = module_id
        self._bot = ROOT / 'bots' / module_id
        self._enabled = enabled
        self._storage_root = str(storage_root or self._bot)
        self._day_marks = DailyMarks(self._storage_root)
        self._offline_fixture = offline_fixture
        self._review = ManualReview(module_id, self._storage_root, offline_fixture, self)
        self._review.toast.connect(self.toast.emit)
        self._review.closed.connect(self._review_closed)
        self._snapshot = {'tables': [], 'activeTable': {}, 'summary': dict(EMPTY), 'config': {}, 'session': {}, 'fields': [], 'outputFolder': ''}
        self._runtime = {'chromiumReady': False, 'captchaEntries': 0}
        self._file_info = {'path': '', 'sheets': []}
        self._plan = {}
        self._detail = {}
        self._view = {'rows': [], 'offset': 0, 'total': 0}
        self._query = {'filter': 'all', 'search': '', 'offset': 0}
        self._events = []
        self._last_daily_message = ''
        self._activity_model = ActivityModel(parent=self)
        self._console = LiveActivity(self)
        self._error = ''
        self._error_command = ''
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
        self._process_guard = ProcessTreeGuard()
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        self._shutdown_timer.setInterval(30000)
        self._shutdown_timer.timeout.connect(self._force_shutdown)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.readyReadStandardError.connect(self._read_error)
        self._process.started.connect(self._started)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._process_error)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1500)
        self._refresh_timer.timeout.connect(self._poll_rows)

    @Property(bool, constant=True)
    def enabled(self): return self._enabled
    @Property(str, constant=True)
    def moduleId(self): return self._module_id
    @Property(str, constant=True)
    def moduleTitle(self):
        return {'detalles': 'Detalles', 'duas_transito': 'DUAs Tránsito',
                'talon': 'Talón', 'xmovimientos': 'XMovimientos'}[self._module_id]
    @Property(bool, constant=True)
    def supportsLightweight(self): return self._module_id == 'detalles'
    @Property(bool, constant=True)
    def supportsClassic(self): return self._module_id == 'detalles'
    @Property(bool, notify=changed)
    def ready(self): return self._ready
    @Property(bool, notify=changed)
    def busy(self): return self._busy
    @Property(bool, notify=changed)
    def loading(self):
        if not self._enabled or self._closing or self._error or self._running or self._daily_active:
            return False
        return not self._ready or any(request['command'] in {
            'initialize','select','refresh','inspect_excel','prepare_import','import'
        } and not request.get('readonly') for request in self._requests.values())
    @Property(bool, notify=changed)
    def running(self): return self._running
    @Property(bool, notify=changed)
    def dailyActive(self): return self._daily_active
    @Property('QVariantMap', notify=changed)
    def daily(self):
        return {**self._daily, 'days': [
            {**day, 'manualCompleted': day.get('date') in self._day_marks.values}
            for day in self._daily['days']]}
    @Property(str, notify=remainingTimeChanged)
    def remainingTime(self): return self._remaining_text
    @Property(bool, notify=changed)
    def closing(self): return self._closing
    @Property(bool, notify=changed)
    def isClosed(self): return self._process.state() == QProcess.NotRunning and self._review.isClosed
    @Property(QObject, constant=True)
    def manualReview(self): return self._review
    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(str, notify=changed)
    def error(self): return self._error
    @Property('QVariantMap', notify=changed)
    def summary(self): return self._snapshot['summary']
    @Property('QVariantList', notify=changed)
    def activeJobs(self): return self.summary.get('active_duas', []) if self.running else []
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
    @Property(QObject, constant=True)
    def activityModel(self): return self._activity_model
    @Property(QObject, constant=True)
    def consoleMonitor(self): return self._console
    @Property(str, notify=changed)
    def outputFolder(self): return self._snapshot['outputFolder']
    @Property(str, notify=changed)
    def storageRoot(self): return self._storage_root

    @Slot()
    def connectModule(self):
        if not self._enabled or self._closing or self._process.state() != QProcess.NotRunning:
            return
        python = self._bot / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.is_file():
            installer = {'detalles': 'Instalar_Detalles.bat', 'duas_transito': 'Instalar_Transito.bat',
                         'talon': 'Instalar_Talon.bat', 'xmovimientos': 'Instalar_XMovimientos.bat'}[self._module_id]
            self._error = f'Falta instalar {self.moduleTitle}. Ejecuta {installer} desde la raíz del Workbench.'
            self._status = 'Requiere instalación'
            self.changed.emit()
            return
        self._buffer = b''
        self._stderr = ''
        self._error = ''
        self._status = 'Preparando módulo…'
        self._console.begin('Cargando módulo…')
        self._process.setWorkingDirectory(str(self._bot))
        arguments = ['-u', str(self._bot / 'workbench_worker.py'), '--storage-root', self._storage_root]
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
            self._console.begin()
            self._busy = True
            self._error = ''
            self._error_command = ''
            self._status = {'run': 'Consultando el portal…', 'import': 'Guardando tabla…', 'export': 'Exportando resultados…'}.get(command, self._status)
        if command in {'run', 'retry_empty'}:
            self._running = True
            self._remaining.reset(self.summary)
            self._eta_timer.start()
            self._update_remaining()
            self._refresh_timer.start()
        elif command in {'daily_run','retry_month','retry_day'}:
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
        self._console.accept(event)
        if kind == 'activity_state':
            return
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
                if event.get('command') == 'view' and self._error_command == 'view':
                    self._error = self._error_command = ''
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
                if self._last_daily_message != event['message']:
                    self._last_daily_message = event['message']
                    self._activity_model.prepend({'message':event['message'],'time':time.strftime('%H:%M:%S'),'level':'INFO'})
        elif kind == 'progress':
            self._snapshot['summary'] = {**EMPTY, **event['summary']}
            if self._running:
                self._remaining.observe(self.summary)
                self._update_remaining()
        elif kind == 'log':
            self._events.insert(0, event)
            del self._events[2000:]
            self._activity_model.prepend(event)
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
            if event.get('command') in {'run', 'retry_empty'}:
                self._running = False
                self._clear_remaining()
                self._refresh_timer.stop()
                self._status = {'completed': 'Completado', 'pending': 'Finalizado con pendientes', 'stopped': 'Detenido; pendientes guardados'}[event['runStatus']]
            elif event.get('command') in {'daily_run','retry_month','retry_day'}:
                self._daily_active = self._running = False
                self._clear_remaining()
                self._refresh_timer.stop()
                self._status = 'Rango completado; resultados guardados.' if event.get('runStatus') == 'completed' else 'Rango revisado; quedan pendientes para revisión manual.' if event.get('runStatus')=='pending' else 'Automático detenido; progreso guardado.'
            elif event.get('command') in {'import', 'select', 'refresh'}:
                self._status = 'Todo consultado' if self.summary['total'] and self.summary['total'] == self.summary['succeeded'] + self.summary.get('empty', 0) else 'Pendientes listos para retomar'
            elif event.get('command') == 'configure':
                self.toast.emit('Configuración guardada.')
            elif event.get('command') == 'export':
                self._status = 'Resultados exportados'
                self.toast.emit('CSV actualizado.')
        elif kind in {'error', 'fatal'}:
            self._activity_model.prepend({'message':event['message'],'time':time.strftime('%H:%M:%S'),'level':'ERROR'})
            if kind == 'fatal':self._console.finish()
            command = event.get('command', '')
            # Un lector tardío no debe ocultar un fallo real del motor.
            if command != 'view' or not self._error or self._error_command == 'view':
                self._error = event['message']
                self._error_command = command
            if command != 'view':
                self._status = 'No se pudo completar la operación'
            if event.get('command') in {'run', 'retry_empty', 'daily_run','retry_month','retry_day'}:
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
                self._console.finish()
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
        self._console.finish()
        self._shutdown_timer.stop()
        self._process_guard.close()
        self._busy = self._running = self._ready = self._daily_active = False
        self._clear_remaining()
        self._refresh_timer.stop()
        self._requests.clear()
        if self._closing:
            self.closed.emit()
        else:
            self._error = f'El proceso de {self.moduleTitle} se cerró. Los resultados SQLite se conservan. Reconecta para continuar.'
            if self._stderr:
                self._error += '\n' + self._stderr[-1500:]
            self._status = 'Módulo desconectado'
        self.changed.emit()

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self._console.finish()
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

    def request(self, command, data=None):
        """Inicio coordinado: conservar el identificador de su respuesta exacta."""
        return self._sequence if self._send(command,data) else 0

    @Slot(str)
    def setOutput(self, value):
        path = QUrl(value).toLocalFile() if value.startswith('file:') else value
        self._send('configure', {'config': {'output_base_path': path}})

    @Slot()
    def startQueries(self): self._send('run')
    @Slot()
    def startDaily(self): self._send('daily_run')
    @Slot(str)
    def retryMonth(self, month): self._send('retry_month', {'month':month})
    @Slot(str)
    def retryDay(self, day): self._send('retry_day', {'day':day})
    @Slot(str, bool)
    def markCalendarDay(self, day, completed):
        if not self._enabled or not self._ready or self._closing:
            return
        selected = next((item for item in self._daily['days'] if item.get('date') == day), {})
        if not selected.get('available'):
            self.toast.emit('Elige un día disponible del calendario.')
            return
        try:
            self._day_marks.set_completed(day, completed)
        except (OSError, ValueError) as error:
            self.toast.emit(f'No se pudo guardar la marca del día: {error}')
            return
        self.changed.emit()
        self.calendarMarksChanged.emit()
        self.toast.emit('Día marcado como completado manual.' if completed else 'Marca manual quitada.')
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
    def openInTica(self, job_id):
        if self.enabled and not self.closing and self.activeTable.get('id'):
            self._review.open({'tableId': self.activeTable['id'], 'jobId': job_id})
    @Slot(str)
    def renameTable(self, name): self._send('rename', {'name': name})
    @Slot('QVariantList', str, str)
    def removeRows(self, ids, table_id, confirmation): self._send('remove_rows', {'ids': ids, 'confirmTableId': table_id, 'confirmation': confirmation})
    @Slot(str, str)
    def cleanCompleted(self, table_id, confirmation): self._send('clean', {'confirmTableId': table_id, 'confirmation': confirmation})
    @Slot(str, str)
    def deleteTable(self, table_id, confirmation): self._send('delete', {'confirmTableId': table_id, 'confirmation': confirmation})
    @Slot()
    def clearActivity(self):
        self._events = []
        self._activity_model.clear()
        self.changed.emit()
    @Slot()
    def openOutput(self):
        if self.outputFolder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.outputFolder))
    @Slot()
    def openLogs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._storage_root) / 'logs')))
    @Slot('QVariantList')
    def retryEmpty(self, ids):
        self._send('retry_empty', {'ids': list(ids) if ids else None})

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
        if not self.supportsClassic:
            self.toast.emit('La interfaz anterior de Tránsito usa datos independientes; utiliza el módulo del Workbench.')
            return
        if self._busy or self._running:
            self.toast.emit('Detén la ejecución antes de abrir la interfaz clásica.')
            return
        if Path(self._storage_root).resolve() != self._bot.resolve():
            self.toast.emit('La interfaz clásica usa la instalación normal; no está disponible en pruebas aisladas.')
            return
        python = self._bot / '.venv' / 'Scripts' / 'pythonw.exe'
        result = QProcess.startDetached(str(python), [str(self._bot / 'src' / 'main.py')], str(self._bot))
        self.toast.emit('Interfaz clásica abierta: comparte las tablas de esta copia.' if result[0] else 'No se pudo abrir la interfaz clásica.')
    @Slot()
    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        self._review.shutdown()
        if self._process.state() == QProcess.NotRunning:
            self.closed.emit()
            return
        if self._process.state() == QProcess.Starting:
            self._process.started.connect(lambda: self._send('shutdown'))
        else:
            self._send('shutdown')
        self._shutdown_timer.start()
        self._status = 'Cerrando y guardando pendientes…'
        self.changed.emit()

    def _review_closed(self):
        self.changed.emit()
        if self._closing and self.isClosed:
            self.closed.emit()

    def _started(self):
        try:
            self._process_guard.attach(self._process.processId())
        except OSError as error:
            self._error = f'No se pudo proteger el cierre del módulo: {error}'
            self.toast.emit(self._error)
            self._process.kill()
            return
        self._send('initialize')

    def _force_shutdown(self):
        # Último recurso: SQLite conserva cada éxito ya confirmado. Las reservas
        # incompletas se recuperan al iniciar el siguiente lote.
        self._process_guard.close()
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
