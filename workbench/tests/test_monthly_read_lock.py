"""Un lector lento de la bitácora no retiene indefinidamente al escritor SQLite."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from threading import Event,Thread
import time
import unittest

from workbench.monthly_progress import readonly


class MonthlyReadLockTests(unittest.TestCase):
    def test_read_transaction_causes_commit_lock_then_budget_releases_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'jobs.sqlite3'
            with closing(sqlite3.connect(path,timeout=.05)) as writer:
                writer.execute('CREATE TABLE jobs(id INTEGER PRIMARY KEY,value TEXT)')
                writer.executemany('INSERT INTO jobs VALUES (?,?)',[(i,'guardado') for i in range(200)])
                writer.commit()
                # Reproducción del fallo anterior: SELECT abierto + COMMIT.
                with closing(sqlite3.connect(path)) as reader:
                    reader.execute('BEGIN');reader.execute('SELECT count(*) FROM jobs').fetchone()
                    writer.execute("UPDATE jobs SET value='nuevo' WHERE id=1")
                    with self.assertRaisesRegex(sqlite3.OperationalError,'locked'):writer.commit()
                    writer.rollback()
                ready=Event();errors=[]
                def read():
                    try:
                        with readonly(path,max_seconds=.2) as db:
                            db.execute('SELECT count(*) FROM jobs').fetchone();ready.set()
                            db.execute('SELECT sum(a.id+b.id+c.id+d.id) FROM jobs a,jobs b,jobs c,jobs d').fetchone()
                    except sqlite3.OperationalError as exc:errors.append(str(exc))
                thread=Thread(target=read);thread.start()
                try:
                    self.assertTrue(ready.wait(2))
                    writer.execute('PRAGMA busy_timeout=2000')
                    started=time.monotonic()
                    writer.execute("UPDATE jobs SET value='nuevo' WHERE id=1");writer.commit()
                    self.assertLess(time.monotonic()-started,2)
                finally:thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors,['interrupted'])
                self.assertEqual(writer.execute('SELECT value FROM jobs WHERE id=1').fetchone()[0],'nuevo')


if __name__=='__main__':unittest.main()
