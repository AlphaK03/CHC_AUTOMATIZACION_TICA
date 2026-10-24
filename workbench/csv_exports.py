"""Generación manual por procesos independientes; nunca inicia consultas."""
from uuid import uuid4
from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot


class CsvExports(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, bridges, parent=None):
        super().__init__(parent)
        self.bridges = bridges
        self._busy = False
        self._message = ''
        self.queue = []
        self.current = None
        self.exported = 0
        self.errors = []

    @Property(bool, notify=changed)
    def busy(self): return self._busy

    @Property(str, notify=changed)
    def message(self): return self._message

    @Slot()
    def generateAll(self):
        if self._busy:return
        self.queue = []
        self.exported = 0
        self.errors = []
        for name, bridge in self.bridges.items():
            if not bridge or not bridge.enabled:continue
            if hasattr(bridge, 'channels'):
                flows = ('bls',) if bridge.isBls else ('tabla','conocimientos','duas','movimientos','contenedores')
                labels={'bls':'BLs','tabla':'Manifiestos','conocimientos':'Conocimientos',
                        'duas':'DUAs por manifiesto','movimientos':'Movimientos por manifiesto','contenedores':'Contenedores'}
                for flow in flows:self.queue.append((labels[flow], bridge.channels[flow], bridge))
            else:
                label={'detalles':'Detalles','duas_transito':'DUAs Tránsito','talon':'Talón','xmovimientos':'XMovimientos'}.get(name,name)
                self.queue.append((label, bridge, bridge))
        self._busy = True
        self.changed.emit()
        self.next()

    def next(self):
        if not self._busy or self.current:return
        while self.queue:
            label, endpoint, bridge = self.queue.pop(0)
            if getattr(bridge, 'closing', False) or endpoint.busy or getattr(bridge, 'dailyActive', False):
                self.errors.append(label+': ocupado; vuelve a generarlo cuando termine.')
                continue
            if not hasattr(endpoint, 'send') and not endpoint.ready:
                self.errors.append(label+': módulo sin conectar.')
                continue
            token = uuid4().hex
            self.current = (label, endpoint, token)
            endpoint.eventReceived.connect(self.receive)
            endpoint.changed.connect(self.check_connection)
            self._message = 'Generando CSV: '+label
            self.changed.emit()
            send = endpoint.send if hasattr(endpoint,'send') else endpoint._send
            if send('export_all', {'exportToken':token}):return
            self.release()
            self.errors.append(label+': no se pudo iniciar la generación.')
        self._busy = False
        self._message = f'CSV generados desde {self.exported} lote(s).'
        if self.errors:self._message += '\n'+'\n'.join(self.errors)
        self.changed.emit()
        self.toast.emit(self._message)

    def check_connection(self):
        if self.current:
            label, endpoint, token = self.current
            if not endpoint.busy and endpoint.error:
                self.errors.append(label+': '+endpoint.error)
                self.release()
                QTimer.singleShot(0,self.next)

    def receive(self, event):
        if not self.current or event.get('command')!='export_all':return
        if event.get('event') not in ('result','error','fatal'):return
        label, endpoint, token = self.current
        report = event.get('exportReport',{})
        if report and report.get('token')!=token:return
        if report:
            self.exported += report['exported']
            self.errors.extend(label+': '+message for message in report['errors'])
        else:self.errors.append(label+': '+event.get('message','No se recibió el resultado.'))
        self.release()
        QTimer.singleShot(0,self.next)

    def release(self):
        if self.current:
            endpoint = self.current[1]
            endpoint.eventReceived.disconnect(self.receive)
            endpoint.changed.disconnect(self.check_connection)
            self.current = None

    @Slot()
    def cancel(self):
        self.queue = []
        self._busy = False
        self.release()
        self.changed.emit()
