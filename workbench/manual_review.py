"""Navegador de revisión por proceso, independiente del worker de descarga."""
import json
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, Signal, Slot
from process_guard import ProcessTreeGuard

ROOT = Path(__file__).resolve().parents[1]


class ManualReview(QObject):
    changed = Signal()
    closed = Signal()
    toast = Signal(str)

    def __init__(self, module, root, fixture=False, parent=None):
        super().__init__(parent)
        self.module, self.root, self.fixture = module, str(root), fixture
        self._status = self._error = ''
        self._closing = False
        self.buffer = b''
        self.stderr = ''
        self.request = None
        self._stop_requested = False
        self.process = QProcess(self)
        self.guard = ProcessTreeGuard()
        self.process.started.connect(self.started)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.force_close)

    @Property(bool, notify=changed)
    def running(self): return self.process.state() != QProcess.NotRunning
    @Property(bool, notify=changed)
    def isClosed(self): return not self.running
    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(str, notify=changed)
    def error(self): return self._error

    def open(self, request):
        if self._closing:
            return False
        if self.running:
            self.toast.emit('Cierra la revisión actual antes de abrir otra consulta de este bot.')
            return False
        python = ROOT / 'bots' / self.module / '.venv/Scripts/python.exe'
        if not python.is_file():
            self.toast.emit('Falta instalar el entorno de este bot.')
            return False
        self.buffer = b''
        self.stderr = ''
        self._error = ''
        self._status = 'Abriendo revisión en TICA…'
        self.request = request
        self._stop_requested = False
        args = ['-u', '-m', 'chc_runtime.manual_review', '--module', self.module, '--storage-root', self.root]
        if self.fixture:
            args.append('--offline-fixture')
        self.process.setWorkingDirectory(str(ROOT))
        self.process.start(str(python), args)
        self.changed.emit()
        return True

    def started(self):
        try:
            self.guard.attach(int(self.process.processId()))
        except OSError as exc:
            self._error = str(exc)
            self.process.kill()
            return
        self.process.write((json.dumps(self.request, ensure_ascii=False) + '\n').encode('utf-8'))
        if self._closing or self._stop_requested:
            self.stop()

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                event = json.loads(line)
            except ValueError:
                self._error = 'La revisión devolvió una respuesta inválida.'
                continue
            self._status = event.get('message', self._status)
            if event.get('event') == 'error':
                self._error = self._status
                self.toast.emit(self._status)
        self.changed.emit()

    def read_error(self):
        self.stderr = (self.stderr + bytes(self.process.readAllStandardError()).decode('utf-8', errors='replace'))[-3000:]

    def failed(self, _):
        if self._closing or self._stop_requested:return
        self._error = self.process.errorString()
        self._status = 'No se pudo abrir la revisión.'
        self.changed.emit()
        self.toast.emit(self._error)
        if not self.running:
            self.closed.emit()

    def finished(self, code, _):
        self.timer.stop()
        self.guard.close()
        if code and not self._closing and not self._stop_requested and not self._error:
            self._error = self.stderr[-700:] or f'La revisión se cerró con error ({code}).'
            self.toast.emit(self._error)
        elif not self._error:
            self._status = 'Revisión cerrada; el progreso del lote se conserva.'
        self.changed.emit()
        self.closed.emit()

    @Slot()
    def stop(self):
        self._stop_requested = True
        if self.process.state() == QProcess.Running:
            self.process.write(b'{"command":"close"}\n')
        if self.running:
            self.timer.start()

    def shutdown(self):
        self._closing = True
        self.stop()

    def force_close(self):
        self.guard.close()
        self.process.kill()
