"""Identidades textuales e identidad del lote de entrada."""
import calendar
import hashlib
import json
import re
from datetime import datetime


def input_job(record, ordinal):
    original = {str(k): '' if v is None else str(v).strip() for k, v in record.items()}
    mid, bl = original.get('IDManifiesto', ''), original.get('BL original', '')
    sequence = original.get('Secuencia Tica', '')
    sequence_key = str(int(sequence)) if sequence.isdigit() else sequence
    key = hashlib.sha256(json.dumps([mid, sequence_key, bl], ensure_ascii=False).encode()).hexdigest()
    error = ''
    try:
        parts = mid.split('-')
        if len(parts) != 5 or parts[0] not in ('1', '4', '7') or parts[1] not in ('0', '1'):
            raise ValueError('IDManifiesto incompatible')
        if not re.fullmatch(r'\d+', parts[2]) or not re.fullmatch(r'[A-Za-z]\d+', parts[3]):
            raise ValueError('Número o ubicación del manifiesto inválidos')
        date = datetime.strptime(parts[4], '%d/%m/%y').date()
        if not bl or bl.lower() in ('nan', 'none', 'null'):
            raise ValueError('BL vacío')
        if sequence and (not sequence.isdigit() or int(sequence) < 1):
            raise ValueError('Secuencia Tica inválida')
        provided = datetime.strptime(original.get('Fecha Manifiesto', ''), '%d/%m/%Y').date()
        if date != provided:
            raise ValueError('Fecha Manifiesto no coincide con la fecha de arribo del ID')
        original.update(ID2=parts[1], ID3=parts[2], ID4=parts[3])
    except (ValueError, TypeError) as exc:
        error = str(exc)
    return {'key': key, 'ordinal': ordinal, 'record': original, 'error': error}


def query_dates(record, config):
    if config.get('dates_from_input', True):
        day = datetime.strptime(record['Fecha Manifiesto'], '%d/%m/%Y').date()
        last = calendar.monthrange(day.year, day.month)[1]
        return f'01/{day.month:02d}/{day.year:04d}', f'{last:02d}/{day.month:02d}/{day.year:04d}'
    return config['fecha_inicio'], config['fecha_fin']


def batch_scope(df, config):
    scope = {'version': 1, 'sheet': config.get('sheet_name', 'BLS'),
             'dates_from_input': bool(config.get('dates_from_input', True)),
             'target_url': config.get('target_url', '')}
    if not scope['dates_from_input']:
        scope.update(fecha_inicio=config['fecha_inicio'], fecha_fin=config['fecha_fin'])
    digest = hashlib.sha256(json.dumps(scope, sort_keys=True).encode())
    columns = list(df.columns)
    for values in df.itertuples(index=False, name=None):
        job = input_job(dict(zip(columns, values)), 0)
        digest.update(json.dumps(job['record'], sort_keys=True, ensure_ascii=False).encode())
        digest.update(b'\n')
    return digest.hexdigest(), scope
