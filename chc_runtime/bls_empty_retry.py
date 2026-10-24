"""Reconsulta explícita y acotada de BLs guardados sin líneas."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


def page_key(job, generations):
    generation = generations.get(job)
    return job + '@' + generation if generation else job


def generations(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='workbench_bls_generations'").fetchone():
        return {}
    return dict(db.execute('SELECT job,generation FROM workbench_bls_generations'))


def load_input(root, record):
    """Usar la entrada persistida del lote, sin regenerar ni cambiar su selección."""
    from .batch_deletion import checked_work
    work = checked_work(Path(root).resolve(), 'bls', record)
    paths = list(work.glob('**/SQLite/bls.sqlite3'))
    if len(paths) != 1 or not paths[0].resolve().is_relative_to(work):
        raise ValueError('No se encontró una única base BLs del lote seleccionado.')
    path = paths[0].resolve()
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        if db.execute("SELECT 1 FROM jobs WHERE state='Descargando' LIMIT 1").fetchone():
            raise ValueError('Primero termina o recupera la descarga de este lote.')
        empty = db.execute("SELECT count(*) FROM jobs WHERE state='Guardado' AND result_count=0").fetchone()[0]
        scope = json.loads(db.execute("SELECT value FROM metadata WHERE key='scope'").fetchone()[0])
        records = [json.loads(r[0]) for r in db.execute('SELECT payload FROM inputs ORDER BY ordinal')]
    return path, scope, records, empty


def begin(store, request):
    """Bajo el bloqueo del motor: respaldo, historial y reapertura en una transacción."""
    if store.path != Path(request['database']).resolve():
        raise ValueError('La firma o configuración no coincide con el lote seleccionado.')
    db = store.db
    condition = "state='Guardado' AND result_count=0"
    if db.execute('SELECT 1 FROM jobs j WHERE '+condition+
                  ' AND EXISTS (SELECT 1 FROM results r WHERE r.job=j.id) LIMIT 1').fetchone():
        raise ValueError('Hay un BL de 0 filas con resultados inconsistentes; se conserva para revisión.')
    count = db.execute('SELECT count(*) FROM jobs WHERE '+condition).fetchone()[0]
    if not count:
        raise ValueError('Ya no hay BLs guardados con 0 filas en este lote.')
    operation = uuid.uuid4().hex
    backup = Path(request['backups'])/(operation+'.sqlite3')
    if backup.resolve().is_relative_to(store.path.parents[3]):
        raise ValueError('El respaldo debe quedar fuera del progreso del lote.')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(backup)) as target:
        db.backup(target)
    timestamp = datetime.now(timezone.utc).isoformat()
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS workbench_empty_requeries(id TEXT PRIMARY KEY,requested TEXT NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS workbench_empty_requery_jobs(
            request TEXT NOT NULL,job TEXT NOT NULL,previous_attempts INTEGER NOT NULL,PRIMARY KEY(request,job))''')
        db.execute('CREATE TABLE IF NOT EXISTS workbench_bls_generations(job TEXT PRIMARY KEY,generation TEXT NOT NULL)')
        db.execute('INSERT INTO workbench_empty_requeries VALUES (?,?)', (operation,timestamp))
        db.execute('INSERT INTO workbench_empty_requery_jobs SELECT ?,id,attempts FROM jobs WHERE '+condition, (operation,))
        db.execute('''INSERT OR REPLACE INTO workbench_bls_generations
            SELECT job,request FROM workbench_empty_requery_jobs WHERE request=?''', (operation,))
        db.execute("""UPDATE jobs SET state='Pendiente',error='',error_code='empty_requery',token=NULL,updated=?
            WHERE id IN (SELECT job FROM workbench_empty_requery_jobs WHERE request=?)""", (timestamp,operation))

    scope_pending_queue(store,'workbench_empty_requery_jobs',operation)
    return count


def scope_pending_queue(store, table, operation):
    if table not in {'workbench_empty_requery_jobs','workbench_bls_query_jobs'}:
        raise ValueError('Selección de pendientes inválida.')
    db=store.db
    original_queue = store.pending_queue
    def pending_queue(transient_only=False):
        original_queue(transient_only)
        store.close_pending_queue()
        db.execute('DELETE FROM temp.pending_queue WHERE id NOT IN '
                   '(SELECT job FROM '+table+' WHERE request=?)', (operation,))
        db.commit()
        count = db.execute('SELECT count(*) FROM temp.pending_queue').fetchone()[0]
        cursor = db.execute('''SELECT j.id,q.ordinal,j.payload FROM temp.pending_queue q
            JOIN jobs j ON j.id=q.id ORDER BY q.ordinal''')
        store._pending_cursor = cursor
        return count, ((key,ordinal,json.loads(payload)) for key,ordinal,payload in cursor)
    store.pending_queue = pending_queue
