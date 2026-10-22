"""Evidencia acotada de XMovimientos, sin GXState ni tablas ajenas al resultado."""
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import re
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .identifiers import normalize_dua

FORMAT = 'chc.xmovimientos.evidence'
VERSION = 1
REPORT_ID = 'chc-movement-evidence'
MAX_REPORT_BYTES = 32768
IDENTITY_FIELDS = ('vVCODI_ADUA', 'vVANO_PRE', 'vVNUME_CORR')


def short_text(value, limit=200):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + '…'


def compact_form(snapshot):
    """Conservar identidades enviadas, excluyendo CAPTCHA, sesiones y otros campos."""
    if not isinstance(snapshot, dict):
        return {}
    result = {'requested': short_text(snapshot.get('requested', ''), 32)}
    for name in ('fields', 'submission'):
        source = snapshot.get(name)
        if isinstance(source, dict):
            result[name] = {key: [short_text(v, 32) for v in value[:2]]
                            if isinstance(value, list) else short_text(value, 32)
                            for key in IDENTITY_FIELDS if (value := source.get(key)) is not None}
    return result


def _number(value):
    return type(value) is int and value >= 0


def _validate(data):
    if not isinstance(data, dict) or data.get('format') != FORMAT or data.get('version') != VERSION:
        raise ValueError('Formato de evidencia de movimientos desconocido.')
    if not isinstance(data.get('requested_dua'), str) or not isinstance(data.get('observed_dua'), str):
        raise ValueError('La evidencia carece de identidad.')
    for section, fields in (('table', ('total_rows', 'header_columns', 'data_rows')),
                            ('errors', ('count',)), ('pagination', ('count', 'enabled_count'))):
        values = data.get(section)
        if not isinstance(values, dict) or any(not _number(values.get(key)) for key in fields):
            raise ValueError('La evidencia carece de comprobaciones verificables.')
    table = data['table']
    if type(table.get('present')) is not bool or table['data_rows'] != max(0, table['total_rows'] - 1):
        raise ValueError('Conteos de tabla incompatibles.')
    if not table['present'] and (table['total_rows'] or table['header_columns']):
        raise ValueError('La tabla ausente contiene conteos incompatibles.')
    if data['pagination']['enabled_count'] > data['pagination']['count']:
        raise ValueError('Conteos de paginación incompatibles.')
    return data


def verified_empty_observation(data, dua):
    try:
        _validate(data)
        return (normalize_dua(data['requested_dua']) == normalize_dua(dua)
                and normalize_dua(data['observed_dua']) == normalize_dua(dua)
                and data['table']['present'] is True
                and data['table']['total_rows'] == 1
                and data['table']['header_columns'] >= 5
                and data['errors']['count'] == 0
                and data['pagination']['enabled_count'] == 0)
    except (ValueError, KeyError, TypeError):
        return False


def read_summary(source):
    """None identifica HTML original; un resumen corrupto nunca pasa por original."""
    soup = source if isinstance(source, BeautifulSoup) else BeautifulSoup(source, 'html.parser')
    node = soup.find(id=REPORT_ID)
    if node is None:
        return None
    data = _validate(json.loads(node.get_text()))
    if (not isinstance(data.get('source_sha256'), str)
            or not re.fullmatch('[0-9a-f]{64}', data['source_sha256'])
            or not _number(data.get('source_bytes')) or not data['source_bytes']
            or not isinstance(data.get('captured_at'), str) or not data['captured_at']
            or data.get('timestamp_origin') not in ('capture', 'file_mtime')):
        raise ValueError('El resumen carece de fecha y firma de la respuesta original.')
    return data


def observe_html(source, dua):
    soup = BeautifulSoup(source, 'html.parser')
    previous = read_summary(soup)
    if previous is not None:
        if normalize_dua(previous['requested_dua']) != normalize_dua(dua):
            raise ValueError('La identidad del resumen no corresponde al archivo.')
        return previous
    identity = [soup.select_one('#span_' + key)
                for key in ('CODI_ADUAN', 'ANO_PRESE', 'NUME_CORRE')]
    actual = '-'.join(short_text(node.get_text(strip=True), 32) if node else '' for node in identity)
    table = soup.find('table', id='SubstkContainerTbl')
    rows = table.find_all('tr') if table is not None else []
    errors = [node for node in soup.select('#ERROR, .gx-error-message') if node.get_text(strip=True)]
    pagers = soup.select('[name="SIGUIENTE"]')
    return {'format': FORMAT, 'version': VERSION, 'requested_dua': normalize_dua(dua),
            'observed_dua': actual,
            'table': {'present': table is not None, 'total_rows': len(rows),
                      'header_columns': len(rows[0].find_all('th')) if rows else 0,
                      'data_rows': max(0, len(rows) - 1),
                      'headers': [short_text(th.get_text(' ', strip=True), 80)
                                  for th in rows[0].find_all('th')[:8]] if rows else [],
                      'sample_rows': [[short_text(td.get_text(' ', strip=True), 120)
                                       for td in tr.find_all('td')[:6]] for tr in rows[1:4]]},
            'errors': {'count': len(errors), 'samples': [short_text(node.get_text(' ', strip=True), 240)
                                                        for node in errors[:3]]},
            'pagination': {'count': len(pagers),
                           'enabled_count': sum(not node.has_attr('disabled') for node in pagers)}}


def render_summary(data):
    _validate(data)
    verdict = ('Vacío verificado' if verified_empty_observation(data, data['requested_dua'])
               else 'Diagnóstico de consulta; no acredita un vacío')
    document = ('<!doctype html><html lang="es"><meta charset="utf-8">'
                '<title>Evidencia de XMovimientos</title><body>'
                '<h1>Evidencia de XMovimientos</h1><p>' + escape(verdict) + '</p>'
                '<p>DUA solicitado: ' + escape(data['requested_dua']) + '<br>DUA observado: '
                + escape(data['observed_dua']) + '<br>Fecha: ' + escape(data.get('captured_at', ''))
                + '<br>Filas de movimientos observadas: ' + str(data['table']['data_rows']) + '</p>'
                '<p>Resumen de la respuesta observada. Conserva identidad, encabezados, conteos, '
                'mensajes y paginación; las muestras de filas y mensajes están limitadas. '
                'No contiene la página completa de TICA.</p><pre id="' + REPORT_ID + '">'
                + escape(json.dumps(data, ensure_ascii=False, indent=2)) + '</pre></body></html>')
    if len(document.encode('utf-8')) > MAX_REPORT_BYTES:
        raise ValueError('El resumen supera el tamaño máximo permitido.')
    return document


def summarize_html(source, dua, snapshot=None, url='', captured_at=None, timestamp_origin='capture'):
    data = observe_html(source, dua)
    # No envolver ni cambiar la fecha/hash de un resumen ya convertido.
    if 'source_sha256' not in data:
        raw = source.encode('utf-8')
        address = urlsplit(url)
        data.update(captured_at=captured_at or datetime.now(timezone.utc).isoformat(),
                    timestamp_origin=timestamp_origin, source_sha256=hashlib.sha256(raw).hexdigest(),
                    source_bytes=len(raw), url=short_text(urlunsplit((address.scheme, address.netloc,
                                                                   address.path, '', '')), 300),
                    form=compact_form(snapshot))
    document = render_summary(data)
    # Comprobar el formato persistido y la misma decisión de vacío antes de escribir.
    restored = read_summary(document)
    if restored != data or verified_empty_observation(restored, dua) != verified_empty_observation(data, dua):
        raise ValueError('No se pudo comprobar la evidencia resumida.')
    return document
