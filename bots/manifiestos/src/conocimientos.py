"""Extracción paginada de conocimientos y avance transaccional por manifiesto."""
import asyncio
import csv
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from conocimientos_queue import OutputLock, QueueStore
from resultados import csv_for_database

MAX_CONCURRENCY = 32
DEFAULT_CONCURRENCY = MAX_CONCURRENCY


def validate_concurrency(value):
    try:
        workers = int(str(value))
    except (TypeError, ValueError):
        raise ValueError(f'Use un entero de 1 a {MAX_CONCURRENCY} descargas.') from None
    if not 1 <= workers <= MAX_CONCURRENCY:
        raise ValueError(f'Use de 1 a {MAX_CONCURRENCY} descargas.')
    return workers


COLUMNS = [
    'IDManifiesto', 'Secuencia Tica', 'BL original', 'Courier', 'Categoria',
    'Tipo', 'RUC del garante', 'Razón social', 'Descarga', 'Desc Descarga',
    'Master', 'Embarque', 'Desc Embarque', 'Estado', 'Nro de Conocimiento Master',
]
FIELDS = [
    'CGNROCONDNA', 'CGNROCON', 'CGCOURIER', 'vVCATEGORIA', 'CGTPOCON',
    'CGRUCAGECAR', 'vVGARANOM', 'CGPTODESCA', 'vDESCDESCARGA', 'vMASTER',
    'CGPTOEMBAR', 'vDESCEMBARQUE', 'CGCONEST', 'CGNROCONMTR',
]
IDENTITY = ['CGTPOTRANS', 'CGTPOMIC', 'CGNROMIC', 'RGDEPID', 'CGFCHARR']


class IncompleteTable(ValueError):
    """No se puede acreditar que la respuesta sea una tabla completa."""


class SessionExpired(IncompleteTable):
    """Respuesta sin formulario válido; permite renovar el enlace de consulta."""


class PortalErrorPage(IncompleteTable):
    """Pantalla frmAmbiente de DUAs: se registra como exclusión definitiva."""


def parse_main_rows(grid, raw_values, base_url, link_field='vVCONS'):
    """DataV contiene los valores reales; Props solo controla la presentación."""
    values = json.loads(raw_values) if isinstance(raw_values, str) else raw_values
    count = int(grid['Count'])
    if not isinstance(values, list) or len(values) != count:
        raise IncompleteTable('Cantidad de filas inconsistente en la lista de manifiestos')
    if count == 0:
        return []
    fields = [p[0].rsplit('_', 1)[0] for p in grid['0']['Props']]
    indices = [fields.index(field) for field in IDENTITY]
    labels = ['Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha']
    snapshot, legacy = [], {}
    for index, row in enumerate(values):
        if not isinstance(row, list) or len(row) != len(fields):
            raise IncompleteTable('Cambió el esquema de la lista de manifiestos')
        props = grid[str(index)]['Props']
        # Solo se reproduce el decodificador viejo para reparar pendientes previos.
        for prop in props:
            if len(prop) >= 2:
                legacy[prop[0].rsplit('_', 1)[0]] = str(prop[1]).strip()
        old_id = '-'.join(legacy.get(field, '') for field in IDENTITY)
        info = dict(zip(labels, [str(row[i]).strip() for i in indices]))
        link = next((p[1] for p in props if p[0].rsplit('_', 1)[0] == link_field and len(p) >= 2), None)
        snapshot.append((urljoin(base_url, link) if link else None, info, old_id))
    return snapshot


class FormInputs(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.values = {}
        self.form_actions = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.form_actions.append(attrs.get('action', ''))
        if (tag == 'input' and attrs.get('name')
                and attrs.get('type', '').lower() not in ('button', 'submit', 'password')):
            self.values[attrs['name']] = attrs.get('value', '')


@dataclass
class GridPage:
    form: dict
    state: dict
    rows: list
    offset: int
    eof: bool


def parse_page(html, expected_id):
    """Lee valores completos del grid, no las propiedades visuales comprimidas."""
    try:
        form = FormInputs(html).values
        if 'GXState' not in form:
            raise SessionExpired('La respuesta no contiene el formulario de conocimientos')
        state = json.loads(form['GXState'])
        identity = '-'.join(str(state[k]).strip() for k in IDENTITY)
        if identity != expected_id:
            raise IncompleteTable(f'Manifiesto inesperado: {identity}; esperado {expected_id}')
        grid = json.loads(state['Grid1ContainerData'])
        values = json.loads(form['Grid1ContainerDataV'])
        if values == [[]]:
            values = []
        offset = int(state['GRID1_nFirstRecordOnPage'])
        eof = str(state['GRID1_nEOF'])
        if eof not in ('0', '1') or offset < 0:
            raise IncompleteTable('Estado de paginación desconocido')
        if not isinstance(values, list) or len(values) != int(grid['Count']):
            raise IncompleteTable('Cantidad de filas inconsistente')
        if len(values) != int(state['nRC_Grid1']):
            raise IncompleteTable('Cantidad de filas inconsistente con nRC_Grid1')
        if not values:
            if eof != '1':
                raise IncompleteTable('Página vacía sin fin confirmado')
            return GridPage(form, state, [], offset, True)
        # GeneXus envía nombres de campos en Props, y valores íntegros en DataV.
        fields = [p[0].rsplit('_', 1)[0] for p in grid['0']['Props']]
        indices = [fields.index(field) for field in FIELDS]
        rows = []
        for values_row in values:
            if not isinstance(values_row, list) or len(values_row) != len(fields):
                raise IncompleteTable('Cambió el esquema de columnas de conocimientos')
            cells = [str(values_row[i]).replace('\xa0', ' ').strip() for i in indices]
            if not cells[0].isdigit() or not cells[1]:
                raise IncompleteTable('Conocimiento sin secuencia numérica o sin BL')
            rows.append([expected_id, *cells])
        return GridPage(form, state, rows, offset, eof == '1')
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, IncompleteTable):
            raise
        raise IncompleteTable(f'Respuesta de conocimientos inválida: {exc}') from exc


async def request_html(request, url, timeout, form=None, *, max_attempts=3,
                       activity_callback=None, heartbeat_seconds=15, expected_status=None):
    """Lee una respuesta completa; timeout=0 mantiene la espera hasta cancelarla."""
    for attempt in range(max_attempts):
        response = None
        started = time.monotonic()
        def activity(stage, **extra):
            if activity_callback:
                activity_callback({'stage': stage, 'attempt': attempt + 1, 'max_attempts': max_attempts,
                                   'elapsed': round(time.monotonic() - started, 1), 'timeout': timeout, **extra})
        async def heartbeat():
            while True:
                await asyncio.sleep(heartbeat_seconds)
                activity('waiting')
        ticker = asyncio.create_task(heartbeat()) if activity_callback else None
        try:
            activity('request')
            if form is None:
                response = await request.get(url, timeout=timeout * 1000)
            else:
                response = await request.post(url, form=form, timeout=timeout * 1000)
            activity('response', status=response.status)
            accepted = response.status == expected_status if expected_status is not None else response.ok
            if not accepted:
                if response.status in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                    activity('retry', error=f'HTTP {response.status}')
                    await asyncio.sleep(1 + attempt)
                    continue
                raise SessionExpired(f'HTTP {response.status} consultando tabla')
            return await response.text()
        except IncompleteTable:
            raise
        except Exception as exc:
            activity('error', error=str(exc).split('\nCall log:')[0] or type(exc).__name__)
            if attempt == max_attempts - 1:
                raise
            activity('retry', error=str(exc).split('\nCall log:')[0] or type(exc).__name__)
            await asyncio.sleep(1 + attempt)
        finally:
            if ticker is not None:
                ticker.cancel()
                await asyncio.gather(ticker, return_exceptions=True)
            if response is not None:
                await response.dispose()


async def extract_table(request, url, manifest_id, timeout=60, courier=None,
                        first_html=None, progress_callback=None, checkpoint=None,
                        refresh_seconds=600, renew_link=None, parse_html=None,
                        sequence_key=None, sort_rows=True, request_attempts=3,
                        recover_errors=True, activity_callback=None, expected_status=None,
                        parse_in_thread=False):
    """Sigue NEXT hasta EOF; nunca entrega un resultado parcial como exitoso."""
    if courier not in (None, 'N', 'S'):
        raise ValueError('Courier debe ser N, S o None')
    rows, sequences = [], set()
    expected_offset = 0
    pages = 0
    first_page = last_page = None
    parser = parse_html or parse_page
    async def parse_response(html):
        # Solo lectura: SQLite se actualiza después, en el hilo de la cola.
        if parse_in_thread:
            return await asyncio.to_thread(parser, html, manifest_id)
        return parser(html, manifest_id)
    async def fetch_html(form=None):
        return await request_html(request, url, timeout, form, max_attempts=request_attempts,
                                  activity_callback=activity_callback, expected_status=expected_status)

    def accept(page, persist=True):
        nonlocal pages, expected_offset, first_page, last_page
        if page.offset != expected_offset:
            raise IncompleteTable(f'Página repetida o faltante: {page.offset}; se esperaba {expected_offset}')
        pages += 1
        for index, row in enumerate(page.rows):
            seq = sequence_key(row, page.offset + index) if sequence_key else int(row[1])
            if seq in sequences:
                raise IncompleteTable(f'Secuencia repetida entre páginas: {seq}')
            sequences.add(seq)
            if courier is None or row[3] == courier:
                rows.append(row)
        expected_offset += len(page.rows)
        if persist and checkpoint is not None:
            checkpoint.save_checkpoint(manifest_id, page)
        first_page = first_page or page
        last_page = page

    def notify_progress():
        if progress_callback:
            progress_callback({'pages': pages, 'read': expected_offset, 'kept': len(rows)})

    def next_form(page, offset=None):
        state = dict(page.state, _EventName='EGRID1PAGING.', _EventGridId='', _EventRowId='')
        if offset is not None:
            state.update(GRID1_nFirstRecordOnPage=str(offset), GRID1_nEOF='0')
        return dict(page.form, GXState=json.dumps(state), GRID1PAGING='NEXT')

    async def restore():
        """Renueva el formulario y verifica la página ancla antes de continuar."""
        fresh = await parse_response(await fetch_html())
        if fresh.offset != 0:
            raise IncompleteTable('La renovación no comenzó en la primera página')
        if first_page is None:
            return fresh
        if fresh.rows != first_page.rows or fresh.eof != first_page.eof:
            raise IncompleteTable('La primera página cambió; se conserva el avance para revisión')
        if last_page.offset:
            size = len(fresh.rows)
            if not size or last_page.offset % size:
                raise IncompleteTable('Cambió el tamaño de página; no se puede reanudar con seguridad')
            fresh = await parse_response(await fetch_html(next_form(fresh, last_page.offset - size)))
        if (fresh.offset, fresh.rows, fresh.eof) != (last_page.offset, last_page.rows, last_page.eof):
            raise IncompleteTable('La página de reanudación cambió; se conserva el avance para revisión')
        return fresh

    async def recover():
        nonlocal url
        # Los errores de integridad no se ignoran ni se sobrescriben.
        for attempt in range(3 if recover_errors else 1):
            try:
                if attempt and renew_link:
                    url = await renew_link()
                return await restore()
            except Exception as exc:
                if isinstance(exc, IncompleteTable) and not isinstance(exc, SessionExpired):
                    raise
                if not recover_errors or attempt == 2:
                    raise
                await asyncio.sleep(2 * (attempt + 1))

    if checkpoint is not None:
        for saved in checkpoint.load_checkpoint(manifest_id):
            if last_page is not None and last_page.eof:
                raise IncompleteTable('Avance guardado contiene páginas después del final')
            accept(saved, persist=False)
        if last_page is not None:
            notify_progress()
            logging.info('[CONS] %s: recuperadas %s páginas y %s registros desde SQLite',
                         manifest_id, pages, expected_offset)

    if last_page is None:
        try:
            html = first_html if first_html is not None else await fetch_html()
            page = await parse_response(html)
        except Exception as exc:
            if checkpoint is None or not recover_errors or (isinstance(exc, IncompleteTable) and not isinstance(exc, SessionExpired)):
                raise
            page = await recover()
        accept(page)
        notify_progress()
    elif last_page.eof:
        page = last_page
    else:
        page = await recover()
    refreshed = time.monotonic()
    while not page.eof:
        if pages >= 10000:
            raise IncompleteTable('Límite de seguridad de paginación excedido')
        if refresh_seconds and time.monotonic() - refreshed >= refresh_seconds:
            logging.info('[CONS] %s: renovando formulario en página %s; avance conservado', manifest_id, pages)
            page = await recover()
            refreshed = time.monotonic()
        try:
            html = await fetch_html(next_form(page))
            received = await parse_response(html)
        except Exception as exc:
            if checkpoint is None or not recover_errors or (isinstance(exc, IncompleteTable) and not isinstance(exc, SessionExpired)):
                raise
            logging.warning('[CONS] %s: reconectando desde la página %s guardada', manifest_id, pages)
            page = await recover()
            refreshed = time.monotonic()
            html = await fetch_html(next_form(page))
            received = await parse_response(html)
        page = received
        accept(page)
        notify_progress()
    if sort_rows:
        rows.sort(key=lambda row: int(row[1]))
    logging.info('[CONS] %s: %s páginas, %s leídos, %s conservados',
                 manifest_id, pages, expected_offset, len(rows))
    return rows, {'pages': pages, 'read': expected_offset, 'kept': len(rows)}


class KnowledgeStore(QueueStore):
    """Checkpoint SQLite: un manifiesto solo se confirma al terminar sus páginas."""
    def __init__(self, csv_path, scope, db_path=None, accept_legacy=False):
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        db_path = Path(db_path) if db_path is not None else self.csv_path.with_suffix('.sqlite3')
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path.resolve()
        if self.csv_path.exists() and not db_path.exists() and not accept_legacy:
            raise ValueError('El CSV ya existe sin control de integridad. Elija otra carpeta de salida.')
        self.lock = OutputLock(str(db_path) + '.lock')
        self.db = None
        try:
            self.db = sqlite3.connect(db_path)
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata (scope TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS manifests (
                    id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL, stats TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rows (
                    manifest TEXT NOT NULL, sequence INTEGER NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(manifest, sequence));
                CREATE TABLE IF NOT EXISTS failures (
                    id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL, reason TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS partial_pages (
                    manifest TEXT NOT NULL, offset INTEGER NOT NULL,
                    data TEXT NOT NULL, eof INTEGER NOT NULL,
                    PRIMARY KEY(manifest, offset));
            ''')
            signature = json.dumps(scope, sort_keys=True)
            stored = self.db.execute('SELECT scope FROM metadata').fetchone()
            if stored and stored[0] != signature:
                raise ValueError('Esta salida pertenece a otros filtros. Elija otra carpeta de salida.')
            if not stored:
                self.db.execute('INSERT INTO metadata VALUES (?)', (signature,))
                self.db.commit()
            self.initialize_queue()
        except Exception:
            if self.db:
                self.db.close()
            self.lock.close()
            raise

    @classmethod
    def open_existing(cls, db_path):
        path = Path(db_path).resolve()
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            scope = json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0])
        finally:
            db.close()
        if scope.get('flow') in ('duas', 'movimientos'):
            from tablas_manifiesto import ManifestTableStore
            return ManifestTableStore(csv_for_database(path), scope, db_path=path)
        return cls(csv_for_database(path), scope, db_path=path)

    def completed(self, manifest_id):
        return self.db.execute('SELECT 1 FROM manifests WHERE id=?', (manifest_id,)).fetchone() is not None

    def save_checkpoint(self, manifest_id, page):
        with self.db:
            self.db.execute('INSERT INTO partial_pages VALUES (?,?,?,?)',
                (manifest_id, page.offset, json.dumps(page.rows, ensure_ascii=False), int(page.eof)))

    def load_checkpoint(self, manifest_id):
        return [GridPage({}, {}, json.loads(data), offset, bool(eof)) for offset, data, eof
                in self.db.execute('SELECT offset,data,eof FROM partial_pages WHERE manifest=? ORDER BY offset',
                                   (manifest_id,))]

    def save(self, manifest_id, ordinal, rows, stats):
        # Incluye vacíos válidos y manifiestos que no contienen el courier elegido.
        if any(len(r) != len(COLUMNS) or r[0] != manifest_id for r in rows):
            raise IncompleteTable('Resultado asignado a otro manifiesto o con columnas incompletas')
        with self.db:
            self.db.execute('DELETE FROM rows WHERE manifest=?', (manifest_id,))
            self.db.executemany('INSERT INTO rows VALUES (?, ?, ?)',
                                [(manifest_id, int(r[1]), json.dumps(r, ensure_ascii=False)) for r in rows])
            self.db.execute('INSERT OR REPLACE INTO manifests VALUES (?, ?, ?)',
                            (manifest_id, ordinal, json.dumps(stats)))
            self.db.execute('DELETE FROM failures WHERE id=?', (manifest_id,))
            self.record_outcome(manifest_id, 'Guardado', stats=stats)
            self.db.execute('DELETE FROM partial_pages WHERE manifest=?', (manifest_id,))

    def fail(self, manifest_id, ordinal, reason):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO failures VALUES (?, ?, ?)',
                            (manifest_id, ordinal, reason))
            self.record_outcome(manifest_id, 'Pendiente', error=reason)

    def export(self, failed_path=None):
        """Exporta solo los datos; el estado y los errores permanecen en SQLite."""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        query = ('SELECT r.data FROM rows r JOIN jobs j ON j.id=r.manifest '
                 "WHERE j.state='Guardado' ORDER BY j.ordinal,j.id,r.sequence") if self.selection_ready() else (
                 'SELECT r.data FROM rows r JOIN manifests m ON m.id=r.manifest ORDER BY m.ordinal,m.id,r.sequence')
        temp = self.csv_path.with_suffix('.csv.tmp')
        with temp.open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            writer.writerows(json.loads(data) for data, in self.db.execute(query))
        os.replace(temp, self.csv_path)

    def summary(self):
        return {name: self.db.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
                for name in ('manifests', 'rows', 'failures')}

    def close(self):
        try:
            self.db.close()
        finally:
            self.lock.close()
