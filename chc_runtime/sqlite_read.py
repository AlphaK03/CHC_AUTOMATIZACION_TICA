"""Opciones por conexión para lectores; no modifica archivos ni su journal."""
import time


def prepare_reader(db, max_seconds=None):
    db.execute('PRAGMA query_only=ON')
    # Compartir páginas con Windows evita pequeñas lecturas repetidas en el HDD.
    # SQLite mantiene sus bloqueos normales y cae a xRead si no admite mmap.
    db.execute('PRAGMA mmap_size=268435456')
    if max_seconds is not None:
        deadline = time.monotonic() + max_seconds
        # 1000 instrucciones pueden implicar muchas E/S lentas antes de comprobar
        # el plazo. Este lector no debe retener el COMMIT de otro proceso.
        db.set_progress_handler(lambda: time.monotonic() >= deadline, 10)
    return db
