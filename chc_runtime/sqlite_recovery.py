"""Recuperación de rollback pendiente al arrancar; las vistas siguen siendo de lectura."""
from contextlib import closing
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import tempfile

from .job_store import RunLock


def recover_interrupted_database(path):
    """Deja a SQLite deshacer una transacción incompleta, sin recuperar reservas.

    Solo abre para escritura ante SQLITE_READONLY_ROLLBACK y con el lote libre.
    Conserva primero la base y sus auxiliares byte a byte. No crea bases,
    migra esquemas, cambia estados ni consulta fuentes externas.
    """
    path = Path(path).resolve()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        try:
            db.execute('SELECT count(*) FROM sqlite_master').fetchone()
            return None
        except sqlite3.OperationalError as exc:
            if getattr(exc, 'sqlite_errorcode', None) != sqlite3.SQLITE_READONLY_ROLLBACK:
                raise
    lock = RunLock(path)
    try:
        lock.__enter__()
    except RuntimeError:
        # Otro motor es dueño de la recuperación y de sus reservas.
        return None
    try:
        backup_root = path.parent / 'backups'
        backup_root.mkdir(exist_ok=True)
        backup = Path(tempfile.mkdtemp(
            prefix='rollback-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-', dir=backup_root))
        for suffix in ('', '-journal', '-wal', '-shm'):
            source = Path(str(path) + suffix)
            if source.exists():
                shutil.copy2(source, backup / source.name)
        with closing(sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=10)) as db:
            # El primer SELECT hace que SQLite ejecute su rollback nativo.
            db.execute('SELECT count(*) FROM sqlite_master').fetchone()
            if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise sqlite3.DatabaseError(f'La base requiere revisión; respaldo: {backup}')
        return backup
    finally:
        lock.__exit__(None, None, None)
