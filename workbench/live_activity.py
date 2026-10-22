"""Vista de las etapas comunicadas por el proceso; el reloj no inventa progreso."""
import time
from PySide6.QtCore import QObject, Property, QTimer, Signal, QAbstractListModel, QModelIndex, Qt


class OperationsModel(QAbstractListModel):
    """Actualizar etapas sin reconstruir ni desplazar su lista cada segundo."""
    def __init__(self,parent):
        super().__init__(parent);self.rows=[]

    def roleNames(self):return {Qt.UserRole+1:b'operation'}
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def data(self,index,role=Qt.DisplayRole):
        if role==Qt.UserRole+1 and index.isValid() and 0<=index.row()<len(self.rows):return self.rows[index.row()]

    def update(self,rows):
        keys={row['key'] for row in rows}
        for index in range(len(self.rows)-1,-1,-1):
            if self.rows[index]['key'] not in keys:
                self.beginRemoveRows(QModelIndex(),index,index);self.rows.pop(index);self.endRemoveRows()
        existing={row['key']:index for index,row in enumerate(self.rows)}
        for row in rows:
            index=existing.get(row['key'])
            if index is None:
                index=len(self.rows);self.beginInsertRows(QModelIndex(),index,index)
                self.rows.append(row);self.endInsertRows();existing[row['key']]=index
            elif row!=self.rows[index]:
                self.rows[index]=row;self.dataChanged.emit(self.index(index),self.index(index),[Qt.UserRole+1])


class LiveActivity(QObject):
    changed = Signal()

    def __init__(self, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self.clock=clock;self.rows=[];self.received=None;self.signal_at=None;self.active=False
        self.waiting='';self.timer=QTimer(self);self.timer.setInterval(1000)
        self.model=OperationsModel(self)
        self.timer.timeout.connect(self.tick)

    def tick(self):
        self.model.update(self.operations);self.changed.emit()

    def begin(self, label='Esperando al motor'):
        self.active=True;self.rows=[];self.received=None;self.signal_at=None;self.waiting=label
        self.timer.start();self.tick()

    def accept(self, event):
        if event.get('event')=='activity_state':
            self.active=bool(event.get('running'))
            self.rows=event.get('operations',[]);self.received=self.clock();self.signal_at=self.received
            if self.active:self.timer.start()
            else:self.timer.stop()
            self.tick()
        elif self.active and event.get('event') in ('log','progress','daily','result','stopping','error'):
            self.signal_at=self.clock();self.changed.emit()

    def finish(self):
        self.active=False;self.rows=[];self.timer.stop();self.tick()

    @Property(QObject,constant=True)
    def operationModel(self):return self.model

    @Property(bool,notify=changed)
    def running(self):return self.active

    @Property('QVariantList',notify=changed)
    def operations(self):
        age=max(0,self.clock()-self.received) if self.received is not None and self.active else 0
        return [{**row,'elapsed':int(row.get('elapsed',0)+age)} for row in self.rows]

    @Property(str,notify=changed)
    def status(self):
        if not self.active:return 'Sin operación en curso'
        if self.signal_at is None:return self.waiting
        age=int(max(0,self.clock()-self.signal_at))
        return (f'Sin señales del motor desde hace {age} s' if age>=10 else
                f'Última señal del motor hace {age} s')
