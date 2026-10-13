"""Cola durable y control de un único escritor para conocimientos."""
import json
import os
import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class OutputLock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0, 2)
                if self.file.tell() == 0:
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuntimeError('Esta salida ya está siendo utilizada por otra ejecución.') from exc

    def close(self):
        if not self.file.closed:
            self.file.close()  # El sistema libera el bloqueo también si el proceso muere.


class QueueStore:
    def initialize_queue(self):
        self.run_id = None
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS selection (id INTEGER PRIMARY KEY CHECK(id=1));
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL,
                source_ordinal INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'Pendiente'
                    CHECK(state IN ('Pendiente','Descargando','Guardado','Excluido')),
                attempts INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
                pages INTEGER NOT NULL DEFAULT 0, read_count INTEGER NOT NULL DEFAULT 0,
                kept_count INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, started TEXT NOT NULL, finished TEXT,
                state TEXT NOT NULL, selected INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (
                run_id TEXT NOT NULL, manifest TEXT NOT NULL, started TEXT NOT NULL,
                finished TEXT, state TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(run_id, manifest));
            CREATE TABLE IF NOT EXISTS identity_changes (
                old_id TEXT NOT NULL, new_id TEXT NOT NULL, changed TEXT NOT NULL,
                reason TEXT NOT NULL, PRIMARY KEY(old_id,new_id));
        ''')
        self._migrate_excluded_state()

    def _migrate_excluded_state(self):
        """Amplía el CHECK de bases anteriores sin modificar sus trabajos/historial."""
        schema = self.db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()[0]
        if "'Excluido'" in schema:
            return
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('''CREATE TABLE jobs_with_exclusions (
                id TEXT PRIMARY KEY, ordinal INTEGER NOT NULL,
                source_ordinal INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'Pendiente'
                    CHECK(state IN ('Pendiente','Descargando','Guardado','Excluido')),
                attempts INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
                pages INTEGER NOT NULL DEFAULT 0, read_count INTEGER NOT NULL DEFAULT 0,
                kept_count INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL)''')
            columns = 'id,ordinal,source_ordinal,state,attempts,error,pages,read_count,kept_count,updated'
            self.db.execute(f'INSERT INTO jobs_with_exclusions ({columns}) SELECT {columns} FROM jobs')
            self.db.execute('DROP TABLE jobs')
            self.db.execute('ALTER TABLE jobs_with_exclusions RENAME TO jobs')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def prepare_selection(self, jobs):
        """Congela las filas seleccionadas; reanudar no incorpora ni pierde filas."""
        if self.db.execute('SELECT 1 FROM selection').fetchone():
            return
        with self.db:
            for position, (source_ordinal, href, info, mid) in enumerate(jobs, 1):
                completed = self.db.execute('SELECT stats FROM manifests WHERE id=?', (mid,)).fetchone()
                failure = self.db.execute('SELECT reason FROM failures WHERE id=?', (mid,)).fetchone()
                stats = json.loads(completed[0]) if completed else {}
                self.db.execute('''INSERT INTO jobs
                    (id,ordinal,source_ordinal,state,error,pages,read_count,kept_count,updated)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (mid, position, source_ordinal, 'Guardado' if completed else 'Pendiente',
                     failure[0] if failure else '', stats.get('pages', 0),
                     stats.get('read', 0), stats.get('kept', 0), now()))
            self.db.execute('INSERT INTO selection VALUES (1)')

    def selection_ready(self):
        return self.db.execute('SELECT 1 FROM selection').fetchone() is not None

    def reconcile_identities(self, corrections, canonical_ids):
        """Repara solo pendientes inequívocos; conserva fila e historial de intentos."""
        changed = []
        with self.db:
            for old, new, source_ordinal in corrections:
                if old in canonical_ids or sum(c[0] == old for c in corrections) != 1:
                    continue
                job = self.db.execute('SELECT state,source_ordinal,error FROM jobs WHERE id=?', (old,)).fetchone()
                if not job or job[0] != 'Pendiente' or self.completed(old):
                    continue
                exact_error = f'Manifiesto inesperado: {new}; esperado {old}'
                if job[1] != source_ordinal and job[2] != exact_error:
                    continue
                if self.db.execute('SELECT 1 FROM jobs WHERE id=?', (new,)).fetchone():
                    continue
                if self.db.execute('SELECT 1 FROM rows WHERE manifest=?', (old,)).fetchone():
                    continue
                reason = 'Identificador corregido usando Grid1ContainerDataV; se conserva la fila y sus intentos.'
                self.db.execute('INSERT OR IGNORE INTO identity_changes VALUES (?,?,?,?)', (old, new, now(), reason))
                self.db.execute('UPDATE jobs SET id=?,error=?,updated=? WHERE id=?', (new, reason, now(), old))
                self.db.execute('UPDATE failures SET id=? WHERE id=?', (new, old))
                self.db.execute('UPDATE attempts SET manifest=? WHERE manifest=?', (new, old))
                changed.append((old, new))
        return changed

    def jobs(self):
        keys = ['id', 'ordinal', 'source_ordinal', 'state', 'attempts', 'error',
                'pages', 'read', 'kept', 'updated']
        return [dict(zip(keys, row)) for row in self.db.execute('''SELECT
            id,ordinal,source_ordinal,state,attempts,error,pages,read_count,kept_count,updated
            FROM jobs ORDER BY ordinal,id''')]

    def job(self, mid):
        keys = ['id', 'ordinal', 'source_ordinal', 'state', 'attempts', 'error',
                'pages', 'read', 'kept', 'updated']
        row = self.db.execute('''SELECT id,ordinal,source_ordinal,state,attempts,error,
            pages,read_count,kept_count,updated FROM jobs WHERE id=?''', (mid,)).fetchone()
        if row is None:
            raise KeyError(mid)
        return dict(zip(keys, row))

    def start_run(self):
        self.interrupt('Ejecución anterior interrumpida; pendiente de reintento.')
        self.run_id = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO runs VALUES (?,?,NULL,?,?)',
                            (self.run_id, now(), 'En curso', len(self.jobs())))
        return self.run_id

    def claim(self, mid):
        with self.db:
            changed = self.db.execute('''UPDATE jobs SET state='Descargando',
                attempts=attempts+1,error='',pages=0,read_count=0,kept_count=0,updated=?
                WHERE id=? AND state='Pendiente' ''', (now(), mid)).rowcount
            if changed != 1:
                raise RuntimeError(f'La fila no está pendiente: {mid}')
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,NULL,?,?)',
                            (self.run_id, mid, now(), 'Descargando', ''))

    def page_progress(self, mid, stats):
        with self.db:
            self.db.execute('''UPDATE jobs SET pages=?,read_count=?,kept_count=?,updated=?
                WHERE id=? AND state='Descargando' ''',
                (stats['pages'], stats['read'], stats['kept'], now(), mid))

    def activity(self, mid, message):
        with self.db:
            self.db.execute("UPDATE jobs SET error=?,updated=? WHERE id=? AND state='Descargando'",
                            (message, now(), mid))

    def record_outcome(self, mid, state, error='', stats=None):
        """Se ejecuta dentro de la misma transacción que guarda datos o fallo."""
        stats = stats or {}
        self.db.execute('''UPDATE jobs SET state=?,error=?,updated=?,
            pages=COALESCE(?,pages),read_count=COALESCE(?,read_count),
            kept_count=COALESCE(?,kept_count) WHERE id=?''',
            (state, error, now(), stats.get('pages'), stats.get('read'), stats.get('kept'), mid))
        if self.run_id:
            self.db.execute('''UPDATE attempts SET finished=?,state=?,error=?
                WHERE run_id=? AND manifest=?''', (now(), state, error, self.run_id, mid))

    def progress(self):
        counts = dict(self.db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state'))
        processed = self.db.execute('''SELECT COUNT(*) FROM attempts
            WHERE run_id=? AND finished IS NOT NULL''', (self.run_id,)).fetchone()[0]
        failed_run = self.db.execute('''SELECT COUNT(*) FROM attempts
            WHERE run_id=? AND finished IS NOT NULL AND state='Pendiente' ''', (self.run_id,)).fetchone()[0]
        return {'selected': sum(counts.values()), 'saved': counts.get('Guardado', 0),
                'excluded': counts.get('Excluido', 0),
                'pending': counts.get('Pendiente', 0), 'active': counts.get('Descargando', 0),
                'processed_run': processed,
                'accounted': counts.get('Guardado', 0) + counts.get('Excluido', 0) + failed_run}

    def finish_run(self, expected_attempts):
        totals = self.progress()
        if totals['active'] or totals['processed_run'] != expected_attempts:
            raise RuntimeError(f'Contabilidad incompleta de la ejecución: {totals}')
        if totals['selected'] != totals['saved'] + totals['pending'] + totals['excluded']:
            raise RuntimeError(f'Faltan filas por contabilizar: {totals}')
        with self.db:
            self.db.execute('UPDATE runs SET finished=?,state=? WHERE id=?',
                            (now(), 'Finalizada con pendientes' if totals['pending'] else
                             'Finalizada con exclusiones' if totals['excluded'] else 'Finalizada', self.run_id))
        return totals

    def interrupt(self, reason):
        with self.db:
            active = list(self.db.execute("SELECT id,source_ordinal FROM jobs WHERE state='Descargando'"))
            for mid, ordinal in active:
                self.db.execute('INSERT OR REPLACE INTO failures VALUES (?,?,?)', (mid, ordinal, reason))
            self.db.execute("UPDATE jobs SET state='Pendiente',error=?,updated=? WHERE state='Descargando'", (reason, now()))
            self.db.execute("UPDATE attempts SET finished=?,state='Pendiente',error=? WHERE finished IS NULL", (now(), reason))
            self.db.execute("UPDATE runs SET finished=?,state='Interrumpida' WHERE finished IS NULL", (now(),))
