"""Inspección local de un CSV elegido; no acredita cobertura ni envía archivos."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from chc_runtime import output_layout


def digest_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def registered_file(path, registry):
    if not registry.is_file():
        return None
    key = os.path.normcase(str(path))
    with closing(sqlite3.connect(registry.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute('SELECT * FROM exports'):
            if os.path.normcase(str(Path(row['path']).resolve())) == key:
                if not row['final']:
                    raise ValueError('Este CSV fue sustituido por un acumulado más reciente. Selecciona el CSV vigente.')
                return dict(row)
    return None


def inspect_file(value, registry):
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.csv':
        raise ValueError('Selecciona un archivo CSV de resultados existente.')
    before = path.stat()
    digest = digest_file(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('El CSV está cambiando. Espera a que termine su exportación y vuelve a elegirlo.')
    registered = registered_file(path, registry)
    spec = json.loads(registered['spec']) if registered else {}
    if registered and (spec.get('target') != registered['target'] or spec.get('period') != registered['period']):
        raise ValueError('El registro del CSV no coincide con su procedimiento o período.')
    name = output_layout.uppercase(path.stem)
    target = spec.get('target', '')
    if not target:
        for flow, label in output_layout.FLOWS.items():
            if label in name and flow != 'tabla':
                target = 'manifiestos:' + flow
                break
        if not target:
            for bot, label in output_layout.BOTS.items():
                if label in name:
                    target = bot
                    break
    mode = spec.get('mode') or next((v.lower() for v in ('MARITIMO', 'AEREO', 'TERRESTRE') if v in name), '')
    if target == 'manifiestos:contenedores' and mode in ('aereo', 'terrestre'):
        raise ValueError('Contenedores admite únicamente resultados de Marítimo.')
    if target == 'manifiestos:contenedores':
        mode = 'maritimo'
    return {'path': str(path), 'name': path.name, 'size': after.st_size,
            'mtime': after.st_mtime_ns, 'digest': digest, 'registered': bool(registered),
            'owner': registered['owner'] if registered else 'manual:' + hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest(),
            'target': target, 'period': spec.get('period') or output_layout.period(path.stem),
            'mode': mode, 'spec': spec}


def review_spec(plan, target, period, mode):
    if plan['registered']:
        spec = plan['spec']
    else:
        if target not in (*output_layout.BOTS, *('manifiestos:' + v for v in output_layout.FLOWS)):
            raise ValueError('Elige el bot o procedimiento al que pertenece el CSV.')
        if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', period):
            raise ValueError('Elige el mes y año del CSV.')
        if target.startswith('manifiestos:') or target == 'bls':
            if mode not in ('maritimo', 'aereo', 'terrestre') or target == 'bls' and mode == 'terrestre':
                raise ValueError('Elige una modalidad válida para el CSV.')
        else:
            mode = ''
        spec = output_layout.specification(target, period, mode,
            qualifier='ARCHIVO_' + output_layout.uppercase(Path(plan['path']).stem))
    if spec['target'] == 'manifiestos:contenedores' and spec.get('mode') != 'maritimo':
        raise ValueError('Contenedores admite únicamente resultados de Marítimo.')
    return spec
