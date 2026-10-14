"""Lectura de la bitácora en un hilo: no bloquea Qt ni abre workers de bots."""
from threading import Thread
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from monthly_progress import MonthlyReader


class MonthlyProgress(QObject):
    changed=Signal()
    received=Signal(object)

    def __init__(self,roots,parent=None):
        super().__init__(parent)
        self.roots=roots
        self.rows=[]
        self.busy=False
        self.message='Sin descargas guardadas.' if roots else 'La bitácora muestra únicamente descargas reales.'
        self._again=False
        self.received.connect(self.finish)
        self.debounce=QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(10000)
        self.debounce.timeout.connect(self.refresh)
        self.timer=QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.refresh)
        if roots:
            self.timer.start()
            QTimer.singleShot(0,self.refresh)

    @Slot()
    def schedule(self):
        if self.roots and not self.debounce.isActive():self.debounce.start()

    @Slot()
    def refresh(self):
        if not self.roots:return
        if self.busy:self._again=True;return
        self.busy=True
        self.changed.emit()
        def run():
            try:result=MonthlyReader(self.roots).read()
            except Exception:result={'rows':[],'errors':1}
            try:self.received.emit(result)
            except RuntimeError:pass  # Qt ya cerró; la lectura nunca escribe.
        Thread(target=run,name='monthly-progress',daemon=True).start()

    @Slot(object)
    def finish(self,result):
        self.rows=result['rows']
        self.busy=False
        self.message=(f"{result['errors']} fuente(s) sin verificar; vuelve a actualizar." if result['errors'] else
                      'Pasa sobre un estado para ver el detalle. Pulsa para abrir el bot.' if self.rows else 'Aún no hay descargas con un mes identificado.')
        self.changed.emit()
        if self._again:
            self._again=False
            self.debounce.start()
