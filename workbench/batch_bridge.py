"""Puente Qt para procedimientos independientes; no importa motores de bots."""
import json
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from process_guard import ProcessTreeGuard

ROOT = Path(__file__).resolve().parents[1]
EMPTY = {'config':{}, 'history':[], 'activeId':'', 'jobs':[], 'outputFolder':'', 'lastBase':'', 'baseInfo':{},
         'summary':{k:0 for k in ('total','succeeded','pending','running','excluded','rows','invalid')}}


class BatchChannel(QObject):
    changed = Signal()
    eventReceived = Signal('QVariantMap')
    closed = Signal()

    def __init__(self, module, flow, root, fixture=False, parent=None):
        super().__init__(parent)
        self.module, self.flow, self.root, self.fixture = module, flow, Path(root), fixture
        self.snapshot = dict(EMPTY)
        self.ready = self.busy = self.closing = False
        self.error = ''
        self.buffer = b''
        self.stderr = ''
        self.pending = None
        self.process = QProcess(self)
        self.guard = ProcessTreeGuard()
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.started.connect(self.started)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(25000)
        self.timer.timeout.connect(self.force_close)

    def started(self):
        try:
            self.guard.attach(int(self.process.processId()))
        except OSError as exc:
            self.error = str(exc)
            self.process.kill()

    def start(self):
        if self.process.state() != QProcess.NotRunning:
            return True
        bot = ROOT/'bots'/self.module
        python = bot/'.venv/Scripts/python.exe'
        if not python.is_file():
            self.error = 'Ejecute Instalar_'+('BLs' if self.module=='bls' else 'Manifiestos')+'.bat.'
            self.changed.emit()
            return False
        self.ready = self.closing = False
        self.buffer = b''
        self.error = ''
        args = ['-u',str(bot/'workbench_worker.py'),'--flow',self.flow,'--storage-root',str(self.root)]
        if self.fixture:
            args.append('--offline-fixture')
        self.process.setWorkingDirectory(str(bot))
        self.process.start(str(python),args)
        return True

    def send(self, command, data=None):
        if self.busy and command not in ('stop','shutdown'):
            return False
        request = {'command':command, **(data or {})}
        if not self.ready and command not in ('stop','shutdown'):
            if not self.start():
                return False
            self.pending = request
            self.busy = True
        elif self.process.state() == QProcess.Running:
            self.process.write((json.dumps(request,ensure_ascii=False)+'\n').encode())
            if command not in ('stop','shutdown'):
                self.busy = True
                self.error = ''
        else:
            return False
        self.changed.emit()
        return True

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer = self.buffer.split(b'\n',1)
            try:
                event = json.loads(line)
            except ValueError:
                self.error = 'El motor devolvió una respuesta inválida.'
                continue
            if 'snapshot' in event:
                self.snapshot = event['snapshot']
            kind = event['event']
            if kind == 'ready':
                self.ready = True
                if self.pending:
                    self.process.write((json.dumps(self.pending,ensure_ascii=False)+'\n').encode())
                    self.pending = None
            elif kind == 'idle':
                self.busy = False
            elif kind == 'error':
                self.error = event.get('message','Error del motor')
            self.changed.emit()
            self.eventReceived.emit(event)

    def read_error(self):
        self.stderr = (self.stderr+bytes(self.process.readAllStandardError()).decode('utf-8',errors='replace'))[-6000:]

    def finished(self, code, status):
        self.timer.stop()
        self.guard.close()
        self.ready = self.busy = False
        if not self.closing:
            self.error = self.error or f'El motor se desconectó ({code}). Puede retomar el progreso guardado. '+self.stderr[-700:]
        self.changed.emit()
        self.closed.emit()

    def failed(self, error):
        self.error = self.process.errorString()
        if self.process.state() == QProcess.NotRunning:
            self.busy = False
            self.pending = None
        self.changed.emit()

    def shutdown(self):
        self.closing = True
        self.pending = None
        if self.process.state() != QProcess.NotRunning:
            self.process.write(b'{"command":"shutdown"}\n')
            self.timer.start()
        else:
            self.closed.emit()

    def force_close(self):
        self.guard.close()
        self.process.kill()


class BatchBridge(QObject):
    changed = Signal()
    toast = Signal(str)
    closed = Signal()
    eventReceived = Signal('QVariantMap')
    baseBuilt = Signal(str)
    filePrepared = Signal(str)

    def __init__(self, module_id='manifiestos', enabled=True, storage_root=None, offline_fixture=False):
        super().__init__()
        self._module = module_id
        self._enabled = enabled
        self._closing = False
        self._flow = 'bls' if module_id=='bls' else 'conocimientos'
        self._root = Path(storage_root or ROOT/'bots'/module_id).resolve()
        flows = ['bls'] if module_id=='bls' else ['tabla','conocimientos','duas','movimientos','contenedores','bases']
        self.channels = {flow:BatchChannel(module_id,flow,self._root,offline_fixture,self) for flow in flows}
        for flow,channel in self.channels.items():
            channel.changed.connect(self.changed.emit)
            channel.eventReceived.connect(lambda event, f=flow:self.receive(f,event))
            channel.closed.connect(self.check_closed)

    def current(self): return self.channels[self._flow]
    @Property(bool, constant=True)
    def enabled(self): return self._enabled
    @Property(bool, constant=True)
    def isBls(self): return self._module=='bls'
    @Property(str, notify=changed)
    def flow(self): return self._flow
    @Property(bool, notify=changed)
    def ready(self): return self.current().ready
    @Property(bool, notify=changed)
    def busy(self): return self.current().busy
    @Property(bool, notify=changed)
    def running(self): return any(c.busy for c in self.channels.values())
    @Property(bool, notify=changed)
    def dailyActive(self): return False
    @Property(bool, notify=changed)
    def closing(self): return self._closing
    @Property(bool, notify=changed)
    def isClosed(self): return all(c.process.state()==QProcess.NotRunning for c in self.channels.values())
    @Property(str, notify=changed)
    def error(self): return self.current().error
    @Property('QVariantMap', notify=changed)
    def config(self): return self.current().snapshot['config']
    @Property('QVariantMap', notify=changed)
    def summary(self): return self.current().snapshot['summary']
    @Property('QVariantList', notify=changed)
    def jobs(self): return self.current().snapshot['jobs']
    @Property('QVariantList', notify=changed)
    def history(self): return self.current().snapshot['history']
    @Property(str, notify=changed)
    def activeId(self): return self.current().snapshot['activeId']
    @Property(str, notify=changed)
    def status(self): return self.current().snapshot.get('message') or ('Listo' if self.ready else 'Preparando…')
    @Property('QVariantMap', notify=changed)
    def baseInfo(self): return self.channels.get('bases',self.current()).snapshot.get('baseInfo',{})
    @Property(bool, notify=changed)
    def baseBusy(self): return self.channels.get('bases',self.current()).busy
    @Property(str, notify=changed)
    def baseError(self): return self.channels.get('bases',self.current()).error
    @Property(str, notify=changed)
    def lastBase(self): return self.channels.get('bases',self.current()).snapshot.get('lastBase','')
    @Property(str, constant=True)
    def defaultBaseFolder(self): return str(self._root/'bases_bls')
    @Property(str, notify=changed)
    def activity(self): return self.current().stderr.splitlines()[-1] if self.current().stderr else ''

    @Slot()
    def connectModule(self):
        if self.enabled:
            self.current().send('refresh')
            if 'bases' in self.channels:
                self.channels['bases'].send('refresh')

    @Slot(str)
    def setFlow(self, flow):
        if flow in self.channels and flow!='bases':
            self._flow = flow
            if not self.current().ready and not self.current().busy:
                self.current().send('refresh')
            self.changed.emit()

    @Slot(str, 'QVariantMap', result=bool)
    def command(self, name, data):
        return self.current().send(name,data) if self.enabled else False

    @Slot(str, 'QVariantMap', result=bool)
    def baseCommand(self, name, data):
        return self.channels['bases'].send(name,data) if self.enabled else False

    @Slot()
    def stop(self): self.current().send('stop')
    @Slot()
    def stopBase(self): self.channels['bases'].send('stop')
    @Slot()
    def shutdown(self):
        self._closing = True
        for channel in self.channels.values():
            channel.shutdown()
        self.changed.emit()

    def check_closed(self):
        if self._closing and self.isClosed:
            self.closed.emit()

    @Slot(str)
    def openPath(self, value):
        path = Path(value)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def openResults(self): self.openPath(self.current().snapshot.get('outputFolder',''))

    @Slot(str)
    def useBase(self, path):
        if self.isBls and not self.busy:
            self.current().send('configure',{'config':{'input':path,'sheet':'BLS'}})

    def receive(self, flow, event):
        self.eventReceived.emit({**event,'flow':flow})
        if event.get('event') == 'error':
            self.toast.emit(event.get('message','Error'))
        if 'baseResult' in event:
            result = event['baseResult']
            self.baseBuilt.emit(result['output'])
            self.toast.emit(f"Base BLs generada: {result.get('exported',0)} conocimientos.")
        if event.get('reviewFolder'):
            self.openPath(event['reviewFolder'])
        if event.get('splitFolder'):
            self.openPath(event['splitFolder'])
        if event.get('event')=='result' and event.get('command')=='configure':
            self.toast.emit('Configuración guardada.')
