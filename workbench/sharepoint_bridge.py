"""Conexión opcional y cola online; los bots nunca esperan por SharePoint."""
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, Property, QProcess, QTimer, Signal, Slot
from process_guard import ProcessTreeGuard

ROOT = Path(__file__).resolve().parents[1]


class SharePointBridge(QObject):
    changed = Signal()
    closed = Signal()
    toast = Signal(str)

    def __init__(self, storage=None, enabled=True, parent=None):
        super().__init__(parent)
        self.storage = Path(storage or ROOT/'runtime/workbench/sharepoint')
        self._enabled = enabled
        self._snapshot = {'connected':False,'account':'','destination':{},'tasks':[],'pending':0,'localRoot':'','months':[]}
        self._browse, self._queue, self._buffer = {}, [], b''
        self._busy = self._ready = self._closing = False
        self._error = ''
        self._status = 'La app puede trabajar sin conectar una cuenta.'
        self.process = QProcess(self)
        self.guard = ProcessTreeGuard()
        self.process.started.connect(self._started)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(lambda: self.process.readAllStandardError())
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._failed)
        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self._sync_tick)
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.setInterval(10000)
        self.close_timer.timeout.connect(self._force_close)

    @Property(bool, constant=True)
    def enabled(self): return self._enabled
    @Property(bool, notify=changed)
    def connected(self): return self._snapshot['connected']
    @Property(str, notify=changed)
    def account(self): return self._snapshot['account']
    @Property('QVariantMap', notify=changed)
    def destination(self): return self._snapshot['destination']
    @Property(str, notify=changed)
    def localRoot(self): return self._snapshot['localRoot']
    @Property('QVariantList', notify=changed)
    def months(self): return self._snapshot['months']
    @Property('QVariantList', notify=changed)
    def tasks(self): return self._snapshot['tasks']
    @Property(int, notify=changed)
    def pending(self): return self._snapshot['pending']
    @Property('QVariantMap', notify=changed)
    def browse(self): return self._browse
    @Property(bool, notify=changed)
    def busy(self): return self._busy or bool(self._queue)
    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(str, notify=changed)
    def error(self): return self._error
    @Property(bool, notify=changed)
    def isClosed(self): return self.process.state()==QProcess.NotRunning

    def _started(self):
        try:
            self.guard.attach(int(self.process.processId()))
        except OSError:
            self._error = 'No se pudo aislar el proceso de SharePoint.'
            self.process.kill()

    def send(self, command, data=None):
        if not self.enabled or self._closing:
            return
        self._queue.append({'command':command, **(data or {})})
        if self.process.state()==QProcess.NotRunning:
            self._ready=False
            self._buffer=b''
            self.process.setWorkingDirectory(str(ROOT))
            self.process.start(str(ROOT/'workbench/.venv/Scripts/python.exe'), ['-u','-m','chc_cloud.worker','--storage',str(self.storage),
                                              '--app',str(ROOT/'workbench/sharepoint_app.json')])
        self._dispatch()

    def _dispatch(self):
        if self._ready and not self._busy and self._queue:
            request=self._queue.pop(0)
            self._busy=True
            self._error=''
            self._status='Conecta tu cuenta en el navegador…' if request['command']=='connect' else 'Consultando SharePoint…'
            self.process.write((json.dumps(request,ensure_ascii=False)+'\n').encode('utf-8'))
        self.changed.emit()

    def _read(self):
        self._buffer+=bytes(self.process.readAllStandardOutput())
        while b'\n' in self._buffer:
            line,self._buffer=self._buffer.split(b'\n',1)
            try:
                event=json.loads(line)
            except ValueError:
                continue
            kind=event.get('event')
            if kind=='ready':
                self._ready=True
                self._dispatch()
            elif kind=='result':
                self._snapshot=event['snapshot']
                self._error=self._snapshot.get('queueError','')
                if 'browse' in event:self._browse=event['browse']
                self._status=f"{self.pending} publicaciones pendientes." if self.pending else 'Sin envíos pendientes.' if self.connected else 'Guardado local; cuenta desconectada.'
                if event.get('command')=='save':self.toast.emit('Carpeta común guardada para todos los bots.')
            elif kind=='error':
                self._error=event['message']
                self._status='El trabajo local continúa.'
                self.toast.emit(self._error)
            elif kind=='idle':
                self._busy=False
                self._dispatch()
            self.changed.emit()

    def _finished(self, *args):
        self.close_timer.stop()
        self.guard.close()
        self._busy=self._ready=False
        self._queue.clear()
        if not self._closing:
            self._error='SharePoint se desconectó. Las descargas locales continúan; puedes volver a conectar.'
        self.changed.emit()
        self.closed.emit()

    def _failed(self, *args):
        self._error='No se pudo abrir la conexión SharePoint. Ejecuta Instalar_Workbench.bat.'
        if self.process.state()==QProcess.NotRunning:
            self._queue.clear()
            self._busy=False
        self.changed.emit()

    def _sync_tick(self):
        return

    @Slot()
    def refresh(self): self.send('status')
    @Slot()
    def connectAccount(self): self.send('connect')
    @Slot()
    def disconnectAccount(self): self.send('disconnect')
    @Slot(str)
    def openSite(self, url): self.send('site',{'url':url})
    @Slot(str, str)
    def searchSites(self, url, query): self.send('sites',{'url':url,'search':query})
    @Slot(str, str)
    def openFolder(self, drive, item): self.send('folders',{'drive':drive,'item':item})
    @Slot(str, str)
    def saveDestination(self, drive, item): self.send('save',{'drive':drive,'item':item})
    @Slot()
    def removeDestination(self): self.send('remove')
    @Slot()
    def retry(self): self.send('retry')
    @Slot(str)
    def uploadMonth(self, month): self.send('upload_month',{'month':month})
    @Slot(str)
    def setLocalRoot(self, path): self.send('local_root',{'path':path})

    def publication(self, module, event):
        return  # Guardar o exportar localmente nunca inicia una subida.

    @Slot()
    def shutdown(self):
        self._closing=True
        self.timer.stop()
        self._queue.clear()
        if self.process.state()!=QProcess.NotRunning:
            self.process.write(b'{"command":"shutdown"}\n')
            self.close_timer.start()
        else:self.closed.emit()

    def _force_close(self):
        self.guard.close()
        self.process.kill()
