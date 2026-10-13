"""CSV públicos por bot/año/modalidad y progreso privado, con rutas portables."""
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLOWS = ('tabla', 'duas', 'movimientos', 'conocimientos', 'contenedores')
PREFIXES = {'tabla': 'manifiestos', **{name: name for name in FLOWS if name != 'tabla'}}
LEGACY_FOLDERS = {'tabla': 'output_manifest', **{name: f'output_manifest_{name}' for name in FLOWS if name != 'tabla'}}
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
          'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
FAILURE_VARIANTS = frozenset(('fallidos', 'fallidas', 'excluidas'))
OLD_NAME = re.compile(r'^(manifiestos|duas|movimientos|conocimientos|contenedores)_'
                      r'(?:(fallidas|fallidos|excluidas|estado)_)?(aereo|maritimo|terrestre)_(\d{4})_(\d{2})'
                      r'(?:_(estado))?_?$', re.I)
NEW_NAME = re.compile(r'^(manifiestos|duas|movimientos|conocimientos|contenedores)_'
                      r'(?:(fallidas|fallidos|excluidas|estado)_)?(aereo|maritimo|terrestre)_('
                      + '|'.join(MONTHS) + r')(\d{2})(?:_historico_.*)?$', re.I)


def resolve_path(value):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def custom_workspace(config, flow):
    key = 'output_manifest_folder' if flow == 'tabla' else f'output_manifest_{flow}_folder'
    explicit = config.get(key)
    if explicit and explicit not in (LEGACY_FOLDERS[flow], 'output_manifest_conocimientos_v2'):
        return resolve_path(explicit)
    return None


def output_base(config, flow):
    custom = custom_workspace(config, flow)
    return custom / 'resultados' if custom else resolve_path(config.get('resultados_folder', 'resultados'))


def application_base(config, flow=None):
    if config.get('app_data_folder'):
        return resolve_path(config['app_data_folder'])
    custom = custom_workspace(config, flow) if flow else None
    return custom / 'datos_app' if custom else PROJECT_ROOT / 'datos_app'


def csv_name(flow, mode, month, year, qualifier=''):
    middle = f'_{qualifier}' if qualifier else ''
    return f'{PREFIXES[flow]}{middle}_{mode}_{MONTHS[month-1]}{year % 100:02d}.csv'


def csv_directory(period, qualifier='', historical=False):
    period = Path(period)
    if historical:
        period = period / 'historicos'
    return period / 'fallidos' if qualifier in FAILURE_VARIANTS else period


def parse_result_name(path):
    """(procedimiento, modalidad, mes, año, variante) en nombres nuevos/anteriores."""
    stem = Path(path).stem
    match = OLD_NAME.fullmatch(stem)
    if match:
        prefix, qualifier, mode, year, month, trailing = match.groups()
        month, year = int(month), int(year)
        qualifier = qualifier or trailing or ''
    else:
        match = NEW_NAME.fullmatch(stem)
        if not match:
            return None
        prefix, qualifier, mode, month_name, year = match.groups()
        month, year = MONTHS.index(month_name.lower()) + 1, 2000 + int(year)
        qualifier = qualifier or ''
    if not 1 <= month <= 12:
        return None
    return ('tabla' if prefix.lower() == 'manifiestos' else prefix.lower(), mode.lower(), month, year, qualifier.lower())


def location_file(database):
    return Path(str(database) + '.exportacion.json')


def register_csv_location(database, csv):
    database, csv = Path(database).resolve(), Path(csv).resolve()
    try:
        target = os.path.relpath(csv, database.parent)
    except ValueError:
        target = str(csv)
    record = location_file(database)
    contents = json.dumps({'version': 1, 'csv': target}, ensure_ascii=False, indent=2)
    if record.exists() and record.read_text(encoding='utf-8') == contents:
        return
    record.parent.mkdir(parents=True, exist_ok=True)
    temporary = record.with_name(record.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(contents, encoding='utf-8')
    temporary.replace(record)


@dataclass(frozen=True)
class OutputPaths:
    period: Path
    stem: str
    failed_stem: str
    database: Path
    private_period: Path

    @property
    def csv(self):
        return self.period / (self.stem + '.csv')

    @property
    def failures(self):
        return self.period / 'fallidos' / (self.failed_stem + '.csv')


def output_paths(config, flow, mode, month, year):
    if flow not in FLOWS or mode not in ('aereo', 'maritimo', 'terrestre') or not 1 <= month <= 12:
        raise ValueError('Procedimiento, modalidad o mes inválidos')
    private = application_base(config, flow) / 'SQLite' / flow / f'{year:04d}' / mode
    database = private / f'{PREFIXES[flow]}_{mode}_{year:04d}_{month:02d}.sqlite3'
    failed = 'fallidas' if flow == 'duas' else 'fallidos'
    paths = OutputPaths(output_base(config, flow) / flow / f'{year:04d}' / mode,
                        Path(csv_name(flow, mode, month, year)).stem,
                        Path(csv_name(flow, mode, month, year, failed)).stem,
                        database, application_base(config, flow) / 'control' / flow / f'{year:04d}' / mode)
    paths.period.mkdir(parents=True, exist_ok=True)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    register_csv_location(paths.database, paths.csv)
    return paths


def csv_for_database(path):
    path = Path(path).resolve()
    record = location_file(path)
    if record.exists():
        value = json.loads(record.read_text(encoding='utf-8'))['csv']
        return (path.parent / value).resolve()
    if path.parent.name == 'SQLite':
        return path.parent.parent / 'CSV' / (path.stem + '.csv')
    return path.with_suffix('.csv')


def failure_csv_path(csv_path):
    path = Path(csv_path)
    prefix, rest = path.stem.split('_', 1)
    suffix = 'fallidas' if prefix == 'duas' else 'fallidos'
    return csv_directory(path.parent, suffix) / f'{prefix}_{suffix}_{rest}.csv'


def exclusion_csv_path(csv_path):
    path = Path(csv_path)
    stem = ('duas_excluidas_' + path.stem[len('duas_'):]
            if path.stem.startswith('duas_') else path.stem + '_excluidas')
    return csv_directory(path.parent, 'excluidas') / (stem + '.csv')
