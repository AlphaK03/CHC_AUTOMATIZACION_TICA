"""Entrada textual desde Excel, SQLite de Conocimientos o caché interna."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

import pandas as pd

from data_reader import leer_bls, prepare_bls
from input_cache import input_cache_info, load_input_cache

SQLITE_EXTENSIONS = {'.sqlite3', '.sqlite', '.db'}
BLS_COLUMNS = ['IDManifiesto', 'Secuencia Tica', 'BL original', 'Fecha Manifiesto', 'Mes']


@contextmanager
def _read_database(path):
    # Nunca crear ni actualizar una entrada, incluso si la ruta no existe.
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db


def _generated_columns(db):
    """Detecta exclusivamente el contrato exportado; no acepta SQLite de progreso."""
    tables = {name.casefold() for name, in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if 'bls' not in tables:
        return None  # Puede ser la caché interna; su lector valida los metadatos.
    if tables != {'bls'}:
        raise ValueError('La base BLS exportada debe contener únicamente la tabla BLS; '
                         'no seleccione la base de progreso.')
    schema = db.execute('PRAGMA table_info("BLS")').fetchall()
    columns = [column[1] for column in schema]
    if columns != BLS_COLUMNS or any(column[2].upper() != 'TEXT' for column in schema):
        raise ValueError('La tabla BLS no tiene las cinco columnas TEXT de la base '
                         'generada desde Conocimientos. Vuelva a exportarla.')
    if db.execute('SELECT 1 FROM "BLS" LIMIT 1').fetchone() is None:
        raise ValueError('La tabla BLS no contiene BL para procesar.')
    return columns


def is_sqlite_input(path):
    return Path(path).suffix.lower() in SQLITE_EXTENSIONS


def input_sheets(path):
    if is_sqlite_input(path):
        with _read_database(path) as db:
            if _generated_columns(db) is not None:
                return ['BLS']
        return [input_cache_info(path)['sheet_name']]
    if Path(path).suffix.lower() != '.xlsx':
        raise ValueError('Seleccione un Excel .xlsx o una base de entrada SQLite del bot.')
    with pd.ExcelFile(path) as workbook:
        return workbook.sheet_names


def load_input_file(path, sheet_name=None):
    if is_sqlite_input(path):
        with _read_database(path) as db:
            columns = _generated_columns(db)
            if columns is not None:
                if sheet_name is not None and sheet_name != 'BLS':
                    raise ValueError(f'La base SQLite contiene la hoja \'BLS\', no {sheet_name!r}.')
                rows = []
                quoted = ','.join('"' + column + '"' for column in columns)
                with closing(db.execute(f'SELECT {quoted} FROM "BLS" ORDER BY rowid')) as cursor:
                    for row in cursor:
                        if not all(isinstance(value, str) for value in row):
                            raise ValueError('La tabla BLS contiene valores no textuales o nulos; '
                                             'vuelva a generar la base desde Conocimientos.')
                        rows.append(row)
                frame = prepare_bls(pd.DataFrame.from_records(rows, columns=columns))
                frame.attrs['sheet_name'] = 'BLS'
                return frame
        frame = load_input_cache(path)
        if sheet_name is not None and sheet_name != frame.attrs['sheet_name']:
            raise ValueError(f"La base SQLite contiene la hoja {frame.attrs['sheet_name']!r}, "
                             f"no {sheet_name!r}.")
        return frame
    if Path(path).suffix.lower() != '.xlsx':
        raise ValueError('Seleccione un Excel .xlsx o una base de entrada SQLite del bot.')
    sheet_name = sheet_name or 'BLS'
    frame = leer_bls(path, sheet_name)
    frame.attrs['sheet_name'] = sheet_name
    return frame
