"""Cada perfil cambia extracción, esquema y selección de base; el resto es común."""
from importlib import import_module
from pathlib import Path
import sys

from .job_store import JobStore
from .playwright_processor import PlaywrightDUAProcessor

ROOT = Path(__file__).resolve().parents[1]


def load_profile(module_id):
    if module_id not in ('detalles', 'duas_transito', 'talon', 'xmovimientos'):
        raise ValueError('Módulo sin integración operativa.')
    root = ROOT / 'bots' / module_id
    sys.path.insert(0, str(root / 'src'))
    if module_id == 'detalles':
        flow = import_module('flows.detalles_flow').DetallesFlow
        return {'id': module_id, 'root': root, 'flow': flow,
                'store': JobStore, 'processor': PlaywrightDUAProcessor,
                'fields': list(flow().extract_data('').columns), 'selection': 'total',
                'prefix': 'Detalles_DUAs', 'legacy': 'MM20YY_Detalles_DUAs__procesados_{sheet}.csv'}
    if module_id in ('talon', 'xmovimientos'):
        from .import_bots import TALON_FIELDS, MOVEMENT_FIELDS, TalonJobStore, MovementsJobStore, ImportRowsProcessor
        talon = module_id == 'talon'
        source = import_module('flows.talon_flow' if talon else 'flows.xmovimientos_flow')
        original = source.XTalonesFlow if talon else source.XMovimientosFlow
        store = TalonJobStore if talon else MovementsJobStore
        class ImportFlow(original):
            pass
        ImportFlow.fields = TALON_FIELDS if talon else MOVEMENT_FIELDS
        ImportFlow.store = store
        ImportFlow.module_id = module_id
        ImportFlow.submit_button = 'DETALLE' if talon else 'MANAERMAR'
        ImportFlow.table_id = 'Sftributos1ContainerTbl' if talon else 'SubstkContainerTbl'
        ImportFlow.raw_columns = 6 if talon else 5
        return {'id': module_id, 'root': root, 'flow': ImportFlow, 'store': store,
                'processor': ImportRowsProcessor, 'fields': ImportFlow.fields, 'selection': 'importacion',
                'prefix': 'Talon_DUAS' if talon else 'xMovimiento_DUAS',
                'legacy': 'MM20YY_Talon_DUAS_{sheet}.csv' if talon else 'MM20YY_xMovimiento_DUAS_{sheet}.csv'}
    from .transit import FIELDS, TransitJobStore, TransitProcessor
    source = import_module('flows.transito_flow')
    class TransitFlow(source.XTransitoFlow):
        fields = FIELDS
    return {'id': module_id, 'root': root, 'flow': TransitFlow,
            'store': TransitJobStore, 'processor': TransitProcessor,
            'fields': FIELDS, 'selection': 'transito', 'prefix': 'Transito_DUAS',
            'legacy': 'MM20YY_Transito_DUAS_{sheet}.csv'}
