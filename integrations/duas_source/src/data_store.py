"""Descargas verificadas por período/régimen/rango; Excel es una exportación."""
import calendar
from contextlib import contextmanager
from datetime import date
import json
import os
from pathlib import Path
import re
import sqlite3

MONTHS = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO',
          'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
REGIMENES = ['EXPORTACION', 'EXPORTACION TEMPORAL', 'IMPORTACION DEFINITIVA',
            'IMPORTACION TEMPORAL', 'PERFECCIONAMIENTO ACTIVO', 'REIMPORTACION',
            'REIMPORTACION PERFECCIONAMIENTO PASIVO', 'TRANSITO', 'ZONA FRANCA']
REGIMENES_IMPORTACION = {'IMPORTACION DEFINITIVA', 'IMPORTACION TEMPORAL',
                       'REIMPORTACION', 'REIMPORTACION PERFECCIONAMIENTO PASIVO'}
OUTPUT_NAMES = ('Total_DUAS.xlsx', 'Total_DUAS - Transito.xlsx', 'Total_DUAS - Importacion.xlsx')


def period_for(month, year):
    try:
        return date(int(year), MONTHS.index(month.upper()) + 1, 1).strftime('%Y-%m')
    except (ValueError, AttributeError):
        raise ValueError('Selecciona un mes y año válidos.') from None


def ranges_for(period, mode, start=None, end=None):
    year, month = map(int, period.split('-'))
    last = calendar.monthrange(year, month)[1]
    if mode in ('Ambos', 'Ambas partes'):
        return [(1, 15), (16, last)]
    if mode == 'Primera parte (1-15)':
        return [(1, 15)]
    if mode == 'Segunda parte (16-fin)':
        return [(16, last)]
    if mode == 'Rango personalizado' and start is not None and end is not None:
        if 1 <= int(start) <= int(end) <= last:
            return [(int(start), int(end))]
    raise ValueError(f'Rango inválido. El mes seleccionado tiene {last} días.')


def normalize_record(record):
    record = {str(key): str(value or '').strip() for key, value in record.items()}
    fields = []
    for key, width in [('aduana', 3), ('ano', 4), ('numero', 6)]:
        value = record.get(key, '')
        if not re.fullmatch(r'[0-9]{1,' + str(width) + '}', value):
            raise ValueError(f'El XML contiene un DUA inválido: campo {key}.')
        if key == 'ano' and len(value) != 4:
            raise ValueError('El año del DUA debe tener cuatro dígitos.')
        record[key] = value.zfill(width)
        fields.append(record[key])
    return '-'.join(fields), record


class RunLock:
    def __init__(self, path):
        self.path = Path(str(path) + '.lock')

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('a+b')
        if self.path.stat().st_size == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('Otra instancia está usando estos datos. Espera a que termine.') from None
        return self

    def __exit__(self, *args):
        self.stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream, fcntl.LOCK_UN)
        self.stream.close()


class RangeStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY, period TEXT NOT NULL, regimen TEXT NOT NULL,
                day_start INTEGER NOT NULL, day_end INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','retry','succeeded')),
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
                count INTEGER NOT NULL DEFAULT 0, updated TEXT,
                UNIQUE(period,regimen,day_start,day_end));
            CREATE TABLE IF NOT EXISTS records (
                query_id INTEGER NOT NULL REFERENCES queries(id), dua TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(query_id,dua));
            CREATE INDEX IF NOT EXISTS query_period ON queries(period,regimen,status);
            CREATE TABLE IF NOT EXISTS query_parts (
                parent_id INTEGER NOT NULL REFERENCES queries(id),
                child_id INTEGER NOT NULL REFERENCES queries(id),
                PRIMARY KEY(parent_id, child_id), CHECK(parent_id != child_id));
        ''')

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self.db
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def plan(self, period, regimens, ranges, refresh=False):
        ids = []
        with self.transaction() as db:
            for regimen in regimens:
                if regimen not in REGIMENES:
                    raise ValueError('Régimen no configurado.')
                for start, end in ranges:
                    ranges_for(period, 'Rango personalizado', start, end)
                    db.execute('INSERT OR IGNORE INTO queries(period,regimen,day_start,day_end) VALUES (?,?,?,?)',
                               (period, regimen, start, end))
                    row = db.execute('SELECT * FROM queries WHERE period=? AND regimen=? AND day_start=? AND day_end=?',
                                     (period, regimen, start, end)).fetchone()
                    ids.append(row['id'])
                    if refresh or row['status'] == 'running':
                        db.execute("UPDATE queries SET status='pending',last_error='' WHERE id=?", (row['id'],))
                    if refresh:
                        # Refresh every saved piece too; an old child must not
                        # silently satisfy a new download of its parent.
                        db.execute("UPDATE queries SET status='pending',last_error='' "
                                   'WHERE period=? AND regimen=? AND day_start>=? AND day_end<=?',
                                   (period, regimen, start, end))
        return ids

    def children(self, query_id):
        return [row[0] for row in self.db.execute(
            'SELECT child_id FROM query_parts JOIN queries ON queries.id=child_id '
            'WHERE parent_id=? ORDER BY day_start,day_end', (query_id,))]

    def leaves(self, query_ids):
        """Durable, ordered work list; split parents are never downloaded again."""
        result = dict()
        def visit(query_id):
            children = self.children(query_id)
            if children:
                for child in children:
                    visit(child)
            else:
                result[query_id] = None
        for query_id in query_ids:
            visit(query_id)
        return list(result)

    def is_complete(self, query_id):
        return all(self.get(key)['status'] == 'succeeded' for key in self.work_items([query_id]))

    def work_items(self, query_ids):
        # Include earlier custom queries inside the requested range as well.
        # Their failed refreshes block export and must also be resumable here.
        related = dict.fromkeys(query_ids)
        for query_id in query_ids:
            query = self.get(query_id)
            for row in self.db.execute('SELECT id FROM queries WHERE period=? AND regimen=? '
                                       'AND day_start>=? AND day_end<=? ORDER BY day_start,day_end',
                                       (query['period'], query['regimen'], query['day_start'], query['day_end'])):
                related[row[0]] = None
        return self.leaves(related)

    def split(self, query_id):
        """Replace an unsuccessful range by two exact, non-overlapping halves."""
        with self.transaction() as db:
            existing = self.children(query_id)
            if existing:
                return existing
            parent = self.get(query_id)
            start, end = parent['day_start'], parent['day_end']
            if start == end or parent['status'] == 'succeeded':
                return []
            midpoint = start + (end - start + 1) // 2 - 1
            children = []
            for first, last in ((start, midpoint), (midpoint + 1, end)):
                db.execute('INSERT OR IGNORE INTO queries(period,regimen,day_start,day_end) VALUES (?,?,?,?)',
                           (parent['period'], parent['regimen'], first, last))
                child = db.execute('SELECT id FROM queries WHERE period=? AND regimen=? AND day_start=? AND day_end=?',
                                   (parent['period'], parent['regimen'], first, last)).fetchone()[0]
                db.execute('INSERT INTO query_parts VALUES (?,?)', (query_id, child))
                children.append(child)
            return children

    def get(self, query_id):
        return dict(self.db.execute('SELECT * FROM queries WHERE id=?', (query_id,)).fetchone())

    def start(self, query_id):
        with self.transaction() as db:
            db.execute("UPDATE queries SET status='running',attempts=attempts+1 WHERE id=?", (query_id,))

    def fail(self, query_id, message, cancelled=False):
        with self.transaction() as db:
            db.execute('UPDATE queries SET status=?,last_error=? WHERE id=?',
                       ('pending' if cancelled else 'retry', str(message)[:2000], query_id))

    def complete(self, query_id, records):
        # Old verified rows remain intact if validation or disk write fails.
        with self.transaction() as db:
            db.execute('DELETE FROM records WHERE query_id=?', (query_id,))
            for record in records:
                dua, normalized = normalize_record(record)
                db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?)',
                           (query_id, dua, json.dumps(normalized, ensure_ascii=False)))
            count = db.execute('SELECT COUNT(*) FROM records WHERE query_id=?', (query_id,)).fetchone()[0]
            db.execute("UPDATE queries SET status='succeeded',last_error='',count=?,updated=CURRENT_TIMESTAMP WHERE id=?",
                       (count, query_id))
        return count

    def collect(self, period, ranges):
        """Only whole verified queries inside requested ranges can prove coverage."""
        first, last = ranges[0][0], ranges[-1][1]
        lists = [dict(), dict(), dict()]
        missing = []
        for regimen in REGIMENES:
            rows = self.db.execute('SELECT * FROM queries WHERE period=? AND regimen=? AND day_start>=? '
                                   'AND day_end<=? AND NOT EXISTS '
                                   '(SELECT 1 FROM query_parts WHERE parent_id=queries.id) '
                                   'ORDER BY day_start,day_end,id', (period, regimen, first, last)).fetchall()
            covered = set()
            # A requested refresh/error must not be hidden by an overlapping older query.
            unresolved = [r for r in rows if r['status'] != 'succeeded']
            for row in rows:
                if row['status'] != 'succeeded':
                    continue
                covered.update(range(row['day_start'], row['day_end'] + 1))
                for record in self.db.execute('SELECT dua FROM records WHERE query_id=? ORDER BY rowid', (row['id'],)):
                    dua = record['dua']
                    lists[0][dua] = None
                    if regimen == 'TRANSITO':
                        lists[1][dua] = None
                    elif regimen in REGIMENES_IMPORTACION:
                        lists[2][dua] = None
            absent = sorted(set(range(first, last + 1)) - covered)
            if absent or unresolved:
                detail = 'días sin descarga verificada: ' + ', '.join(map(str, absent)) if absent else 'hay rangos pendientes de actualización'
                missing.append(f'{regimen}: {detail}')
        return [list(items) for items in lists], missing

    def export_queries(self, period, regimen):
        return [dict(row) for row in self.db.execute(
            'SELECT * FROM queries WHERE period=? AND regimen=? AND NOT EXISTS '
            '(SELECT 1 FROM query_parts WHERE parent_id=queries.id) ORDER BY day_start,day_end,id',
            (period, regimen))]

    def export_records(self, query_ids, unique=False):
        seen = set()
        for query_id in query_ids:
            for row in self.db.execute('SELECT dua,payload FROM records WHERE query_id=? ORDER BY rowid', (query_id,)):
                if unique and row['dua'] in seen:
                    continue
                if unique:
                    seen.add(row['dua'])
                yield json.loads(row['payload'])
