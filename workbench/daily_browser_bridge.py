"""Una preparación del navegador por apertura, en un proceso ajeno a Qt/bots."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from chc_runtime.distribution import packaged

ROOT = Path(__file__).resolve().parents[1]


class DailyBrowserSetup(QObject):
    changed = Signal()
    closed = Signal()
    messageReceived = Signal(str)

    def __init__(self, enabled=True, parent=None):
        super().__init__(parent)
        self.enabled = enabled and not packaged()
        self.ready = not self.enabled
        self.busy = self.enabled
        self.error = ''
        self.message = 'Comprobando navegador para las bases diarias…' if self.enabled else ''
        self.started = False
        self.closing = False
        self._buffer = b''
        self._stderr = ''
        self._result = None
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(ROOT))
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(self._read_error)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._failed)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180000)
        self.timer.timeout.connect(self._timeout)

    @property
    def isClosed(self):
        return self.process.state() == QProcess.NotRunning

    def start(self):
        if not self.enabled or self.started or self.closing:
            return
        self.started = True
        python = Path(sys.executable)
        if python.name.lower() == 'pythonw.exe':
            python = python.with_name('python.exe')
        self.process.start(str(python), ['-u', str(ROOT / 'tools/install_daily_driver.py'), '--json'])
        self.timer.start()
        self.changed.emit()

    def _read(self):
        self._buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            try:
                event = json.loads(line.decode('utf-8'))
            except (ValueError, UnicodeError):
                self.error = 'No se pudo leer la preparación del navegador.'
                continue
            self.message = event.get('message', self.message)
            if event.get('event') == 'result':
                self._result = event
            elif event.get('event') == 'error':
                self.error = self.message
            self.messageReceived.emit(self.message)
            self.changed.emit()

    def _read_error(self):
        self._stderr = (self._stderr + bytes(self.process.readAllStandardError()).decode('utf-8', 'replace'))[-2000:]

    def _finished(self, code, status):
        self._read()
        self._read_error()
        self.timer.stop()
        self.busy = False
        self.ready = code == 0 and status == QProcess.NormalExit and self._result is not None and not self.error and not self.closing
        if not self.ready and not self.error and not self.closing:
            self.error = 'No se pudo preparar el navegador. Ejecuta Instalar_Base_Diaria.bat y vuelve a iniciar.'
            if self._stderr:
                self.error += '\n' + self._stderr
        self.changed.emit()
        self.closed.emit()

    def _failed(self, error):
        if error == QProcess.FailedToStart:
            self.timer.stop()
            self.busy = False
            self.error = 'No se pudo iniciar la preparación del navegador: ' + self.process.errorString()
            self.changed.emit()
            self.closed.emit()

    def _timeout(self):
        self.error = 'La preparación del navegador tardó demasiado. Ejecuta Instalar_Base_Diaria.bat para reintentar.'
        self.changed.emit()
        self.shutdown()

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        if self.isClosed:
            self.busy = False
            self.closed.emit()
        else:
            self.process.write(b'stop\n')
            self.process.closeWriteChannel()
            # La descarga publica solo después de comprobar cancelación y limpia
            # sus temporales al salir. Último recurso ante una E/S sin respuesta.
            QTimer.singleShot(90000, self._force_shutdown)

    def _force_shutdown(self):
        if not self.isClosed:
            self.process.kill()
