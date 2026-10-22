"""Nombres y selección de Manifiestos compartidos por la GUI y su worker."""
import calendar
from datetime import date
import hashlib
import json

MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
          'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')


def manifest_scope(flow, config):
    year, month = int(config['year']), int(config['month'])
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError('Año o mes inválido')
    modes = list(dict.fromkeys(config['modes']))
    if not modes or any(mode not in ('maritimo', 'aereo', 'terrestre') for mode in modes):
        raise ValueError('Seleccione al menos una modalidad')
    start = date.fromisoformat(config.get('start') or f'{year:04d}-{month:02d}-01')
    end = date.fromisoformat(config.get('end') or f'{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]}')
    if start > end or any((day.year, day.month) != (year, month) for day in (start, end)):
        raise ValueError('El intervalo debe estar ordenado y dentro del mes elegido.')
    courier = config.get('courier', 'todos')
    if courier not in ('todos', 'N', 'S'):
        raise ValueError('Filtro Courier inválido')
    return {'flow': flow, 'year': year, 'month': month, 'modes': modes,
            'start': start.isoformat(), 'end': end.isoformat(),
            'courier': courier if flow == 'conocimientos' else 'todos',
            'ids': sorted(set(config.get('manifestIds', '').split())),
            'limit': int(config.get('limit', 0))}


def normalized_scope(spec):
    return {**spec, 'modes': sorted(set(spec['modes'])), 'ids': sorted(set(spec['ids']))}


def cumulative_family(spec):
    """Una acumulación mensual; selecciones filtradas conservan su aislamiento."""
    if spec.get('ids') or spec.get('limit'):
        return None
    return {key:value for key,value in normalized_scope(spec).items()
            if key not in ('start','end','modes')}


def manifest_name(spec):
    year, month = spec['year'], spec['month']
    parts = [MONTHS[month - 1] + f'{year % 100:02d}']
    modes = sorted(set(spec['modes']))
    if modes != ['maritimo'] and not cumulative_family(spec):
        parts.append('-'.join(modes))
    start, end = date.fromisoformat(spec['start']), date.fromisoformat(spec['end'])
    if not cumulative_family(spec) and (start.day != 1 or end.day != calendar.monthrange(year, month)[1]):
        parts.append(f'{start.day:02d}-{end.day:02d}')
    if spec['courier'] != 'todos':
        parts.append('courier-' + spec['courier'].lower())
    if spec['limit']:
        parts.append('limite-' + str(spec['limit']))
    if spec['ids']:
        digest = hashlib.sha256(json.dumps(sorted(set(spec['ids']))).encode()).hexdigest()[:8]
        parts.append('ids-' + digest)
    return '_'.join(parts)
