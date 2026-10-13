"""Cola y resultados transaccionales, con un escritor y exportación ordenada."""
import csv
from contextlib import closing
import json
import os
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.inputs import input_job


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class OutputLock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0, 2)
                if not self.file.tell():
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuntimeError('Otra ejecución está utilizando este lote.') from exc

    def close(self):
        self.file.close()


class JobStore:
    def __init__(self, path, signature, scope):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = OutputLock(str(self.path) + '.lock')
        self.db = None
        self._pending_cursor = None
        self.run_id = None
        try:
            self.db = sqlite3.connect(self.path)
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY,ordinal INTEGER NOT NULL,payload TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('Pendiente','Descargando','Guardado','Inválido')),
                    attempts INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '',
                    error_code TEXT NOT NULL DEFAULT '',result_count INTEGER NOT NULL DEFAULT 0,
                    token TEXT,updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS inputs(ordinal INTEGER PRIMARY KEY,job TEXT NOT NULL,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS results(job TEXT NOT NULL,position INTEGER NOT NULL,data TEXT NOT NULL,
                    PRIMARY KEY(job,position));
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,started TEXT,finished TEXT,state TEXT);
                CREATE TABLE IF NOT EXISTS attempts(token TEXT PRIMARY KEY,run TEXT,job TEXT,
                    started TEXT,finished TEXT,state TEXT,error TEXT NOT NULL DEFAULT '');
            ''')
            existing = self.get_metadata('signature')
            if existing is not None and existing != signature:
                raise ValueError('El lote pertenece a otro archivo o rango de consulta.')
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('signature', signature))
                self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('scope', json.dumps(scope, sort_keys=True)))
                self.db.execute("UPDATE attempts SET state='Interrumpido',finished=? WHERE state='Descargando'", (now(),))
                self.db.execute("UPDATE jobs SET state='Pendiente',token=NULL,error='Ejecución interrumpida',error_code='interrupted',updated=? WHERE state='Descargando'", (now(),))
                self.db.execute("UPDATE runs SET state='Interrumpido',finished=? WHERE state='Descargando'", (now(),))
        except BaseException:
            self.close()
            raise

    def get_metadata(self, key):
        row = self.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def prepare(self, df):
        if self.get_metadata('selection_ready'):
            return
        columns = list(df.columns)
        with self.db:
            for ordinal, values in enumerate(df.itertuples(index=False, name=None), 1):
                job = input_job(dict(zip(columns, values)), ordinal)
                payload = json.dumps(job['record'], ensure_ascii=False)
                state = 'Inválido' if job['error'] else 'Pendiente'
                self.db.execute('INSERT OR IGNORE INTO jobs(id,ordinal,payload,state,error,error_code,updated) VALUES (?,?,?,?,?,?,?)',
                    (job['key'], ordinal, payload, state, job['error'], 'invalid' if job['error'] else '', now()))
                self.db.execute('INSERT INTO inputs VALUES (?,?,?)', (ordinal, job['key'], payload))
            self.db.execute('INSERT INTO metadata VALUES (?,?)', ('selection_ready', '1'))

    def start_run(self):
        self.run_id = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO runs VALUES (?,?,NULL,?)', (self.run_id, now(), 'Descargando'))

    def pending(self, transient_only=False):
        query = "SELECT id,ordinal,payload FROM jobs WHERE state='Pendiente'"
        if transient_only:
            query += " AND error_code IN ('transient','interrupted')"
        return [(key, ordinal, json.loads(payload)) for key, ordinal, payload in self.db.execute(query + ' ORDER BY ordinal')]

    def pending_queue(self, transient_only=False):
        """Congela una ronda en SQLite; mantiene solo el BL activo de cada trabajador."""
        self.close_pending_queue()
        condition = "state='Pendiente'"
        if transient_only:
            condition += " AND error_code IN ('transient','interrupted')"
        self.db.execute('DROP TABLE IF EXISTS temp.pending_queue')
        self.db.execute('CREATE TEMP TABLE pending_queue AS SELECT id,ordinal FROM jobs WHERE ' + condition)
        self.db.commit()
        count = self.db.execute('SELECT COUNT(*) FROM pending_queue').fetchone()[0]
        cursor = self.db.execute('SELECT j.id,q.ordinal,j.payload FROM pending_queue q JOIN jobs j ON j.id=q.id ORDER BY q.ordinal')
        self._pending_cursor = cursor
        return count, ((key, ordinal, json.loads(payload)) for key, ordinal, payload in cursor)

    def close_pending_queue(self):
        if self._pending_cursor is not None:
            self._pending_cursor.close()
            self._pending_cursor = None

    def claim(self, key):
        token = uuid.uuid4().hex
        with self.db:
            cursor = self.db.execute("UPDATE jobs SET state='Descargando',attempts=attempts+1,token=?,updated=? WHERE id=? AND state='Pendiente'",
                                     (token, now(), key))
            if cursor.rowcount != 1:
                raise RuntimeError('El BL ya está reservado o guardado.')
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,?,NULL,?,?)',
                            (token, self.run_id, key, now(), 'Descargando', ''))
        return token

    def _check_token(self, key, token):
        row = self.db.execute('SELECT state,token FROM jobs WHERE id=?', (key,)).fetchone()
        if row != ('Descargando', token):
            raise RuntimeError('El intento ya no tiene una reserva válida.')

    def save(self, key, token, columns, rows):
        if not columns or len(columns) != len(set(columns)) or any(len(row) != len(columns) for row in rows):
            raise ValueError('Esquema de resultados incompatible.')
        columns = list(columns)
        with self.db:
            self._check_token(key, token)
            schema = self.get_metadata('columns')
            if schema and json.loads(schema) != columns:
                raise ValueError('El portal cambió las columnas de resultados.')
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('columns', json.dumps(columns)))
            self.db.execute('DELETE FROM results WHERE job=?', (key,))
            self.db.executemany('INSERT INTO results VALUES (?,?,?)',
                [(key, position, json.dumps(list(row), ensure_ascii=False)) for position, row in enumerate(rows, 1)])
            self.db.execute("UPDATE jobs SET state='Guardado',error='',error_code='',result_count=?,token=NULL,updated=? WHERE id=?",
                            (len(rows), now(), key))
            self.db.execute("UPDATE attempts SET state='Guardado',finished=? WHERE token=?", (now(), token))

    def fail(self, key, token, error, code='transient'):
        with self.db:
            self._check_token(key, token)
            self.db.execute("UPDATE jobs SET state='Pendiente',error=?,error_code=?,token=NULL,updated=? WHERE id=?",
                            (str(error), code, now(), key))
            self.db.execute("UPDATE attempts SET state='Pendiente',error=?,finished=? WHERE token=?", (str(error), now(), token))

    def summary(self):
        states = {state: count for state, count in self.db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state')}
        input_states = {state: count for state, count in self.db.execute('SELECT j.state,COUNT(*) FROM inputs i JOIN jobs j ON j.id=i.job GROUP BY j.state')}
        return {'total': sum(states.values()), 'saved': states.get('Guardado', 0), 'pending': states.get('Pendiente', 0),
                'running': states.get('Descargando', 0), 'invalid': states.get('Inválido', 0),
                'input_total': sum(input_states.values()), 'input_saved': input_states.get('Guardado', 0),
                'attempts': self.db.execute('SELECT COALESCE(SUM(attempts),0) FROM jobs').fetchone()[0],
                'empty_saved': self.db.execute("SELECT COUNT(*) FROM jobs WHERE state='Guardado' AND result_count=0").fetchone()[0],
                'result_rows': self.db.execute('SELECT COUNT(*) FROM results').fetchone()[0], 'database': str(self.path)}

    def finish_run(self, stopped=False, failed=False):
        summary = self.summary()
        if self.run_id:
            state = 'Error' if failed else 'Detenido' if stopped else 'Pendiente' if summary['pending'] or summary['invalid'] else 'Guardado'
            with self.db:
                self.db.execute('UPDATE runs SET state=?,finished=? WHERE id=?', (state, now(), self.run_id))
        return summary

    def cancel_running(self, error='Ejecución interrumpida'):
        with self.db:
            self.db.execute("UPDATE attempts SET state='Interrumpido',error=?,finished=? WHERE state='Descargando'",
                            (error, now()))
            self.db.execute("UPDATE jobs SET state='Pendiente',token=NULL,error=?,error_code='interrupted',updated=? WHERE state='Descargando'",
                            (error, now()))

    def progress_rows(self, limit=1000):
        return self.db.execute('SELECT ordinal,payload,state,attempts,result_count,error FROM jobs ORDER BY ordinal LIMIT ?', (limit,)).fetchall()

    def export(self, path):
        return _export_results(self.db, path)

    def export_review(self, path, empty=False):
        """Identidades originales e intentos; un vacío confirmado no es un fallo."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ['IDManifiesto', 'Secuencia Tica', 'BL original', 'Fecha Manifiesto', 'Mes']
        columns = ['Fila'] + fields + ['Estado', 'Intentos', 'Lineas guardadas', 'Codigo error', 'Ultimo error']
        condition = "j.state='Guardado' AND j.result_count=0" if empty else "j.state!='Guardado'"
        sql = ('SELECT i.ordinal,i.payload,j.state,j.attempts,j.result_count,j.error_code,j.error '
               'FROM inputs i JOIN jobs j ON j.id=i.job WHERE ' + condition + ' ORDER BY i.ordinal')
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.stem + '.', suffix='.tmp')
        count = 0
        try:
            with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(columns)
                with closing(self.db.execute(sql)) as cursor:
                    for ordinal, payload, state, attempts, lines, code, error in cursor:
                        record = json.loads(payload)
                        writer.writerow([ordinal] + [record.get(field, '') for field in fields] +
                                        [state, attempts, lines, code, error])
                        count += 1
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return count

    def close(self):
        try:
            # sqlite3.close() difiere el cierre real si queda un cursor activo.
            # La cola puede seguir referenciada por tareas canceladas o tracebacks.
            self.close_pending_queue()
            if self.db is not None:
                self.db.close()
                self.db = None
        finally:
            self.lock.close()


def _export_results(db, path):
    with closing(db.execute("SELECT value FROM metadata WHERE key='columns'")) as cursor:
        row = cursor.fetchone()
    columns = json.loads(row[0]) if row else []
    if not columns:
        return 0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.stem + '.', suffix='.tmp')
    count = 0
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            with closing(db.execute("SELECT r.data FROM inputs i JOIN jobs j ON j.id=i.job JOIN results r ON r.job=j.id WHERE j.state='Guardado' ORDER BY i.ordinal,r.position")) as cursor:
                for data, in cursor:
                    writer.writerow(json.loads(data))
                    count += 1
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return count


def export_saved(database, destination):
    """Instantánea de solo lectura; nunca recupera trabajos ni adquiere el escritor."""
    path = Path(database).resolve()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=30)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        return _export_results(db, destination)
