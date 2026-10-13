"""Cada perfil cambia extracción, esquema y selección de base; el resto es común."""
from importlib import import_module
from pathlib import Path
import sys

from .job_store import JobStore
from .playwright_processor import PlaywrightDUAProcessor

ROOT = Path(__file__).resolve().parents[1]


def load_profile(module_id):
    if module_id not in ('detalles', 'duas_transito'):
        raise ValueError('Módulo sin integración operativa.')
    root = ROOT / 'bots' / module_id
    sys.path.insert(0, str(root / 'src'))
    if module_id == 'detalles':
        flow = import_module('flows.detalles_flow').DetallesFlow
        return {'id': module_id, 'root': root, 'flow': flow,
                'store': JobStore, 'processor': PlaywrightDUAProcessor,
                'fields': list(flow().extract_data('').columns), 'selection': 'total',
                'prefix': 'Detalles_DUAs', 'legacy': 'MM20YY_Detalles_DUAs__procesados_{sheet}.csv'}
    from .transit import FIELDS, TransitJobStore, TransitProcessor
    source = import_module('flows.transito_flow')
    class TransitFlow(source.XTransitoFlow):
        fields = FIELDS
    return {'id': module_id, 'root': root, 'flow': TransitFlow,
            'store': TransitJobStore, 'processor': TransitProcessor,
            'fields': FIELDS, 'selection': 'transito', 'prefix': 'Transito_DUAS',
            'legacy': 'MM20YY_Transito_DUAS_{sheet}.csv'}
