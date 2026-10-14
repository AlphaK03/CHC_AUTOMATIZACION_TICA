"""Ciclo diario de Detalles: descarga propia, acumulación mensual y calendario."""
import calendar
from contextlib import contextmanager
from datetime import date, datetime, time as daytime, timedelta
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from zoneinfo import ZoneInfo

from .job_store import JobStore, RunLock

ZONE = ZoneInfo('America/Costa_Rica')
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
          'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
SOURCE = Path(__file__).resolve().parents[1] / 'integrations' / 'duas_source'


def local_now():
    return datetime.now(ZONE)


def eligible_day(now):
    now = now.astimezone(ZONE)
    return now.date() - timedelta(days=1 if now.time() >= daytime(0, 1) else 2)


def next_midnight(now):
    now = now.astimezone(ZONE)
    wake = datetime.combine(now.date(), daytime(0, 1), ZONE)
    return wake if now < wake else wake + timedelta(days=1)


class DailyJobStore(JobStore):
    """Reserva solo los DUAs del día; el CSV mantiene todo el acumulado mensual."""
    def __init__(self, path, duas, automatic=False):
        self.automatic = automatic
        super().__init__(path)
        with self.transaction() as db:
            db.execute('CREATE TEMP TABLE daily_scope (dua TEXT PRIMARY KEY)')
            db.executemany('INSERT OR IGNORE INTO daily_scope VALUES (?)', ((dua,) for dua in duas))
            db.execute('''CREATE TABLE IF NOT EXISTS daily_automatic_attempts (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                used INTEGER NOT NULL DEFAULT 0 CHECK(used>=0))''')
            if automatic:
                # Fallos históricos también agotaron oportunidades; no repetirlos
                # indefinidamente al estrenar la actualización. Interrupciones no cuentan.
                db.execute('''INSERT OR IGNORE INTO daily_automatic_attempts
                    SELECT j.id,MIN(3,(SELECT count(*) FROM attempts a WHERE a.job_id=j.id AND a.outcome='retry'))
                    FROM jobs j WHERE EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=j.dua)''')

    def claim(self, round_number):
        with self.transaction() as db:
            row = db.execute('''SELECT id,dua FROM jobs INDEXED BY jobs_ready
                WHERE status IN ('pending','retry') AND run_attempts < ?
                AND EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua)
                AND (?=0 OR COALESCE((SELECT used FROM daily_automatic_attempts a WHERE a.job_id=jobs.id),0)<3)
                ORDER BY run_attempts, rowid LIMIT 1''', (round_number,self.automatic)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running', attempts=attempts+1, run_attempts=run_attempts+1 WHERE id=?", (row['id'],))
            attempt = db.execute('INSERT INTO attempts(job_id) VALUES (?)', (row['id'],)).lastrowid
            if self.automatic:
                db.execute('UPDATE daily_automatic_attempts SET used=used+1 WHERE job_id=?',(row['id'],))
            return {'id': row['id'], 'dua': row['dua'], 'attempt_id': attempt}

    def summary(self):
        with self.lock:
            counts = dict(self.db.execute('''SELECT status,COUNT(*) FROM jobs
                WHERE EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua) GROUP BY status''').fetchall())
            attempts = self.db.execute('''SELECT COALESCE(SUM(attempts),0) FROM jobs
                WHERE EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua)''').fetchone()[0]
            total = self.db.execute('SELECT COUNT(*) FROM daily_scope').fetchone()[0]
            active = [r[0] for r in self.db.execute("SELECT dua FROM jobs WHERE status='running' AND EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua) ORDER BY rowid LIMIT 20")]
            ready = self.db.execute('''SELECT count(*) FROM jobs WHERE status IN ('pending','retry')
                AND EXISTS (SELECT 1 FROM daily_scope s WHERE s.dua=jobs.dua)
                AND COALESCE((SELECT used FROM daily_automatic_attempts a WHERE a.job_id=jobs.id),0)<3''').fetchone()[0] if self.automatic else None
        return {**{state: counts.get(state, 0) for state in ('pending', 'running', 'retry', 'succeeded', 'invalid', 'empty')},
                'total': sum(counts.values()), 'attempts': attempts, 'source_rows': total,
                'active_duas': active, 'automatic_ready': ready}


class DailyLedger:
    def __init__(self, root):
        self.path = Path(root) / 'data' / 'daily' / 'calendar.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS days (
                    day TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'pending',
                    base_ready INTEGER NOT NULL DEFAULT 0, table_id TEXT NOT NULL DEFAULT '',
                    total INTEGER NOT NULL DEFAULT 0, succeeded INTEGER NOT NULL DEFAULT 0,
                    empty INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS daily_duas (
                    day TEXT NOT NULL REFERENCES days(day), dua TEXT NOT NULL, PRIMARY KEY(day,dua));
                CREATE TABLE IF NOT EXISTS months (period TEXT PRIMARY KEY, table_id TEXT NOT NULL);
            ''')

            if 'empty' not in {row[1] for row in db.execute('PRAGMA table_info(days)')}:
                db.execute('ALTER TABLE days ADD COLUMN empty INTEGER NOT NULL DEFAULT 0')
            if 'retry_cycles' not in {row[1] for row in db.execute('PRAGMA table_info(days)')}:
                db.execute('ALTER TABLE days ADD COLUMN retry_cycles INTEGER NOT NULL DEFAULT 0')

    @contextmanager
    def connect(self, readonly=False):
        db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True, timeout=5) if readonly else sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, day):
        with self.connect(True) as db:
            row = db.execute('SELECT * FROM days WHERE day=?', (day.isoformat(),)).fetchone()
            return dict(row) if row else {}

    def update(self, day, **values):
        allowed = {'state', 'base_ready', 'table_id', 'total', 'succeeded', 'empty', 'error', 'retry_cycles'}
        if not values.keys() <= allowed:
            raise ValueError('Campos de calendario inválidos.')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO days(day) VALUES (?)', (day.isoformat(),))
            assignments = ','.join(f'{key}=?' for key in values)
            db.execute(f'UPDATE days SET {assignments},updated=CURRENT_TIMESTAMP WHERE day=?', (*values.values(), day.isoformat()))

    def save_base(self, day, duas):
        values = list(dict.fromkeys(duas))
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO days(day) VALUES (?)', (day.isoformat(),))
            db.executemany('INSERT OR IGNORE INTO daily_duas(day,dua) VALUES (?,?)', ((day.isoformat(), dua) for dua in values))
            db.execute("UPDATE days SET base_ready=1,total=?,state='pending',error='' WHERE day=?", (len(values), day.isoformat()))

    def duas(self, day):
        with self.connect(True) as db:
            return [row[0] for row in db.execute('SELECT dua FROM daily_duas WHERE day=? ORDER BY rowid', (day.isoformat(),))]

    def next_day(self, start, last):
        with self.connect(True) as db:
            completed = {row[0] for row in db.execute("SELECT day FROM days WHERE state IN ('completed','omitted') AND day BETWEEN ? AND ?", (start.isoformat(), last.isoformat()))}
        current = start
        while current <= last:
            if current.isoformat() not in completed:
                return current
            current += timedelta(days=1)
        return None

    def month_id(self, period):
        with self.connect(True) as db:
            row = db.execute('SELECT table_id FROM months WHERE period=?', (period,)).fetchone()
            return row[0] if row else None

    def set_month(self, period, table_id):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO months VALUES (?,?)', (period, table_id))

    def month(self, period, start, now):
        year, month = map(int, period.split('-'))
        first_weekday, count = calendar.monthrange(year, month)
        with self.connect(True) as db:
            saved = {row['day']: dict(row) for row in db.execute('SELECT * FROM days WHERE day LIKE ?', (period + '-%',))}
        result = [{'day': 0, 'state': 'blank', 'date': ''} for _ in range(first_weekday)]
        for number in range(1, count + 1):
            target = date(year, month, number)
            state = 'future' if target > eligible_day(now) else 'outside' if target < start else 'pending'
            result.append({'day': number, 'date': target.isoformat(), 'state': state, 'available': target <= eligible_day(now), 'total': 0, 'succeeded': 0, 'error': '', **saved.get(target.isoformat(), {})})
            result[-1]['day'] = number
        return result


class DownloadPending(RuntimeError):
    pass


class DailyCoordinator:
    def __init__(self, service, offline=False, now=local_now):
        self.service = service
        self.offline = offline
        self.now = now
        self.ledger = DailyLedger(service.root)
        self.active = False
        self.phase = 'stopped'
        self.day = ''
        self.wake = ''
        self.month = now().strftime('%Y-%m')

    def start_date(self):
        return date.fromisoformat(self.service.machine.get('daily_start_date') or (self.now().date() - timedelta(days=1)).isoformat())

    def end_date(self):
        value = self.service.machine.get('daily_end_date')
        return date.fromisoformat(value) if value else None

    def snapshot(self):
        return {'active': self.active, 'phase': self.phase, 'day': self.day, 'wakeAt': self.wake,
                'tableId': self.ledger.get(date.fromisoformat(self.day)).get('table_id', '') if self.day else '',
                'startDate': self.start_date().isoformat(), 'endDate': self.service.machine.get('daily_end_date', ''), 'month': self.month,
                'monthLabel': f'{MONTHS[int(self.month[5:]) - 1].capitalize()} {self.month[:4]}',
                'days': self.ledger.month(self.month, self.start_date(), self.now()),
                'driverReady': (SOURCE / 'drivers' / 'msedgedriver.exe').is_file()}

    def emit(self, phase, message='', wake='', refresh=False):
        self.phase, self.wake = phase, wake
        values = {'daily': self.snapshot(), 'message': message}
        if refresh:
            values['snapshot'] = self.service.snapshot()
        self.service.protocol.emit('daily', **values)

    def download(self, day):
        database = self.service.root / 'data' / 'daily' / 'bases.sqlite3'
        if (self.service.profile['selection'] == 'importacion' and not self.offline
                and self.service.root.resolve() == self.service.profile['root'].resolve()):
            # Ambos consumidores reutilizan descargas verificadas. Sus colas,
            # calendarios y resultados siguen perteneciendo a cada bot.
            database = SOURCE / 'data' / 'importacion' / 'bases.sqlite3'
        driver = SOURCE / 'drivers' / 'msedgedriver.exe'
        if not self.offline and not driver.is_file():
            raise RuntimeError('Ejecuta Instalar_Base_Diaria.bat para preparar el navegador de descarga.')
        args = [sys.executable, '-u', str(SOURCE / 'worker.py'), '--day', day.isoformat(),
                '--database', str(database), '--driver', str(driver), '--selection', self.service.profile['selection']]
        if self.offline:
            args.append('--offline-fixture')
        elif not self.service.machine.get('headless', True):
            args.append('--visible')
        log_path = self.service.root / 'logs' / 'duas_source.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
        finished = threading.Event()
        result = None
        with log_path.open('a', encoding='utf-8') as error_log:
            child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=error_log, text=True, encoding='utf-8', env=env,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            def cancel():
                while not finished.wait(.2):
                    if self.service.stop_event.is_set():
                        try:
                            child.stdin.write('stop\n')
                            child.stdin.flush()
                        except (OSError, ValueError):
                            pass
                        return
            watcher = threading.Thread(target=cancel, daemon=False)
            watcher.start()
            try:
                for line in child.stdout:
                    event = json.loads(line)
                    if event['event'] == 'log':
                        logging.info(event['message'])
                    elif event['event'] == 'result':
                        result = event
                child.wait()
            finally:
                finished.set()
                watcher.join()
                child.stdin.close()
                child.stdout.close()
                child.wait()
        if self.service.stop_event.is_set():
            return None
        if not result or result.get('fatal'):
            raise RuntimeError((result or {}).get('message') or 'El proveedor se cerró; revisa el registro de descarga.')
        if not result.get('complete'):
            raise DownloadPending(result.get('message') or 'Quedan regímenes pendientes de descarga.')
        return result['duas']

    def append_day(self, day, duas):
        catalog = self.service.catalog
        period = day.strftime('%Y-%m')
        name = MONTHS[day.month - 1] + str(day.year)[-2:]
        known_id = self.ledger.month_id(period)
        revision = 'daily:' + day.isoformat()
        with catalog.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            record = catalog.get(known_id) if known_id else catalog.find_by_name(name)
            table_id = record['id'] if record else 'daily-' + period
            database = catalog.database(record) if record else catalog.folder / (table_id + '.sqlite3')
            with RunLock(database):
                store = self.service.Store(database)
                try:
                    if revision not in store.meta('active_revisions', []):
                        if duas:
                            store.import_values(duas, revision, append=True)
                        elif store.meta('revision') is None:
                            with store.transaction() as batch:
                                store._set_meta(batch, 'revision', revision)
                                store._set_meta(batch, 'active_revisions', [revision])
                                store._set_meta(batch, 'source_rows', 0)
                    with store.transaction() as batch:
                        store._set_meta(batch, 'catalog_managed', True)
                finally:
                    store.close()
            if not record:
                db.execute('''INSERT INTO saved_tables(id,name,name_key,filename,source_path,source_sheet,output_name)
                              VALUES (?,?,?,?,?,?,?)''',
                           (table_id, name, name.casefold(), database.name, 'daily://' + period, name, name))
        self.ledger.set_month(period, table_id)
        self.ledger.update(day, table_id=table_id)
        self.service.select(table_id)
        self.service.protocol.emit('daily', daily=self.snapshot(), snapshot=self.service.snapshot())
        return catalog.get(table_id)

    def confirmed(self, record, duas):
        success = set()
        verified = "status='succeeded'"
        if getattr(self.service, 'profile', {}).get('id') == 'xmovimientos':
            verified += " OR (status='empty' AND EXISTS (SELECT 1 FROM empty_observations o WHERE o.job_id=jobs.id))"
        with self.service.read_database(record) as db:
            for offset in range(0, len(duas), 900):
                chunk = duas[offset:offset + 900]
                marks = ','.join('?' for _ in chunk)
                success.update(row[0] for row in db.execute(f'''SELECT dua FROM jobs WHERE ({verified}) AND dua IN ({marks})
                    UNION SELECT dua FROM retained_results WHERE dua IN ({marks})''', (*chunk, *chunk)))
        return len(success)

    def empty_count(self, record, duas):
        if getattr(self.service, 'profile', {}).get('id') != 'xmovimientos':
            return 0
        found = set()
        with self.service.read_database(record) as db:
            for offset in range(0, len(duas), 900):
                chunk = duas[offset:offset+900]
                marks = ','.join('?' for _ in chunk)
                found.update(row[0] for row in db.execute(f"SELECT dua FROM jobs WHERE status='empty' AND dua IN ({marks})", chunk))
        return len(found)

    def reopen(self, duas):
        with self.ledger.connect() as db:
            for offset in range(0, len(duas), 900):
                chunk = duas[offset:offset+900]
                marks = ','.join('?' for _ in chunk)
                db.execute(f"UPDATE days SET state='pending',error='' WHERE state='completed' AND day IN (SELECT day FROM daily_duas WHERE dua IN ({marks}))", chunk)

    def reconcile(self, record):
        with self.ledger.connect(True) as db:
            days = [date.fromisoformat(row[0]) for row in db.execute('SELECT day FROM days WHERE table_id=? AND base_ready=1', (record['id'],))]
        for day in days:
            duas = self.ledger.duas(day)
            confirmed = self.confirmed(record, duas)
            empty = self.empty_count(record, duas)
            complete = confirmed == len(duas) == self.ledger.get(day)['total']
            previous = self.ledger.get(day)['state']
            self.ledger.update(day, state='completed' if complete else 'omitted' if previous=='omitted' else 'pending', succeeded=confirmed-empty, empty=empty,
                               error='' if complete else 'Pendientes omitidos del automático; requieren un reintento manual.' if previous=='omitted' else 'Quedan DUAs pendientes; se retomarán automáticamente.')

    def reset_manual_range(self, start, end):
        """Una acción explícita concede tres oportunidades nuevas, sin tocar resultados."""
        with self.ledger.connect() as db:
            db.execute("UPDATE days SET state='pending',retry_cycles=0,error='' WHERE day BETWEEN ? AND ? AND state!='completed'",(start.isoformat(),end.isoformat()))
            tables = [row[0] for row in db.execute("SELECT DISTINCT table_id FROM days WHERE day BETWEEN ? AND ? AND table_id!=''",(start.isoformat(),end.isoformat()))]
            duas = [row[0] for row in db.execute('SELECT DISTINCT dua FROM daily_duas WHERE day BETWEEN ? AND ?',(start.isoformat(),end.isoformat()))]
        for table_id in tables:
            record = self.service.catalog.get(table_id)
            with RunLock(self.service.catalog.database(record)):
                store = self.service.Store(self.service.catalog.database(record))
                try:
                    with store.transaction() as db:
                        db.execute('''CREATE TABLE IF NOT EXISTS daily_automatic_attempts (
                            job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                            used INTEGER NOT NULL DEFAULT 0 CHECK(used>=0))''')
                        for offset in range(0,len(duas),900):
                            chunk=duas[offset:offset+900];marks=','.join('?' for _ in chunk)
                            db.execute(f"INSERT OR REPLACE INTO daily_automatic_attempts SELECT id,0 FROM jobs WHERE dua IN ({marks}) AND status IN ('pending','retry')",chunk)
                finally:store.close()

    def cycle(self, day):
        self.day = day.isoformat()
        self.month = day.strftime('%Y-%m')
        self.ledger.update(day,retry_cycles=self.ledger.get(day).get('retry_cycles',0)+1)
        if not self.ledger.get(day).get('base_ready'):
            self.ledger.update(day, state='downloading', error='')
            self.emit('downloading', 'Descargando base del ' + day.strftime('%d/%m/%Y'))
            duas = self.download(day)
            if duas is None:
                self.ledger.update(day, state='pending', error='Descarga detenida.')
                return False
            self.ledger.save_base(day, duas)
        duas = self.ledger.duas(day)
        record = self.append_day(day, duas)
        if self.service.stop_event.is_set():
            return False
        self.ledger.update(day, state='processing', error='')
        self.emit('processing', 'Procesando el ' + day.strftime('%d/%m/%Y'))
        self.service.execute('run', {'daily_duas': duas, 'daily_automatic':True})
        confirmed = self.confirmed(record, duas)
        complete = confirmed == len(duas)
        # La descarga usa tres rondas acotadas; si quedan fallos se dejan al usuario.
        omitted = not complete and not self.service.stop_event.is_set()
        state = 'completed' if complete else 'omitted' if omitted else 'pending'
        self.ledger.update(day, state=state, succeeded=confirmed-self.empty_count(record, duas),
                           empty=self.empty_count(record, duas),
                           error='' if complete else 'Pendientes omitidos del automático; puedes reintentar el día o el mes manualmente.' if omitted else 'Descarga detenida; progreso conservado.')
        self.emit(state,
                  f'{day:%d/%m/%Y}: {confirmed} de {len(duas)} consultados.', refresh=True)
        return complete

    def run(self, start=None, end=None, manual=False):
        start = start or self.start_date()
        end = end if manual else self.end_date()
        if start >= self.now().date():
            raise ValueError('La fecha inicial debe ser anterior a hoy.')
        if end and (end < start or end >= self.now().date()):
            raise ValueError('El rango debe terminar entre Desde y ayer.')
        if not self.service.machine.get('output_base_path'):
            raise ValueError('Elige la carpeta de resultados antes de iniciar.')
        if not self.offline and not (SOURCE / 'drivers' / 'msedgedriver.exe').is_file():
            raise ValueError('Ejecuta Instalar_Base_Diaria.bat antes de iniciar el modo diario.')
        with RunLock(self.ledger.path):
            if manual:self.reset_manual_range(start,end)
            # Preserve the initial date across restarts; "yesterday" is only
            # the initial default, never an advancing cursor that skips backlog.
            if not manual and (not self.service.machine.get('daily_start_date') or not self.service.machine.get('daily_mode')):
                self.service.configure({'daily_start_date': start.isoformat(), 'daily_mode': True})
            self.active = True
            finished = False
            try:
                while not self.service.stop_event.is_set():
                    now = self.now()
                    last = min(end, eligible_day(now)) if end else eligible_day(now)
                    day = self.ledger.next_day(start, last)
                    if day is None:
                        if end and end <= eligible_day(now):
                            finished = True
                            break
                        wake = next_midnight(now)
                        self.emit('waiting', f'Esperando al {wake:%d/%m} a las 00:01', wake.isoformat())
                        # Re-evaluate the wall clock so clock changes do not skip days.
                        self.service.stop_event.wait(min(30, max(.1, (wake - now).total_seconds())))
                        continue
                    try:
                        complete = self.cycle(day)
                    except DownloadPending as error:
                        cycles = self.ledger.get(day).get('retry_cycles',0)
                        self.ledger.update(day, state='omitted' if cycles>=3 else 'pending', error=str(error))
                        complete = False
                    if not complete and not self.service.stop_event.is_set() and self.ledger.get(day)['state']!='omitted':
                        self.emit('retrying', 'Reintentando la base pendiente; máximo tres intentos.')
                        self.service.stop_event.wait(min(2**self.ledger.get(day).get('retry_cycles',1),5))
            except Exception as error:
                if self.day:
                    self.ledger.update(date.fromisoformat(self.day), state='pending', error=str(error))
                raise
            finally:
                self.active = False
                with self.ledger.connect(True) as db:
                    omitted=db.execute("SELECT count(*) FROM days WHERE state='omitted' AND day BETWEEN ? AND ?",(start.isoformat(),(end or eligible_day(self.now())).isoformat())).fetchone()[0]
                self.emit('finished_with_pending' if finished and omitted else 'completed' if finished else 'stopped',
                          f'Rango revisado; {omitted} días con pendientes para reintentar manualmente.' if finished and omitted else 'Rango completado; resultados guardados.' if finished else 'Automático detenido; progreso guardado.')
        return {'snapshot': self.service.snapshot(), 'daily': self.snapshot(), 'runStatus': 'pending' if finished and omitted else 'completed' if finished else 'stopped'}
