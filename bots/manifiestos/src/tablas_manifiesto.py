"""Lectura estricta de DUAs y Movimientos, con el mismo contenido del bot original."""
import csv
import json
import logging
import shutil
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from conocimientos import FormInputs, GridPage, IDENTITY, IncompleteTable, KnowledgeStore, SessionExpired, PortalErrorPage
from resultados import exclusion_csv_path
from conocimientos_queue import now

HEADERS = {
    'duas': ['Conoc.', 'Línea', 'Aduana', 'Año', 'DUA', 'Item', 'Agente',
             'Cantidad de Bultos', 'Estado de la Asociación', 'Fecha de la Asociación'],
    'movimientos': ['Deposito', 'Movimiento', 'Año', 'Tipo de Mov.', 'Fecha', 'Estado',
                    'Conoc.', 'Línea', 'Tipo de Bultos', 'Total', 'Usados', '',
                    'Consignatario', 'Razón Social'],
}
LINK_FIELDS = {'duas': 'vVDUAS', 'movimientos': 'vVMOVSTK'}
FIELDS = {
    'duas': ['CGNROCONDNA', 'CGNROLIN', 'CODI_ADUAN', 'ANO_PRESE', 'NUME_CORRE',
             'NUME_SERIE', 'CODI_AGENT', 'CGCNTBULASO', 'CGESTASOD', 'CGFCHASOD'],
    'movimientos': ['CGDEPIDSTK', 'CGMOVSKID', 'CGANOMOV', 'CGMOVTPO', 'CGMOVFCH',
                    'CGMOVSTS', 'CGNROCONDNA', 'CGNROLIN', 'CGTPOBULMOV', 'CGTOTBULMOV',
                    'CGBULUSA', 'CGMOVCDOC', 'CGMOVCONSI', 'vVCONSNOM'],
}


class GridHeaders(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.headers, self.tables, self.cell = [], [], None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.tables.append(dict(attrs).get('id') == 'Grid1ContainerTbl')
        if tag == 'th' and any(self.tables):
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag == 'th' and self.cell is not None:
            self.headers.append(''.join(self.cell).strip().replace('\xa0', ' '))
            self.cell = None
        if tag == 'table' and self.tables:
            self.tables.pop()


def read_grid_count(raw, actual_count, flow):
    value = str(raw).strip()
    if (flow == 'duas' and value and set(value) == {'*'} and 1 <= len(value) <= 10
            and actual_count >= 10 ** len(value)):
        return None  # Máscara desbordada; se exige otro contador numérico verificable.
    return int(value)


def parse_table(html, expected_id, flow):
    try:
        document = FormInputs(html)
        form = document.values
        if 'GXState' not in form:
            if flow == 'duas':
                for action in document.form_actions:
                    target = urlsplit(action)
                    query = {key.casefold(): values for key, values in parse_qs(target.query).items()}
                    error_paths = query.get('aspxerrorpath', [])
                    if (target.path.rstrip('/').rsplit('/', 1)[-1].casefold() in ('frmambiente', 'frmambiente.aspx')
                            and any(urlsplit(path).path.casefold().endswith('/hcgduama.aspx') for path in error_paths)):
                        raise PortalErrorPage('TICA devolvió frmAmbiente con aspxerrorpath=/Tica/hcgduama.aspx '
                                              'en lugar de la tabla de DUAs; excluido de reintentos')
            raise SessionExpired('La respuesta no contiene el formulario de la tabla')
        state = json.loads(form['GXState'])
        actual = '-'.join(str(state[key]).strip() for key in IDENTITY)
        if actual != expected_id:
            raise IncompleteTable(f'Manifiesto inesperado: {actual}; esperado {expected_id}')
        headers = GridHeaders(html).headers
        if headers and headers != HEADERS[flow]:
            raise IncompleteTable(f'Cambió el esquema de columnas de {flow}')
        values = json.loads(form['Grid1ContainerDataV'])
        if values == [[]]:
            values = []
        grid = json.loads(state['Grid1ContainerData'])
        # Tolerar máscaras como **** solo con otro contador numérico que acredite DataV.
        if not isinstance(values, list):
            raise IncompleteTable('La tabla no contiene una lista de filas')
        counts = [read_grid_count(raw, len(values), flow) for raw in (grid['Count'], state['nRC_Grid1'])]
        # nRC puede desbordar 16 bits: 61356 filas se representan como -4180.
        # Aceptar únicamente la equivalencia exacta con Count y DataV completos.
        signed_16_count = (len(values) + 32768) % 65536 - 32768
        if (flow == 'duas' and len(values) >= 32768 and counts[0] == len(values)
                and counts[1] == signed_16_count):
            counts[1] = len(values)
        numeric_counts = [count for count in counts if count is not None]
        if not numeric_counts or any(count != len(values) for count in numeric_counts):
            raise IncompleteTable(f"Cantidad de filas inconsistente en la tabla: "
                                  f"datos={len(values) if isinstance(values, list) else 'inválido'}, "
                                  f"grid={grid['Count']}, nRC={state['nRC_Grid1']}")
        if values:
            fields = [(prop[0] if isinstance(prop[0], str) else prop[1]).rsplit('_', 1)[0]
                      for prop in grid['0']['Props']]
            if fields != FIELDS[flow]:
                raise IncompleteTable(f'Cambió el esquema de campos de {flow}')
        elif len(grid['Columns']) != len(HEADERS[flow]):
            raise IncompleteTable('Esquema de tabla vacía inválido')
        rows = []
        for row in values:
            if not isinstance(row, list) or len(row) != len(HEADERS[flow]):
                raise IncompleteTable('Fila con columnas incompletas')
            # No normalizar los valores: conservar exactamente lo que extraía pandas.
            rows.append([*row, expected_id])
        if 'GRID1_nEOF' in state or 'GRID1_nFirstRecordOnPage' in state:
            eof = str(state['GRID1_nEOF'])
            offset = int(state['GRID1_nFirstRecordOnPage'])
            if eof not in ('0', '1') or offset < 0 or (not rows and eof != '1'):
                raise IncompleteTable('Estado de paginación inválido')
            return GridPage(form, state, rows, offset, eof == '1')
        # Estas dos consultas entregan todos los registros en un grid sin paginación.
        if 'PagingButtonsNext' in html:
            raise IncompleteTable('Se detectó paginación sin estado verificable')
        return GridPage(form, state, rows, 0, True)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, IncompleteTable):
            raise
        raise IncompleteTable(f'Respuesta de {flow} inválida: {exc}') from exc


class ManifestTableStore(KnowledgeStore):
    def __init__(self, csv_path, scope, db_path=None, **kwargs):
        self.flow = scope['flow']
        self.columns = [*HEADERS[self.flow], 'manifiesto']
        self.index_column = f'index_flujo_{self.flow}'
        super().__init__(csv_path, scope, db_path=db_path, accept_legacy=True)
        try:
            self.db.execute('CREATE TABLE IF NOT EXISTS legacy_import (id INTEGER PRIMARY KEY CHECK(id=1))')
            if self.csv_path.exists() and not self.db.execute('SELECT 1 FROM legacy_import').fetchone() and not self.db.execute('SELECT 1 FROM manifests').fetchone():
                self._import_legacy()
        except BaseException:
            self.close()
            raise

    def start_run(self):
        if self.flow == 'duas':
            self._reconsider_conversion_errors()
        return super().start_run()

    def _reconsider_conversion_errors(self):
        """Repara exclusiones antiguas de conversión; conserva los intentos previos."""
        candidates = self.db.execute('''SELECT j.id,j.error FROM jobs j
            WHERE j.state='Excluido' AND lower(j.error) LIKE ?
            AND lower(j.error) NOT LIKE '%frmambiente%'
            AND NOT EXISTS (SELECT 1 FROM manifests m WHERE m.id=j.id)''',
            ('%invalid literal for int()%base 10%',)).fetchall()
        if not candidates:
            return
        with self.db:
            self.db.execute('''CREATE TABLE IF NOT EXISTS job_reconsiderations (
                manifest TEXT PRIMARY KEY, changed TEXT NOT NULL, previous_reason TEXT NOT NULL)''')
            for mid, reason in candidates:
                self.db.execute('INSERT OR REPLACE INTO job_reconsiderations VALUES (?,?,?)', (mid, now(), reason))
                self.db.execute("UPDATE jobs SET state='Pendiente',updated=? WHERE id=? AND state='Excluido'", (now(), mid))
        logging.info('[DUAS] %s consultas con errores de conversión recuperadas como Pendiente; '
                     'historial conservado', len(candidates))

    def _import_legacy(self):
        # Guardar el archivo intacto antes de cualquier exportación del formato nuevo.
        archive = self.db_path.parent / 'historicos' / self.csv_path.name
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(self.csv_path, archive)
        counts, order = Counter(), {}
        logging.info('[%s] Importando CSV anterior a SQLite: %s', self.flow, self.csv_path)
        with self.db, self.csv_path.open('r', encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream)
            if next(reader, None) != [self.index_column, *self.columns]:
                raise ValueError('El CSV anterior tiene otro esquema; se conserva para revisión')
            batch = []
            for position, row in enumerate(reader, 1):
                if len(row) != len(self.columns) + 1 or not row[-1]:
                    raise ValueError(f'Fila incompleta en el CSV anterior: {position}')
                mid = row[-1]
                order.setdefault(mid, len(order) + 1)
                counts[mid] += 1
                batch.append((mid, position, json.dumps(row[1:], ensure_ascii=False)))
                if len(batch) == 1000:
                    self.db.executemany('INSERT INTO rows VALUES (?,?,?)', batch)
                    batch.clear()
            self.db.executemany('INSERT INTO rows VALUES (?,?,?)', batch)
            self.db.executemany('INSERT INTO manifests VALUES (?,?,?)',
                [(mid, order[mid], json.dumps({'pages': 1, 'read': count, 'kept': count, 'source': 'CSV anterior'}))
                 for mid, count in counts.items()])
            self.db.execute('INSERT INTO legacy_import VALUES (1)')
        logging.info('[%s] Importados %s manifiestos y %s filas; CSV original conservado en %s',
                     self.flow, len(counts), sum(counts.values()), archive)

    def save(self, manifest_id, ordinal, rows, stats):
        if any(len(row) != len(self.columns) or row[-1] != manifest_id for row in rows):
            raise IncompleteTable('Resultado asignado a otro manifiesto o con columnas incompletas')
        with self.db:
            self.db.execute('DELETE FROM rows WHERE manifest=?', (manifest_id,))
            self.db.executemany('INSERT INTO rows VALUES (?,?,?)',
                [(manifest_id, position, json.dumps(row, ensure_ascii=False)) for position, row in enumerate(rows, 1)])
            self.db.execute('INSERT OR REPLACE INTO manifests VALUES (?,?,?)',
                            (manifest_id, ordinal, json.dumps(stats)))
            self.db.execute('DELETE FROM failures WHERE id=?', (manifest_id,))
            self.record_outcome(manifest_id, 'Guardado', stats=stats)
            self.db.execute('DELETE FROM partial_pages WHERE manifest=?', (manifest_id,))

    def export(self, failed_path=None):
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        query = ('SELECT r.data FROM rows r JOIN jobs j ON j.id=r.manifest '
                 "WHERE j.state='Guardado' ORDER BY j.ordinal,j.id,r.sequence") if self.selection_ready() else (
                 'SELECT r.data FROM rows r JOIN manifests m ON m.id=r.manifest ORDER BY m.ordinal,m.id,r.sequence')
        temp = self.csv_path.with_suffix('.csv.tmp')
        with temp.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow([self.index_column, *self.columns])
            for index, (data,) in enumerate(self.db.execute(query), 1):
                writer.writerow([index, *json.loads(data)])
        temp.replace(self.csv_path)
        if self.flow == 'duas':
            excluded_path = exclusion_csv_path(self.csv_path)
            excluded_path.parent.mkdir(parents=True, exist_ok=True)
            temp = excluded_path.with_suffix('.csv.tmp')
            with temp.open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['Fila origen', 'IDManifiesto', 'Fecha Manifiesto', 'Motivo', 'Intentos'])
                for source_ordinal, mid, reason, attempts in self.db.execute('''
                        SELECT source_ordinal,id,error,attempts FROM jobs
                        WHERE state='Excluido' ORDER BY ordinal,id'''):
                    writer.writerow([source_ordinal, mid, mid.rsplit('-', 1)[-1], reason, attempts])
            temp.replace(excluded_path)

    def exclude(self, manifest_id, ordinal, reason):
        if self.flow != 'duas':
            raise ValueError('La exclusión de frmAmbiente solo aplica a DUAs')
        with self.db:
            if self.job(manifest_id)['state'] != 'Descargando':
                raise RuntimeError('Solo se puede excluir un manifiesto que se está descargando')
            self.db.execute('INSERT OR REPLACE INTO failures VALUES (?,?,?)', (manifest_id, ordinal, reason))
            self.record_outcome(manifest_id, 'Excluido', error=reason)
