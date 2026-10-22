"""Consultas de XMovimientos vacías, verificadas y recuperables sin filas ficticias."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .identifiers import normalize_dua
from .job_store import atomic_output
from .movement_evidence import observe_html, verified_empty_observation


def verified_empty_html(html, dua):
    try:
        return verified_empty_observation(observe_html(html, dua), dua)
    except (AttributeError, ValueError, TypeError):
        return False


def empty_record(dua, html, evidence=''):
    if not verified_empty_html(html, dua):
        raise ValueError('No se pudo confirmar que la consulta de movimientos está vacía.')
    return {'numero_del_dua': normalize_dua(dua), 'empty': True, 'rows': [],
            'checked_at': datetime.now(timezone.utc).isoformat(), 'evidence': evidence,
            'verified_html': html}


def prepare_store(store):
    """Actualización transaccional del CHECK, con respaldo de bases antiguas."""
    db = store.db
    schema = db.execute("SELECT sql FROM sqlite_master WHERE name='jobs'").fetchone()[0]
    if "'empty'" not in schema:
        folder = Path(store.path).parent / 'backups'
        folder.mkdir(exist_ok=True)
        backup = folder / (Path(store.path).stem + '-antes-vacios-' +
                           datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
        target = sqlite3.connect(backup)
        try:
            db.backup(target)
        finally:
            target.close()
        indexes = [r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='jobs' AND sql IS NOT NULL")]
        db.execute('PRAGMA foreign_keys=OFF')
        try:
            with store.transaction():
                expanded = schema.replace('CREATE TABLE jobs', 'CREATE TABLE jobs_with_empty', 1)
                expanded = expanded.replace("'succeeded','invalid'", "'succeeded','invalid','empty'")
                if expanded == schema or "'empty'" not in expanded:
                    raise ValueError('Esquema de cola incompatible; respaldo conservado.')
                db.execute(expanded)
                db.execute('INSERT INTO jobs_with_empty (rowid,id,dua,status,attempts,run_attempts,last_error,error_kind,evidence,result) SELECT rowid,* FROM jobs')
                db.execute('DROP TABLE jobs')
                db.execute('ALTER TABLE jobs_with_empty RENAME TO jobs')
                for index in indexes:
                    db.execute(index)
                if db.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('La migración dejó referencias inválidas; se revierte.')
        finally:
            db.execute('PRAGMA foreign_keys=ON')
    with store.transaction():
        db.execute('''CREATE TABLE IF NOT EXISTS empty_observations (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            checked_at TEXT NOT NULL, evidence TEXT NOT NULL, origin TEXT NOT NULL)''')
    if store.meta('movement_empty_legacy_migrated'):
        return
    # NoRows/timeout por sí solos nunca prueban ausencia. Exigir HTML íntegro.
    candidates = db.execute("SELECT id,dua,evidence FROM jobs WHERE status IN ('retry','pending') AND error_kind='NoMovimientosError'").fetchall()
    verified = []
    for row in candidates:
        path = Path(row['evidence'])
        try:
            if not row['evidence'] or not verified_empty_html(path.read_text(encoding='utf-8'), row['dua']):
                continue
            checked = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            verified.append((row['id'], checked, str(path)))
        except (OSError, UnicodeError):
            continue
    with store.transaction():
        for key, checked, evidence in verified:
            db.execute("UPDATE jobs SET status='empty',last_error='',error_kind='' WHERE id=?", (key,))
            db.execute("INSERT OR REPLACE INTO empty_observations VALUES (?,?,?,'legacy_html')", (key, checked, evidence))
        store._set_meta(db, 'movement_empty_legacy_migrated', True)


def complete_empty(store, job, record):
    if record.get('rows') != [] or not verified_empty_html(record.get('verified_html', ''), job['dua']):
        raise ValueError('Una consulta no verificada no puede registrarse como Vacío.')
    if normalize_dua(record['numero_del_dua']) != job['dua']:
        raise ValueError('La consulta vacía no corresponde al DUA reservado.')
    with store.transaction() as db:
        store._check_claim(db, job)
        db.execute("UPDATE jobs SET status='empty',result=NULL,last_error='',error_kind='',evidence=? WHERE id=?", (record['evidence'], job['id']))
        db.execute("INSERT OR REPLACE INTO empty_observations VALUES (?,?,?,'portal')", (job['id'], record['checked_at'], record['evidence']))
        db.execute("UPDATE attempts SET outcome='empty',error='',finished=CURRENT_TIMESTAMP WHERE id=?", (job['attempt_id'],))


def queue_empty(store, ids=None):
    with store.transaction() as db:
        rows = db.execute("SELECT id,dua FROM jobs WHERE status='empty' OR (status IN ('pending','retry') AND error_kind='NoMovimientosError')").fetchall()
        selected = set(ids) if ids is not None else None
        rows = [row for row in rows if selected is None or row['id'] in selected]
        db.executemany("UPDATE jobs SET status='pending',run_attempts=0,last_error='',error_kind='' WHERE id=?", [(r['id'],) for r in rows])
        return [r['dua'] for r in rows]


def export_empty(store, paths):
    with store.lock:
        rows = [dict(row) for row in store.db.execute('''SELECT j.dua,o.checked_at,o.evidence
            FROM jobs j JOIN empty_observations o ON o.job_id=j.id WHERE j.status='empty' ORDER BY j.rowid''')]
        if 'no_rows_duas' in paths:
            with atomic_output(paths['no_rows_duas']) as stream:
                stream.writelines(row['dua'] + '\n' for row in rows)
        if 'pending_json' in paths:
            destination = Path(paths['pending_json']).with_name('vacios.json')
            with atomic_output(destination) as stream:
                json.dump({'empty': rows}, stream, ensure_ascii=False, indent=2)
