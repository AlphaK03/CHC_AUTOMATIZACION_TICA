"""Puente Qt para procedimientos independientes; no importa motores de bots."""
import json
from pathlib import Path
import sys
import time

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from process_guard import ProcessTreeGuard
from manual_review import ManualReview
from activity_model import ActivityModel
from live_activity import LiveActivity

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
from chc_runtime.manifest_names import manifest_scope, manifest_name
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
        self.active_command = ''
        self.activity_model = ActivityModel(parent=self)
        self.console = LiveActivity(self)
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
        self.console.begin('Cargando módulo…')
        self.process.start(str(python),args)
        return True

    def send(self, command, data=None):
        if self.busy and command not in ('stop','shutdown'):
            return False
        request = {'command':command, **(data or {})}
        if command=='stop' and not self.ready:
            self.pending=None
            self.busy=False
            self.changed.emit()
            return True
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
        if command not in ('stop','shutdown'):
            self.active_command = command
            self.console.begin()
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
            self.console.accept(event)
            if kind == 'activity_state':
                continue
            if kind == 'log':
                self.activity_model.prepend(event)
            if kind == 'ready':
                self.ready = True
                if self.pending:
                    self.process.write((json.dumps(self.pending,ensure_ascii=False)+'\n').encode())
                    self.pending = None
            elif kind == 'idle':
                self.console.finish()
                self.busy = False
                self.active_command = ''
            elif kind == 'error':
                self.error = event.get('message','Error del motor')
                self.activity_model.prepend(dict(time=time.strftime('%H:%M:%S'),level='ERROR',message=self.error))
            self.changed.emit()
            self.eventReceived.emit(event)

    def read_error(self):
        self.stderr = (self.stderr+bytes(self.process.readAllStandardError()).decode('utf-8',errors='replace'))[-6000:]

    def finished(self, code, status):
        self.console.finish()
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
            self.console.finish()
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

    def __init__(self, module_id='manifiestos', enabled=True, storage_root=None, offline_fixture=False, knowledge_root=None):
        super().__init__()
        self._review = ManualReview(module_id, storage_root or ROOT/'bots'/module_id, offline_fixture, self)
        self._review.toast.connect(self.toast.emit)
        self._review.closed.connect(self.check_closed)
        self._module = module_id
        self._enabled = enabled
        self._closing = False
        self._flow = 'bls' if module_id=='bls' else 'conocimientos'
        self._root = Path(storage_root or ROOT/'bots'/module_id).resolve()
        flows = ['bls'] if module_id=='bls' else ['tabla','conocimientos','duas','movimientos','contenedores','bases']
        self.channels = {flow:BatchChannel(module_id,flow,self._root,offline_fixture,self) for flow in flows}
        self._knowledge_request=None
        self._knowledge_error=''
        self._knowledge_status=''
        self._refresh_knowledge=False
        if module_id=='bls':
            source_root=Path(knowledge_root or (self._root.parent/'manifiestos' if offline_fixture else ROOT/'bots/manifiestos')).resolve()
            self.channels['bls_source']=BatchChannel('manifiestos','bls_source',source_root,offline_fixture,self)
        for flow,channel in self.channels.items():
            channel.changed.connect(self.changed.emit)
            channel.eventReceived.connect(lambda event, f=flow:self.receive(f,event))
            channel.closed.connect(self.check_closed)
        if module_id=='bls':
            self.channels['bls_source'].changed.connect(self.source_changed)

    def source_changed(self):
        channel=self.channels['bls_source']
        if self._knowledge_request is not None and channel.error and channel.process.state()==QProcess.NotRunning:
            self._knowledge_request=None
            self._knowledge_error=channel.error
            self._knowledge_status='No se iniciaron consultas de BLs.'
            self.changed.emit()

    def current(self): return self.channels[self._flow]
    @Slot('QVariantMap', result=str)
    def automaticTableName(self, config):
        try:
            return manifest_name(manifest_scope(self._flow, config))
        except (KeyError, TypeError, ValueError):
            return ''
    @Property(bool, constant=True)
    def enabled(self): return self._enabled
    @Property(bool, constant=True)
    def isBls(self): return self._module=='bls'
    @Property(str, notify=changed)
    def flow(self): return self._flow
    @Property(bool, notify=changed)
    def ready(self): return self.current().ready
    @Property(bool, notify=changed)
    def busy(self): return self.current().busy or self._knowledge_request is not None or (self.isBls and self.channels['bls_source'].busy)
    @Property(bool, notify=changed)
    def loading(self):
        if not self.enabled or self._closing or self._knowledge_request is not None:
            return False
        channel = self.current()
        if channel.busy and channel.active_command in {'run','retry_empty'}:
            return False
        if not channel.error and (not channel.ready or
                (channel.busy and channel.active_command in {'refresh','select','import_progress'})):
            return True
        auxiliary = self.channels.get('bls_source' if self.isBls else 'bases')
        return bool(auxiliary and not auxiliary.error and auxiliary.busy and
                    auxiliary.active_command in {'refresh','knowledge_catalog','base_load'})
    @Property(bool, notify=changed)
    def running(self): return any(c.busy for c in self.channels.values())
    @Property(bool, notify=changed)
    def dailyActive(self): return False
    @Property(bool, notify=changed)
    def closing(self): return self._closing
    @Property(bool, notify=changed)
    def isClosed(self): return self._review.isClosed and all(c.process.state()==QProcess.NotRunning for c in self.channels.values())
    @Property(QObject, constant=True)
    def manualReview(self): return self._review
    @Property(str, notify=changed)
    def error(self): return self._knowledge_error or self.current().error
    @Property('QVariantMap', notify=changed)
    def config(self): return self.current().snapshot['config']
    @Property('QVariantMap', notify=changed)
    def summary(self): return self.current().snapshot['summary']
    @Property('QVariantList', notify=changed)
    def modeSummaries(self): return self.current().snapshot.get('modeSummaries',[])
    @Property(str, notify=changed)
    def viewMode(self): return self.current().snapshot.get('viewMode','')
    @Property(str, notify=changed)
    def viewSearch(self): return self.current().snapshot.get('viewSearch','')
    @Property(int, notify=changed)
    def viewOffset(self): return self.current().snapshot.get('viewOffset',0)
    @Property('QVariantList', notify=changed)
    def jobs(self): return self.current().snapshot['jobs']
    @Property('QVariantList', notify=changed)
    def activeJobs(self): return self.current().snapshot.get('activeJobs',[]) if self.current().busy else []
    @Property('QVariantList', notify=changed)
    def history(self): return self.current().snapshot['history']
    @Property(str, notify=changed)
    def activeId(self): return self.current().snapshot['activeId']
    @Property(str, notify=changed)
    def status(self): return self._knowledge_status or self.current().snapshot.get('message') or ('Listo' if self.ready else 'Preparando…')
    @Property('QVariantMap', notify=changed)
    def knowledgeCatalog(self):
        if not self.isBls:
            return {'periods':[]}
        channel=self.channels['bls_source']
        data=channel.snapshot.get('knowledgeCatalog',{'periods':[]})
        return {**data,'message':channel.error} if channel.error else data
    @Property(bool, notify=changed)
    def knowledgeBusy(self): return self.isBls and self.channels['bls_source'].busy
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
    @Property(QObject, notify=changed)
    def activityModel(self): return self.current().activity_model
    @Property(QObject, notify=changed)
    def consoleMonitor(self):
        auxiliary=self.channels.get('bls_source' if self.isBls else 'bases')
        if auxiliary and auxiliary.busy and not self.current().busy:
            return auxiliary.console
        return self.current().console

    @Slot()
    def clearActivity(self): self.current().activity_model.clear()

    @Slot()
    def connectModule(self):
        if self.enabled:
            self.current().send('refresh')
            if 'bases' in self.channels:
                self.channels['bases'].send('refresh')
            if self.isBls:
                self.refreshKnowledge()

    @Slot(str)
    def setFlow(self, flow):
        if flow in self.channels and flow!='bases':
            self._flow = flow
            if not self.current().ready and not self.current().busy:
                self.current().send('refresh')
            self.changed.emit()

    @Slot(str, 'QVariantMap', result=bool)
    def command(self, name, data):
        if self.isBls and name == 'retry_empty':
            if self.busy or self._closing or self._review.running:
                return False
            self._knowledge_error=self._knowledge_status=''
        if name == 'delete' and (self.busy or self._closing or self._review.running):
            return False
        if self.isBls and name=='run' and self.enabled:
            config=dict(data.get('config',self.config))
            if 'inputMode' not in config and config.get('input'):
                config['inputMode']='file'
            if config.get('inputMode',self.config.get('inputMode','knowledge'))=='knowledge':
                if self.busy:
                    return False
                self._knowledge_error=''
                self._knowledge_status='Preparando base desde Conocimientos…'
                self._knowledge_request=config
                accepted=self.channels['bls_source'].send('knowledge_build',{'periods':config.get('knowledgePeriods',[])})
                if not accepted:
                    self._knowledge_request=None
                    self._knowledge_error=self.channels['bls_source'].error
                self.changed.emit()
                return accepted
            self._knowledge_error=self._knowledge_status=''
        return self.current().send(name,data) if self.enabled else False

    @Slot(str, str, str, str, result=bool)
    def deleteDatabase(self, flow, table_id, table_name, confirmation):
        if flow != self._flow:
            return False
        return self.command('delete', {'confirmTableId': table_id,
            'confirmTableName': table_name, 'confirmation': confirmation})

    @Slot()
    def refreshKnowledge(self):
        if self.isBls and self.enabled and not self._closing:
            channel=self.channels['bls_source']
            if channel.busy or self._knowledge_request is not None:
                self._refresh_knowledge=True
            else:
                channel.send('knowledge_catalog')

    @Slot(str, 'QVariantMap', result=bool)
    def baseCommand(self, name, data):
        return self.channels['bases'].send(name,data) if self.enabled else False

    @Slot()
    def stop(self):
        if self.isBls and self._knowledge_request is not None:
            self._knowledge_request=None
            self._knowledge_status='Preparación detenida; no se iniciaron consultas de BLs.'
            self.channels['bls_source'].send('stop')
        elif self.isBls and self.channels['bls_source'].busy:
            self.channels['bls_source'].send('stop')
        if self.current().busy:
            self.current().send('stop')
    @Slot()
    def stopBase(self): self.channels['bases'].send('stop')
    @Slot()
    def shutdown(self):
        self._closing = True
        self._review.shutdown()
        self._knowledge_request=None
        self._refresh_knowledge=False
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

    @Slot(str, int)
    @Slot(str, int, str)
    def openInTica(self, job_id, ordinal, database=''):
        if self.enabled and not self.closing and self.activeId:
            request = {'flow':self.flow, 'recordId':self.activeId, 'jobId':job_id, 'ordinal':ordinal}
            if database:request['database'] = database
            self._review.open(request)

    @Slot(str)
    def useBase(self, path):
        if self.isBls and not self.busy:
            self.current().send('configure',{'config':{'input':path,'sheet':'BLS','inputMode':'file'}})

    def receive(self, flow, event):
        if flow in ('bls_source','bases') and event.get('event')=='log':
            target=self.channels['bls'] if self.isBls else self.current()
            target.activity_model.prepend({**event,'message':'Base BLs · '+event.get('message','')})
        if flow=='bls_source':
            if event.get('event')=='error':
                self._knowledge_error=event.get('message','No se pudo preparar la base.')
                self._knowledge_status='No se iniciaron consultas de BLs.'
                self._knowledge_request=None
            if event.get('knowledgeBase') and self._knowledge_request is not None and not self._closing:
                result=event['knowledgeBase']
                config={**self._knowledge_request,'input':result['output'],'sheet':'BLS','inputMode':'knowledge'}
                # Fechas/modalidades viajan en cada fila original; no hay modo global de búsqueda.
                self._knowledge_request=None
                self._knowledge_status=''
                self.current().send('knowledge_empty' if result['empty'] else 'run',{'config':config})
            if event.get('event')=='idle' and self._refresh_knowledge and not self._closing:
                self._refresh_knowledge=False
                QTimer.singleShot(0,self.refreshKnowledge)
            self.changed.emit()
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
