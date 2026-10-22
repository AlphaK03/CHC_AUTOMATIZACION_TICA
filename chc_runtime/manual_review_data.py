"""Selección de una revisión manual leyendo exclusivamente el progreso existente."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .identifiers import normalize_dua

DUA_MODULES = ('detalles', 'duas_transito', 'talon', 'xmovimientos')
MANIFEST_FLOWS = ('tabla', 'conocimientos', 'duas', 'movimientos', 'contenedores')


@contextmanager
def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db
    finally:
        db.close()


def contained(path, folder):
    path, folder = Path(path).resolve(), Path(folder).resolve()
    if not path.is_relative_to(folder) or path.suffix != '.sqlite3':
        raise ValueError('La tabla de revisión no pertenece al lote seleccionado.')
    return path


def load_selection(root, module, request):
    root = Path(root).resolve()
    if module in DUA_MODULES:
        folder = root / 'data/queues'
        with readonly(folder / 'catalog.sqlite3') as db:
            table = db.execute('SELECT * FROM saved_tables WHERE id=? AND deleted=0',
                               (request['tableId'],)).fetchone()
        if table is None:
            raise ValueError('La tabla seleccionada ya no está disponible.')
        database = contained(folder / table['filename'], folder)
        if database.parent != folder or database.name == 'catalog.sqlite3':
            raise ValueError('Ruta de tabla inválida.')
        with readonly(database) as db:
            row = db.execute('SELECT id,dua,status FROM jobs WHERE id=?', (request['jobId'],)).fetchone()
        if row is None or not row['dua']:
            raise ValueError('Esta fila no contiene un DUA válido para consultar.')
        config_path = root / 'config/machine.json'
        config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
        return {'module': module, 'dua': normalize_dua(row['dua']), 'config': config,
                'tableId': table['id'], 'jobId': row['id']}
    flow = 'bls' if module == 'bls' else request.get('flow')
    if module not in ('bls', 'manifiestos') or flow not in (*MANIFEST_FLOWS, 'bls'):
        raise ValueError('Módulo o procedimiento de revisión inválido.')
    if module == 'manifiestos' and flow == 'bls':
        raise ValueError('BLs se revisa desde su propio módulo.')
    index = json.loads((root / 'data/workbench' / flow / 'session.json').read_text(encoding='utf-8'))
    record = next((r for r in index['history'] if r['id'] == request['recordId']), None)
    if record is None:
        raise ValueError('La ejecución seleccionada ya no está disponible.')
    folder = root / 'data/jobs' / flow / record['id']
    if folder.resolve().parent != (root/'data/jobs'/flow).resolve():
        raise ValueError('La ejecución no pertenece al módulo seleccionado.')
    candidates = list(folder.glob('**/SQLite/bls.sqlite3')) if module == 'bls' else record.get('databases', [])
    if request.get('database'):
        selected = contained(request['database'],folder)
        if selected not in [contained(p,folder) for p in candidates]:
            raise ValueError('La base de revisión no pertenece a la ejecución seleccionada.')
        candidates = [selected]
    matches = []
    for candidate in candidates:
        path = contained(candidate, folder)
        with readonly(path) as db:
            if module == 'bls':
                row = db.execute('SELECT ordinal,payload,state FROM jobs WHERE ordinal=?',
                                 (int(request['ordinal']),)).fetchone()
                if row:
                    matches.append({'ordinal': row['ordinal'], 'record': json.loads(row['payload'])})
            else:
                row = db.execute('SELECT id,state FROM jobs WHERE id=?', (request['jobId'],)).fetchone()
                if row:
                    scope = json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0])
                    matches.append({'manifest': row['id'], 'scope': scope})
    if len(matches) != 1:
        raise ValueError('No se encontró una fila inequívoca en el progreso seleccionado.')
    return {'module': module, 'flow': flow, 'recordId': record['id'],
            'config': record['config'], **matches[0]}
