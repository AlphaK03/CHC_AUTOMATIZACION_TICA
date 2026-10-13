"""Caché SQLite de la entrada validada; independiente del progreso de los lotes."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import pandas as pd

VERSION = '1'
REQUIRED = {'BL original', 'IDManifiesto', 'Fecha Manifiesto'}


def save_input_cache(frame, destination, source_file='', sheet_name=None):
    """Reemplaza la caché completa de forma atómica y conserva texto y orden."""
    columns = [str(column) for column in frame.columns]
    if frame.empty or not REQUIRED.issubset(columns) or len(set(columns)) != len(columns):
        raise ValueError('La base cargada no tiene el esquema esperado.')
    path = Path(destination)
    sheet_name = sheet_name or path.stem
    _validate_sheet_name(sheet_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.stem + '.', suffix='.tmp')
    os.close(fd)
    try:
        with closing(sqlite3.connect(temporary)) as db:
            with db:
                db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                db.execute('CREATE TABLE input_rows(ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
                db.executemany('INSERT INTO metadata VALUES (?,?)', [
                    ('version', VERSION), ('columns', json.dumps(columns, ensure_ascii=False)),
                    ('row_count', str(len(frame))), ('source_file', str(source_file)),
                    ('sheet_name', sheet_name)])
                # Igual que inputs.input_job: None es vacío; NaN conserva su texto.
                rows = ((ordinal, json.dumps(['' if value is None else str(value) for value in values],
                            ensure_ascii=False, separators=(',', ':')))
                        for ordinal, values in enumerate(frame.itertuples(index=False, name=None), 1))
                db.executemany('INSERT INTO input_rows VALUES (?,?)', rows)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _validate_sheet_name(name):
    if not isinstance(name, str) or not name or len(name) > 31 or name in ('.', '..') or \
            any(character in name for character in '[]:*?/\\'):
        raise ValueError('Nombre de hoja incompatible en la base de entrada.')


def _read_metadata(db, path):
    try:
        with closing(db.execute('SELECT key,value FROM metadata')) as cursor:
            metadata = dict(cursor)
        if metadata.get('version') != VERSION:
            raise ValueError('Versión de caché incompatible.')
        columns = json.loads(metadata['columns'])
        if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns) or \
                not REQUIRED.issubset(columns) or len(set(columns)) != len(columns):
            raise ValueError('Columnas de caché incompatibles.')
        if int(metadata['row_count']) < 1:
            raise ValueError('La base de entrada está vacía.')
        metadata['sheet_name'] = metadata.get('sheet_name') or path.stem
        _validate_sheet_name(metadata['sheet_name'])
        with closing(db.execute('SELECT ordinal,payload FROM input_rows LIMIT 1')) as cursor:
            if cursor.fetchone() is None:
                raise ValueError('La base de entrada está vacía.')
        return metadata, columns
    except (sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        raise ValueError('Este SQLite no es una base de entrada válida de BLs BOT. '
                         'Seleccione la caché de Datos_Cargados, no la base de progreso. '
                         f'Detalle: {exc}') from exc


def input_cache_info(source):
    """Obtiene la hoja sin cargar las filas; compatible con las cachés anteriores."""
    path = Path(source).resolve()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        metadata, _ = _read_metadata(db, path)
    return metadata


def load_input_cache(source):
    """Lee únicamente texto ya normalizado; no vuelve a interpretar fechas ni BL."""
    path = Path(source).resolve()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        metadata, columns = _read_metadata(db, path)
        rows = []
        with closing(db.execute('SELECT payload FROM input_rows ORDER BY ordinal')) as cursor:
            for payload, in cursor:
                row = json.loads(payload)
                if not isinstance(row, list) or len(row) != len(columns) or \
                        not all(isinstance(value, str) for value in row):
                    raise ValueError('Fila de caché incompleta o incompatible.')
                rows.append(row)
        if not rows or len(rows) != int(metadata['row_count']):
            raise ValueError('Cantidad de filas de caché incompatible.')
    frame = pd.DataFrame.from_records(rows, columns=columns)
    frame.attrs['sheet_name'] = metadata['sheet_name']
    return frame
