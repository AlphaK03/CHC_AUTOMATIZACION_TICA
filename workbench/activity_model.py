"""Actividad incremental: una notificación de progreso no reconstruye la lista."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot


class ActivityModel(QAbstractListModel):
    beforeChange=Signal()
    afterChange=Signal()
    EventRole=Qt.UserRole+1

    def __init__(self,limit=2000,parent=None):
        super().__init__(parent)
        self.limit=limit
        self.rows=[]
        self.sequence=0

    def roleNames(self):return {self.EventRole:b'eventData'}

    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)

    def data(self,index,role=Qt.DisplayRole):
        if role==self.EventRole and index.isValid() and 0<=index.row()<len(self.rows):return self.rows[index.row()]
        return None

    def prepend(self,event):
        self.beforeChange.emit()
        self.sequence+=1
        item={**event,'activityId':self.sequence,
              'level':event.get('level') or {'success':'SUCCESS','warning':'WARNING','error':'ERROR'}.get(event.get('kind'),'INFO')}
        self.beginInsertRows(QModelIndex(),0,0)
        self.rows.insert(0,item)
        self.endInsertRows()
        if len(self.rows)>self.limit:
            self.beginRemoveRows(QModelIndex(),self.limit,len(self.rows)-1)
            del self.rows[self.limit:]
            self.endRemoveRows()
        self.afterChange.emit()

    @Slot()
    def clear(self):
        if not self.rows:return
        self.beforeChange.emit()
        self.beginRemoveRows(QModelIndex(),0,len(self.rows)-1)
        self.rows.clear()
        self.endRemoveRows()
        self.afterChange.emit()

    @Slot(int,result=int)
    def idAt(self,index):return self.rows[index]['activityId'] if 0<=index<len(self.rows) else -1
