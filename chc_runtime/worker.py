"""Servicio JSONL común: perfiles de extracción aislados, sin Tk ni Qt."""
import argparse
from contextlib import contextmanager, nullcontext
from .activity import ActivityReporter, COMMANDS
import json
import logging
import os
from pathlib import Path
from . import output_layout
import re
import sqlite3
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1] / 'bots' / 'detalles'
SHUTDOWN_GRACE_SECONDS = 30

from .catalog import TableCatalog, table_name
from .captcha import load_captcha_lookup
from .job_store import JobStore, RunLock, active_revisions
from .sqlite_recovery import recover_interrupted_database
from .messages import pending_reason
from .playwright_processor import PlaywrightDUAProcessor
from .profiles import load_profile
from .daily import DailyCoordinator, DailyJobStore, local_now
from . import utils
from .sqlite_read import prepare_reader


class Protocol:
    def __init__(self):
        self.lock = threading.Lock()

    def emit(self, event, **data):
        with self.lock:
            sys.stdout.write(json.dumps({'event': event, **data}, ensure_ascii=False, allow_nan=False) + '\n')
            sys.stdout.flush()


class EventLog(logging.Handler):
    def __init__(self, protocol):
        super().__init__()
        self.protocol = protocol

    def emit(self, record):
        if not getattr(record, 'technical_only', False):
            self.protocol.emit('log', message=record.getMessage(), level=getattr(record, 'tag', record.levelname),
                               time=time.strftime('%H:%M:%S'))


class DetailsService:
    def __init__(self, storage_root, protocol, offline=False, module_id="detalles"):
        self.module_id=module_id
        self.profile = load_profile(module_id)
        self.Store = self.profile["store"]
        self.Processor = self.profile["processor"]
        self.flow = self.profile["flow"]()
        self.ScopedStore = DailyJobStore if self.Store is JobStore else type("ScopedTransitStore", (DailyJobStore, self.Store), {})
        self.root = Path(storage_root).resolve()
        self.protocol = protocol
        # Conserva estructura y formatos del bot; --storage-root aísla pruebas.
        utils._BASE_DIR = str(self.root)
        utils._CONFIG_DIR = str(self.root / 'config')
        utils._MACHINE_PATH = str(self.root / 'config' / 'machine.json')
        utils._SESSION_PATH = str(self.root / 'config' / 'session.json')
        self.machine = utils.load_machine_config()
        self.session = utils.load_session()
        self.catalog = TableCatalog(self.root / 'data' / 'queues', store_factory=self.Store)
        self.catalog.discover_legacy()
        # Recuperar el journal de un cierre abrupto antes de las vistas mode=ro.
        # No abrir JobStore ni rearmar trabajos al cargar el panel.
        recovered = []
        for table in self.catalog.list_tables():
            backup = recover_interrupted_database(self.catalog.database(table))
            if backup:
                recovered.append((table['name'], backup))
        if getattr(self.Store, 'supports_empty', False):
            for table in self.catalog.list_tables():
                path = self.catalog.database(table)
                try:
                    with RunLock(path):
                        store = self.Store(path)
                        store.close()
                except RuntimeError as exc:
                    # Una instancia ocupada conserva sus reservas y su bloqueo.
                    if 'ya está siendo procesado' in str(exc):
                        continue
                    raise
        self.fields = list(self.profile['fields'])
        self.captcha = load_captcha_lookup(self.profile['root'] / 'config/captcha_lookup.json')
        self.stop_event = threading.Event()
        self.active_id = self.session.get('active_table_id', '')
        self.daily = DailyCoordinator(self, offline=offline)
        if getattr(self.Store, 'supports_empty', False):
            for table in self.catalog.list_tables():
                try:
                    with RunLock(self.catalog.database(table)):
                        self.daily.reconcile(table)
                except RuntimeError as exc:
                    if 'ya está siendo procesado' in str(exc):
                        continue
                    raise
        if not self.active_id and self.session.get('input_file_path') and self.session.get('sheet_name'):
            self.active_id = utils.dataset_key(self.session['input_file_path'], self.session['sheet_name'])
        try:
            self.catalog.get(self.active_id)
        except (ValueError, OSError):
            self.active_id = ''
        utils.setup_logging(str(self.root / 'logs' / 'workbench.log'))
        logging.getLogger().addHandler(EventLog(protocol))
        for name, backup in recovered:
            logging.warning('Transacción interrumpida recuperada en «%s». Respaldo: %s', name, backup)

    @contextmanager
    def read_database(self, record):
        db = sqlite3.connect(self.catalog.database(record).as_uri() + '?mode=ro', uri=True, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            prepare_reader(db,10)
            yield db
        finally:
            db.close()

    def summary(self, record):
        if not record:
            return {state: 0 for state in ('pending', 'running', 'retry', 'succeeded', 'invalid', 'empty', 'total', 'attempts', 'source_rows', 'retained')}
        # Instantánea de solo lectura: nunca recupera ni modifica reservas ajenas.
        with self.read_database(record) as db:
            revisions = active_revisions(db)
            marks = ','.join('?' for _ in revisions)
            counts = dict(db.execute(f'''SELECT status, COUNT(*) FROM jobs WHERE status!='invalid'
                OR EXISTS (SELECT 1 FROM source_rows s WHERE s.job_id=jobs.id AND s.revision IN ({marks}))
                GROUP BY status''', revisions).fetchall())
            source = db.execute("SELECT value FROM metadata WHERE key='source_rows'").fetchone()
            attempts = db.execute('SELECT COALESCE(SUM(attempts),0) FROM jobs').fetchone()[0]
            retained = db.execute('SELECT COUNT(*) FROM retained_results').fetchone()[0]
            unverified = db.execute("SELECT count(*) FROM jobs WHERE status IN ('pending','retry') AND error_kind='NoMovimientosError'").fetchone()[0] if getattr(self.Store,'supports_empty',False) else 0
        return {**{state: counts.get(state, 0) for state in ('pending', 'running', 'retry', 'succeeded', 'invalid', 'empty')},
                'total': sum(counts.values()), 'attempts': attempts,
                'source_rows': json.loads(source[0]) if source else 0, 'retained': retained, 'empty_unverified': unverified}

    def record(self):
        return self.catalog.get(self.active_id) if self.active_id else None

    def paths(self, record=None):
        record = record or self.record()
        base = self.local_root()
        if not record:
            raise ValueError('Importa o abre una tabla guardada.')
        name = self.output_name(record['name'])
        for other in self.catalog.list_tables():
            if other['id'] != record['id'] and self.output_name(other['name']).casefold() == name.casefold():
                raise ValueError('Dos tablas producen el mismo nombre de carpeta. Renombra una antes de exportar.')
        spec=output_layout.dua_spec(self.module_id,record)
        folder=Path(base).joinpath(*spec['relativeFolders'])
        internal = self.root / 'data' / 'exports' / record['id']
        folder.mkdir(parents=True, exist_ok=True)
        internal.mkdir(parents=True, exist_ok=True)
        return {
            'output_csv': str(internal / 'resultados.csv'),
            'processed_log': str(internal / 'procesados.txt'),
            'failed_duas': str(internal / 'pendientes.txt'),
            'pending_json': str(internal / 'pendientes.json'),
            'diagnostics': str(internal / 'diagnosticos'),
            'no_rows_duas': str(internal / 'sin_filas.txt'),
        }

    def published(self, record, paths):
        path = Path(paths['output_csv'])
        if path.is_file():
            module=self.module_id
            spec=output_layout.dua_spec(module,record)
            result=output_layout.publish(path,self.local_root(),spec,module+':'+record['id'],output_layout.registry_path(self.root))
            if result:self.protocol.emit('published',**result)

    def local_root(self):
        return output_layout.local_root(self.root,self.machine.get('output_base_path',''))

    @staticmethod
    def output_name(name):
        # Preserve the chosen name, including spaces and accents. Replace only
        # characters Windows cannot use in a directory or file name.
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .') or 'Tabla'
        if safe.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *{f'COM{i}' for i in range(1, 10)}, *{f'LPT{i}' for i in range(1, 10)}}:
            safe = '_' + safe
        return safe

    def select(self, table_id):
        record = self.catalog.get(table_id)
        self.active_id = record['id']
        self.session.update(active_table_id=record['id'], input_file_path=record['source_path'], sheet_name=record['source_sheet'])
        utils.save_session(self.session)

    def snapshot(self):
        try:
            record = self.record()
        except (ValueError, OSError):
            self.active_id = ''
            self.session['active_table_id'] = ''
            utils.save_session(self.session)
            record = None
        tables = self.catalog.list_tables()
        for item in tables:
            try:
                item['summary'] = self.summary(item)
            except (OSError, sqlite3.Error):
                item['summary'] = self.summary(None)
                item['unavailable'] = True
        # Reutilizar únicamente la lectura de ESTA instantánea. La siguiente
        # petición vuelve a consultar SQLite y ve resultados nuevos de inmediato.
        active_summary = next((dict(item['summary']) for item in tables
                               if record and item['id']==record['id'] and not item.get('unavailable')), None)
        if active_summary is None:
            active_summary = self.summary(record)
        return {'tables': tables, 'activeTable': record or {}, 'summary': active_summary,
                'config': {**self.machine,'output_base_path':str(self.local_root())}, 'session': self.session, 'fields': self.fields, 'daily': self.daily.snapshot(),
                'storageRoot': str(self.root),
                'outputFolder': str(self.local_root().joinpath(*output_layout.dua_spec(self.module_id,record)['relativeFolders'])) if record else ''}

    def runtime(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = Path(playwright.chromium.executable_path)
        return {'chromiumReady': browser.is_file(), 'chromiumPath': str(browser), 'captchaEntries': len(self.captcha)}

    def configure(self, values):
        updated = dict(self.machine)
        for key, low, high in [('cant_hilos', 1, 20), ('timeout', 5, 120), ('max_retries', 1, 10)]:
            value = values.get(key, updated.get(key, {'cant_hilos': 1, 'timeout': 30, 'max_retries': 3}[key]))
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f'Valor inválido para {key}: debe estar entre {low} y {high}.')
            updated[key] = value
        for key in ('headless', 'dark_mode', 'reuse_context', 'lightweight_details', 'daily_mode'):
            if key in values:
                if not isinstance(values[key], bool):
                    raise ValueError(f'Valor inválido para {key}.')
                updated[key] = values[key]
        if 'output_base_path' in values:
            updated['output_base_path'] = str(values['output_base_path']).strip()
            if updated['output_base_path']:output_layout.set_local_root(updated['output_base_path'],self.root)
        if 'daily_start_date' in values:
            from datetime import date
            start = date.fromisoformat(str(values['daily_start_date']))
            if start >= local_now().date():
                raise ValueError('La fecha inicial debe ser anterior a hoy.')
            updated['daily_start_date'] = start.isoformat()
        if 'daily_end_date' in values:
            updated['daily_end_date'] = str(values['daily_end_date']).strip()
        if updated.get('daily_end_date'):
            from datetime import date, timedelta
            end = date.fromisoformat(updated['daily_end_date'])
            start = date.fromisoformat(updated.get('daily_start_date') or (local_now().date() - timedelta(days=1)).isoformat())
            if end < start or end >= local_now().date():
                raise ValueError('Hasta debe ser igual o posterior a Desde y anterior a hoy.')
        utils.save_machine_config(updated)
        self.machine = updated

    def view(self, request):
        record = self.record()
        if not record:
            return {'rows': [], 'total': 0, 'offset': 0}
        offset = max(0, int(request.get('offset', 0)))
        total, rows = self.catalog.read_rows(record['id'], request.get('filter', 'all'), str(request.get('search', '')),
                                             offset=offset, limit=100)
        for row in rows:
            row['reason'] = ('Resultado guardado.' if row['status'] == 'succeeded' else
                             'Vacío: sin movimientos en la última consulta. Se puede reintentar.' if row['status'] == 'empty' else
                             'Consulta en curso.' if row['status'] == 'running' else
                             'Listo para consultar.' if row['status'] == 'pending' and not row['last_error'] else
                             pending_reason(row['error_kind'], row['last_error']))
            if row.get('autoOmitted'):
                row['reason'] = 'Omitido del automático tras tres intentos. ' + row['reason']
        return {'rows': rows, 'total': total, 'offset': offset}

    def detail(self, job_id):
        record = self.record()
        if not record:
            raise ValueError('No hay tabla activa.')
        with self.read_database(record) as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise ValueError('La fila ya no existe.')
            sources = [dict(item) for item in db.execute('SELECT revision,row_number,raw FROM source_rows WHERE job_id=?', (job_id,))]
            has_empty = getattr(self.Store, 'supports_empty', False) and db.execute("SELECT 1 FROM sqlite_master WHERE name='empty_observations'").fetchone()
            observed = db.execute('SELECT checked_at FROM empty_observations WHERE job_id=?', (job_id,)).fetchone() if has_empty else None
            attempts = [dict(item) for item in db.execute('SELECT started,finished,outcome,error FROM attempts WHERE job_id=? ORDER BY id DESC LIMIT 100', (job_id,))]
        result = json.loads(row['result']) if row['result'] else {}
        evidence = row['evidence']
        if evidence and not Path(evidence).is_file():
            archived = self.root / 'data' / 'exports' / record['id'] / 'legacy-output' / 'diagnosticos' / Path(evidence).name
            if archived.is_file():
                evidence = str(archived)
        return {**dict(row), 'result': result, 'sources': sources, 'attemptHistory': attempts,
                'evidence': evidence, 'emptyCheckedAt': observed[0] if observed else '',
                'values': [{'field': name, 'value': str(result.get(name, ''))} for name in self.fields],
                'resultRows': result.get('rows', []),
                'reason': 'Resultado guardado.' if result else 'Vacío: sin movimientos en la última consulta. Se puede reintentar.' if row['status'] == 'empty' else
                             'Consulta en curso.' if row['status'] == 'running' else
                          pending_reason(row['error_kind'], row['last_error']) if row['last_error'] else 'Listo para consultar.'}

    def execute(self, command, request):
        if command == 'daily_calendar':
            month = str(request.get('month') or self.daily.month)
            if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month) or not 1 <= int(month[:4]) <= 9999:
                raise ValueError('Mes inválido.')
            self.daily.month = month
            return {'daily': self.daily.snapshot()}
        if command == 'daily_run':
            return self.daily.run(bounded=request.get('bounded') is True)
        if command in {'retry_month','retry_day'}:
            from datetime import date
            import calendar
            if command=='retry_day':
                start=end=date.fromisoformat(request['day'])
            else:
                period=str(request['month'])
                if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',period):raise ValueError('Mes inválido.')
                year,month=map(int,period.split('-'))
                start=date(year,month,1)
                from .daily import eligible_day
                end=min(date(year,month,calendar.monthrange(year,month)[1]),eligible_day(local_now()))
            if end<start:raise ValueError('El período no tiene días disponibles para consultar.')
            return self.daily.run(start,end,manual=True)
        if command == 'initialize':
            return {'snapshot': self.snapshot(), 'runtime': self.runtime(), 'view': self.view({})}
        if command == 'inspect_excel':
            from openpyxl import load_workbook
            source = Path(request['path']).resolve()
            book = load_workbook(source, read_only=True)
            try:
                sheets = book.sheetnames
            finally:
                book.close()
            return {'fileInfo': {'path': str(source), 'sheets': sheets}}
        if command == 'prepare_import':
            name = table_name(request['name'])
            target = self.catalog.find_by_name(name)
            return {'importPlan': {'name': name, 'targetId': target['id'] if target else None,
                                   'source': request['source'], 'sheet': request['sheet'], 'appended': bool(target)}}
        if command == 'import':
            if 'targetId' not in request:
                raise ValueError('Confirma la tabla de destino antes de importar.')
            source, sheet, name = request['source'], request['sheet'], request['name']
            base = self.machine.get('output_base_path', '')
            legacy = Path(base) / sheet / self.profile['legacy'].format(sheet=sheet) if base else None
            record = self.catalog.import_excel(source, sheet, name, legacy, self.fields, expected_target=request['targetId'])
            self.select(record['id'])
            report = record['import_summary']
            logging.info('Tabla «%s»: %s DUAs nuevos, %s existentes y %s entradas para revisar.', name, report['added'], report['existing'], report['invalid'])
            return {'snapshot': self.snapshot(), 'view': self.view(request.get('viewQuery', {})), 'importSummary': report}
        if command == 'select':
            self.select(request['tableId'])
        elif command == 'configure':
            self.configure(request['config'])
        elif command == 'view':
            return {'view': self.view(request)}
        elif command == 'detail':
            return {'detail': self.detail(request['jobId'])}
        elif command == 'rename':
            self.catalog.rename(self.active_id, request['name'])
        elif command in {'remove_rows', 'clean', 'delete'}:
            if request.get('confirmTableId') != self.active_id or not self.active_id:
                raise ValueError('La tabla seleccionada cambió. Confirma de nuevo la operación.')
            if request.get('confirmation') != 'BORRAR':
                raise ValueError('Escribe exactamente BORRAR para confirmar.')
            if command == 'delete':
                backup = self.catalog.delete_table(self.active_id)
                self.active_id = ''
                self.session['active_table_id'] = ''
                utils.save_session(self.session)
            else:
                count, backup = self.catalog.remove_rows(self.active_id, ids=request.get('ids'), succeeded_only=command == 'clean')
                logging.info('Se retiraron %s filas. Los resultados confirmados se conservan.', count)
            logging.info('Respaldo previo: %s', backup)
        elif command == 'export':
            record = self.record()
            if not record:
                raise ValueError('Selecciona una tabla.')
            with RunLock(self.catalog.database(record)):
                store = self.Store(self.catalog.database(record))
                try:
                    store.export(self.paths(record), self.fields)
                    self.published(record, self.paths(record))
                finally:
                    store.close()
            logging.info('Resultados exportados desde SQLite; no se consultó el portal.')
        elif command == 'retry_empty':
            if not getattr(self.Store, 'supports_empty', False):
                raise ValueError('Este módulo no registra consultas vacías.')
            record = self.record()
            if not record:
                raise ValueError('Selecciona una tabla.')
            with RunLock(self.catalog.database(record)):
                store = self.Store(self.catalog.database(record))
                try:
                    duas = store.queue_empty(request.get('ids'))
                finally:
                    store.close()
            if not duas:
                raise ValueError('No hay vacíos en la selección para reintentar.')
            self.daily.reopen(duas)
            result = self.execute('run', {'daily_duas': duas, 'viewQuery': request.get('viewQuery', {})})
            self.daily.reconcile(record)
            result['snapshot'] = self.snapshot()
            return result
        elif command == 'run':
            record = self.record()
            if not record:
                raise ValueError('Selecciona una tabla.')
            paths = self.paths(record)
            with RunLock(self.catalog.database(record)):
                self.catalog.get(record['id'])
                automatic=request.get('daily_automatic') is True
                store = self.ScopedStore(self.catalog.database(record), request['daily_duas'], automatic=automatic) if 'daily_duas' in request else self.Store(self.catalog.database(record))
                monitor_stop = threading.Event()
                def monitor():
                    last = None
                    while not monitor_stop.wait(0.2):
                        value = store.summary()
                        if value != last:
                            self.protocol.emit('progress', summary=value)
                            last = value
                monitor_thread = threading.Thread(target=monitor, daemon=False)
                try:
                    processor = self.Processor({**self.machine,'max_retries':3} if automatic else self.machine, paths, self.flow, self.captcha, self.stop_event)
                    processor.on_export = lambda: self.published(record, paths)
                    monitor_thread.start()
                    processor.run(store, lambda summary: self.protocol.emit('progress', summary=summary))
                finally:
                    monitor_stop.set()
                    if monitor_thread.is_alive():
                        monitor_thread.join()
                    summary = store.summary()
                    store.close()
            if not automatic:self.daily.reconcile(record)
            return {'snapshot': self.snapshot(), 'view': self.view(request.get('viewQuery', {})),
                    'runStatus': 'stopped' if self.stop_event.is_set() else 'completed' if summary['total'] == summary['succeeded'] + summary.get('empty', 0) else 'pending'}
        elif command == 'refresh':
            self.machine = utils.load_machine_config()
        else:
            raise ValueError(f'Comando desconocido: {command}')
        return {'snapshot': self.snapshot(), 'view': self.view(request.get('viewQuery', {}))}


def main(module_id="detalles"):
    root = Path(__file__).resolve().parents[1] / "bots" / module_id
    profile = load_profile(module_id)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage-root', type=Path, default=root)
    parser.add_argument('--offline-fixture', action='store_true', help='Solo pruebas: sustituir el portal por HTML local y bloquear red.')
    args = parser.parse_args()
    if args.offline_fixture:
        if args.storage_root.resolve() == root:
            parser.error('La fixture exige almacenamiento separado de la instalación normal.')
        import asyncio
        async def local_result(processor, page, row):
            await page.route('**/*', lambda route: route.abort())
            await asyncio.sleep(0.25)
            html = ''.join(f'<span id="{key}">{value}</span>' for key, value in [
                ('span_CODI_ADUAN', row['Aduana']), ('span_ANO_PRESE', row['Año']), ('span_NUME_CORRE', row['Número'])])
            await page.set_content(html)
            return await page.content()
        if module_id == 'detalles':
            profile['processor']._fetch_result = local_result
        elif module_id == 'duas_transito':
            from .transit import install_offline_fixture
            install_offline_fixture(profile['processor'])
        else:
            from .import_fixture import install_offline_fixture
            install_offline_fixture(profile['processor'])
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    sys.stdin.reconfigure(encoding='utf-8')
    protocol = Protocol()
    reporter = ActivityReporter(protocol.emit)
    try:
        with reporter.session('Cargando bases de datos'):
            service = DetailsService(args.storage_root, protocol, offline=args.offline_fixture, module_id=module_id)
    except Exception as error:
        protocol.emit('fatal', message=str(error))
        return 1
    operation = None
    busy = threading.Event()
    readers = []

    def execute(request, foreground=True):
        try:
            observation = reporter.session(COMMANDS.get(request['command'], 'Procesando solicitud')) if foreground else nullcontext()
            with observation:
                result = service.execute(request['command'], request)
            protocol.emit('result', requestId=request.get('requestId'), command=request['command'], **result)
        except Exception as error:
            # Un lector de la lista puede coincidir con el COMMIT del motor.
            # La próxima actualización lo reintenta; no falló la descarga.
            code = getattr(error, 'sqlite_errorcode', 0)
            if (not foreground and request.get('command') == 'view'
                    and isinstance(error, sqlite3.OperationalError)
                    and code & 0xff in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_INTERRUPT)):
                protocol.emit('view_deferred', requestId=request.get('requestId'), command='view')
                return
            logging.exception('Operación interrumpida: %s', error, extra={'technical_only': True})
            data = {}
            if foreground:
                try:
                    data = {'snapshot': service.snapshot(), 'view': service.view(request.get('viewQuery', {}))}
                except Exception:
                    pass
            protocol.emit('error', requestId=request.get('requestId'), command=request.get('command'), message=str(error), **data)
        finally:
            if foreground:
                busy.clear()
            protocol.emit('idle', requestId=request.get('requestId'), readonly=not foreground)

    for line in sys.stdin:
        try:
            request = json.loads(line)
            command = request['command']
            if command == 'stop':
                service.stop_event.set()
                protocol.emit('stopping')
                continue
            if command == 'shutdown':
                break
            if busy.is_set() and command in {'view', 'detail', 'daily_calendar'}:
                readers = [thread for thread in readers if thread.is_alive()]
                if len(readers) >= 2:
                    protocol.emit('error', requestId=request.get('requestId'), command=command, message='Espera a que termine la lectura actual.')
                    continue
                thread = threading.Thread(target=execute, args=(request, False), daemon=False)
                readers.append(thread)
                thread.start()
                continue
            if busy.is_set():
                protocol.emit('error', requestId=request.get('requestId'), command=command,
                              message='Espera a que termine la operación actual o detén las consultas.')
                continue
            service.stop_event.clear()
            busy.set()
            operation = threading.Thread(target=execute, args=(request,), daemon=False)
            operation.start()
        except Exception as error:
            protocol.emit('error', message=str(error))
    service.stop_event.set()
    shutdown_deadline = time.monotonic() + SHUTDOWN_GRACE_SECONDS
    if operation:
        operation.join(timeout=max(0, shutdown_deadline - time.monotonic()))
    for reader in readers:
        reader.join(timeout=max(0, shutdown_deadline - time.monotonic()))
    if (operation and operation.is_alive()) or any(reader.is_alive() for reader in readers):
        # También protege el caso de GUI desaparecida: no queda un worker
        # esperando join() durante horas y reteniendo los bloqueos del lote.
        logging.error('Cierre sin respuesta; se conservan los resultados confirmados en SQLite.')
        os._exit(2)
    protocol.emit('closed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
