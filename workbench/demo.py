"""Estado del prototipo: solo datos sintéticos en memoria, sin motores de bots."""
from datetime import datetime
import json
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

PRESENTATION = {
    'manifiestos': {'title':'Manifiestos', 'subtitle':'Manifiestos y conocimientos', 'icon':'ship',
                   'color':'#78c5df', 'description':'Consulta manifiestos, conocimientos, DUAs, movimientos y contenedores.',
                   'inputLabel':'Período y modalidad', 'format':'TICA · SQLite', 'outputLabel':'Registros por manifiesto'},
    'bls': {'title': 'BLs', 'subtitle': 'Conocimientos de embarque', 'icon': 'ship',
            'color': '#6daff2', 'description': 'Explora y organiza los conocimientos de embarque asociados a tus manifiestos.',
            'inputLabel': 'Base de conocimientos', 'format': 'XLSX · SQLite', 'outputLabel': 'Líneas de BL'},
    'detalles': {'title': 'Detalles', 'subtitle': 'Información de declaraciones', 'icon': 'document',
                 'color': '#ab93f2', 'description': 'Un espacio para consultar y administrar la información detallada de cada declaración.',
                 'inputLabel': 'Base de declaraciones', 'format': 'XLSX · NroDUA', 'outputLabel': 'Detalles por DUA'},
    'duas_transito': {'title': 'DUAs Tránsito', 'subtitle': 'Operaciones de tránsito', 'icon': 'route',
                     'color': '#67cab1', 'description': 'Consulta las operaciones de tránsito y sigue el estado de tus declaraciones en un solo panel.',
                     'inputLabel': 'Base de tránsito', 'format': 'XLSX · NroDUA', 'outputLabel': 'Registros de tránsito'},
    'talon': {'title': 'Talón', 'subtitle': 'Talones de declaraciones', 'icon': 'receipt',
              'color': '#e7b46d', 'description': 'Organiza las consultas de talones y revisa sus resultados desde un espacio independiente.',
              'inputLabel': 'Base de declaraciones', 'format': 'XLSX · NroDUA', 'outputLabel': 'Talones por DUA'},
    'xmovimientos': {'title': 'XMovimientos', 'subtitle': 'Historial de movimientos', 'icon': 'activity',
                     'color': '#df8fa9', 'description': 'Visualiza el historial de movimientos y el avance de cada consulta de forma ordenada.',
                     'inputLabel': 'Base de declaraciones', 'format': 'XLSX · NroDUA', 'outputLabel': 'Movimientos por DUA'},
}


class DemoBackend(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, registry: Path, details=None, transit=None, talon=None, movements=None, manifests=None, bls=None):
        super().__init__()
        entries = json.loads(registry.read_text(encoding='utf-8'))['modules']
        self._modules = []
        for entry in entries:
            visual = PRESENTATION.get(entry['id'], {
                'title': entry['name'], 'subtitle': 'Módulo de automatización', 'icon': 'grid',
                'color': '#8da4bc', 'description': 'Un nuevo espacio de automatización.',
                'inputLabel': 'Base de prueba', 'format': 'Demostración', 'outputLabel': 'Registros',
            })
            self._modules.append({'id': entry['id'], **visual, 'loaded': False,
                                  'status': 'available', 'progress': 0, 'total': 240,
                                  'workers': 2, 'events': []})
        self._route = 'overview'
        self._query = ''
        self._activity = []
        self.details = details
        self._bridges = {'detalles': details, 'duas_transito': transit, 'talon': talon, 'xmovimientos': movements,
                         'manifiestos': manifests, 'bls': bls}
        for bridge in self._bridges.values():
            if bridge and bridge.enabled:
                bridge.changed.connect(self.changed.emit)
        self._timer = QTimer(self)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @Property('QVariantList', notify=changed)
    def modules(self):
        modules = [{key: value for key, value in item.items() if key != 'events'} for item in self._modules]
        for item in modules:
            item['mode'] = 'demo'
            bridge = self._bridges.get(item['id'])
            if bridge and bridge.enabled:
                item.update(mode='real', status='running' if bridge.running or bridge.dailyActive else 'available' if bridge.ready else 'unavailable',
                            progress=bridge.summary['succeeded'], total=bridge.summary['total'])
        return modules

    @Property('QVariantList', notify=changed)
    def filteredModules(self):
        query = self._query.casefold().strip()
        return [item for item in self.modules if query in (item['title'] + ' ' + item['subtitle']).casefold()]

    @Property(str, notify=changed)
    def route(self):
        return self._route

    @Property('QVariantMap', notify=changed)
    def selectedModule(self):
        return next((item.copy() for item in self._modules if item['id'] == self._route), {})

    @Property('QVariantList', notify=changed)
    def activity(self):
        return self._activity[:6]

    @Property(int, notify=changed)
    def runningCount(self):
        return sum(item['status'] == 'running' for item in self.modules)

    @Property(int, notify=changed)
    def processedCount(self):
        return sum(item['progress'] for item in self.modules)

    @Property('QVariantList', notify=changed)
    def previewRows(self):
        item = self.selectedModule
        if not item.get('loaded'):
            return []
        rows = []
        for index in range(8):
            completed = item['progress'] >= (index + 1) * 4
            working = not completed and item['status'] == 'running' and index == item['progress'] // 4
            rows.append({'number': f'{index + 1:02}', 'identifier': f'DEMO-{index + 1:04}',
                         'category': item['outputLabel'], 'status': 'Confirmado' if completed else 'En proceso' if working else 'Pendiente',
                         'time': '00:01' if completed else '—'})
        return rows

    def _current(self):
        return next((item for item in self._modules if item['id'] == self._route), None)

    def _log(self, item, message, kind='info'):
        event = {'time': datetime.now().strftime('%H:%M:%S'), 'message': message,
                 'module': item['title'], 'color': item['color'], 'kind': kind}
        item['events'].insert(0, event)
        del item['events'][30:]
        self._activity.insert(0, event)
        del self._activity[40:]

    @Slot(str)
    def navigate(self, route):
        if route == 'overview' or any(item['id'] == route for item in self._modules):
            self._route = route
            bridge = self._bridges.get(route)
            if bridge and bridge.enabled:
                bridge.connectModule()
            self.changed.emit()

    @Slot(str)
    def search(self, query):
        self._query = query
        if query.strip():
            self._route = 'overview'
        self.changed.emit()

    @Slot()
    def loadSample(self):
        item = self._current()
        if not item or item['status'] == 'running':
            return
        item.update(loaded=True, status='ready', progress=0)
        self._log(item, 'Base de ejemplo preparada · 240 registros sintéticos')
        self.changed.emit()
        self.toast.emit('Base de ejemplo cargada. Puedes iniciar la simulación.')

    @Slot()
    def startDemo(self):
        item = self._current()
        if not item or not item['loaded'] or item['status'] in {'running', 'completed'}:
            return
        item['status'] = 'running'
        self._log(item, 'Simulación iniciada · solo datos de ejemplo')
        self.changed.emit()

    @Slot()
    def pauseDemo(self):
        item = self._current()
        if item and item['status'] == 'running':
            item['status'] = 'paused'
            self._log(item, 'Simulación pausada · avance conservado')
            self.changed.emit()

    @Slot()
    def resetDemo(self):
        item = self._current()
        if item:
            item.update(loaded=False, progress=0, status='available', events=[])
            self.changed.emit()
            self.toast.emit('El espacio de prueba se ha reiniciado.')

    @Slot(int)
    def setWorkers(self, workers):
        item = self._current()
        if item and item['status'] != 'running':
            item['workers'] = max(1, min(4, workers))
            self.changed.emit()

    @Slot()
    def exportDemo(self):
        self.toast.emit('Vista de prueba: los resultados permanecen en memoria.')

    def _tick(self):
        updated = False
        for item in self._modules:
            if item['status'] != 'running':
                continue
            previous = item['progress']
            item['progress'] = min(item['total'], previous + item['workers'] * 2)
            if item['progress'] == item['total']:
                item['status'] = 'completed'
                self._log(item, 'Simulación completada · 240 registros de ejemplo', 'success')
                self.toast.emit(f"{item['title']}: simulación completada.")
            elif item['progress'] // 60 > previous // 60:
                self._log(item, f"{item['progress']} de 240 registros de ejemplo procesados")
            updated = True
        if updated:
            self.changed.emit()
