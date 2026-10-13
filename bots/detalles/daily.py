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

from core.job_store import JobStore, RunLock

ZONE = ZoneInfo('America/Costa_Rica')
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
          'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
SOURCE = Path(__file__).resolve().parents[2] / 'integrations' / 'duas_source'


def local_now():
    return datetime.now(ZONE)


def eligible_day(now):
    now = now.astimezone(ZONE)
    return now.date() - timedelta(days=1 if now.time() >= daytime(0, 1) else 2)


def next_midnight(now):
    now = now.astimezone(ZONE)
    wake = datetime.combine(now.date(), daytime(0, 1), ZONE)
    return wake if now < wake else wake + timedelta(days=1)


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
                    error TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS daily_duas (
                    day TEXT NOT NULL REFERENCES days(day), dua TEXT NOT NULL, PRIMARY KEY(day,dua));
                CREATE TABLE IF NOT EXISTS months (period TEXT PRIMARY KEY, table_id TEXT NOT NULL);
            ''')

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
        allowed = {'state', 'base_ready', 'table_id', 'total', 'succeeded', 'error'}
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
            completed = {row[0] for row in db.execute("SELECT day FROM days WHERE state='completed' AND day BETWEEN ? AND ?", (start.isoformat(), last.isoformat()))}
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
            result.append({'day': number, 'date': target.isoformat(), 'state': state, 'total': 0, 'succeeded': 0, 'error': '', **saved.get(target.isoformat(), {})})
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

    def snapshot(self):
        return {'active': self.active, 'phase': self.phase, 'day': self.day, 'wakeAt': self.wake,
                'tableId': self.ledger.get(date.fromisoformat(self.day)).get('table_id', '') if self.day else '',
                'startDate': self.start_date().isoformat(), 'month': self.month,
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
        driver = SOURCE / 'drivers' / 'msedgedriver.exe'
        if not self.offline and not driver.is_file():
            raise RuntimeError('Ejecuta Instalar_Base_Diaria.bat para preparar el navegador de descarga.')
        args = [sys.executable, '-u', str(SOURCE / 'worker.py'), '--day', day.isoformat(),
                '--database', str(database), '--driver', str(driver)]
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
                store = JobStore(database)
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
        with self.service.read_database(record) as db:
            for offset in range(0, len(duas), 900):
                chunk = duas[offset:offset + 900]
                marks = ','.join('?' for _ in chunk)
                success.update(row[0] for row in db.execute(f'''SELECT dua FROM jobs WHERE status='succeeded' AND dua IN ({marks})
                    UNION SELECT dua FROM retained_results WHERE dua IN ({marks})''', (*chunk, *chunk)))
        return len(success)

    def cycle(self, day):
        self.day = day.isoformat()
        self.month = day.strftime('%Y-%m')
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
        self.service.execute('run', {})
        confirmed = self.confirmed(record, duas)
        complete = confirmed == len(duas)
        self.ledger.update(day, state='completed' if complete else 'pending', succeeded=confirmed,
                           error='' if complete else 'Quedan DUAs pendientes; se retomarán automáticamente.')
        self.emit('completed' if complete else 'pending',
                  f'{day:%d/%m/%Y}: {confirmed} de {len(duas)} guardados.', refresh=True)
        return complete

    def run(self):
        start = self.start_date()
        if start >= self.now().date():
            raise ValueError('La fecha inicial debe ser anterior a hoy.')
        if not self.service.machine.get('output_base_path'):
            raise ValueError('Elige la carpeta de resultados antes de iniciar.')
        if not self.offline and not (SOURCE / 'drivers' / 'msedgedriver.exe').is_file():
            raise ValueError('Ejecuta Instalar_Base_Diaria.bat antes de iniciar el modo diario.')
        with RunLock(self.ledger.path):
            # Preserve the initial date across restarts; "yesterday" is only
            # the initial default, never an advancing cursor that skips backlog.
            if not self.service.machine.get('daily_start_date') or not self.service.machine.get('daily_mode'):
                self.service.configure({'daily_start_date': start.isoformat(), 'daily_mode': True})
            self.active = True
            try:
                while not self.service.stop_event.is_set():
                    now = self.now()
                    day = self.ledger.next_day(start, eligible_day(now))
                    if day is None:
                        wake = next_midnight(now)
                        self.emit('waiting', f'Esperando al {wake:%d/%m} a las 00:01', wake.isoformat())
                        # Re-evaluate the wall clock so clock changes do not skip days.
                        self.service.stop_event.wait(min(30, max(.1, (wake - now).total_seconds())))
                        continue
                    try:
                        complete = self.cycle(day)
                    except DownloadPending as error:
                        self.ledger.update(day, state='pending', error=str(error))
                        complete = False
                    if not complete and not self.service.stop_event.is_set():
                        wake = self.now() + timedelta(minutes=5)
                        self.emit('retrying', 'Pendientes guardados. Reintento en 5 min.', wake.isoformat())
                        self.service.stop_event.wait(300)
            except Exception as error:
                if self.day:
                    self.ledger.update(date.fromisoformat(self.day), state='pending', error=str(error))
                raise
            finally:
                self.active = False
                self.emit('stopped', 'Automático detenido; progreso guardado.')
        return {'snapshot': self.service.snapshot(), 'daily': self.snapshot(), 'runStatus': 'stopped'}
