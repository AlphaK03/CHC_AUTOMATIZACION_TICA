"""Trabajadores asyncio con sesiones propias y SQLite como única fuente de avance."""
import asyncio
import logging
from pathlib import Path

from core.inputs import batch_scope
from core.browser_runtime import BrowserSetupCancelled, configure_browser_cache, launch_chromium
from core.internet import ConnectionWaitStopped, InternetGuard, probe_internet
from core.store import JobStore
from core.tables import InvalidResponse
from core.tica import TicaSession
from paths import APP_DIR


class BLSProcessor:
    def __init__(self, config, stop_event):
        self.config, self.stop_event = config, stop_event
        self.summary = None
        self.store = None
        self.internet = None
        self.stats = {'contexts_created': 0, 'browser_requests': 0, 'http_requests': 0, 'attempted_this_run': 0}

    @staticmethod
    def validate_runtime():
        import importlib.util
        if importlib.util.find_spec('playwright') is None:
            raise RuntimeError('Instale Playwright y Chromium en el entorno virtual del bot.')

    def run(self, df):
        self.validate_runtime()
        return asyncio.run(self.run_async(df))

    def emit(self, kind='summary', **extra):
        callback = self.config.get('event_callback')
        if callback:
            callback({'kind': kind, **(self.summary or {}), **self.stats, **extra})

    async def run_async(self, df, session_factory=None):
        self.internet = None
        configure_browser_cache()
        signature, scope = batch_scope(df, self.config)
        scope['revision'] = self.config.get('batch_revision', '')
        if scope['revision']:
            import hashlib
            signature = hashlib.sha256((signature + scope['revision']).encode()).hexdigest()
        output = Path(self.config.get('output_base_path') or Path(APP_DIR) / 'output').expanduser().resolve()
        folder = output / self.config.get('sheet_name', 'BLS') / signature[:16]
        folder.mkdir(parents=True, exist_ok=True)
        database = folder / 'SQLite/bls.sqlite3'
        csv_path = folder / 'CSV' / f"Duas_procesados_{self.config.get('sheet_name', 'BLS')}.csv"
        self.store = JobStore(database, signature, scope)
        self.config.update(job_db=str(database), output_csv=str(csv_path), batch_folder=str(folder))
        try:
            self.emit(phase='prepare', output_folder=str(folder))
            self.store.prepare(df)
            self.store.start_run()
            self.summary = self.store.summary()
            self.emit(phase='ready', output_folder=str(folder), rows=[self.job_event(*row) for row in self.store.progress_rows(500)])
            count, queue = self.store.pending_queue()
            if count and not self.stop_event.is_set():
                n_workers = int(self.config.get('cant_hilos', 2))
                if not 1 <= n_workers <= 20:
                    raise ValueError('La concurrencia debe estar entre 1 y 20')
                attempts = int(self.config.get('max_retries', 3))
                if not 1 <= attempts <= 10:
                    raise ValueError('Los intentos deben estar entre 1 y 10')
                if session_factory is not None:
                    await self.rounds(queue, n_workers, attempts, session_factory)
                else:
                    from playwright.async_api import async_playwright
                    async with async_playwright() as pw:
                        self.internet = InternetGuard(lambda: probe_internet(pw), self.stop_event,
                            lambda phase, message: self.emit(phase=phase, message=message))
                        try:
                            browser = await launch_chromium(pw, bool(self.config.get('headless', True)), self.stop_event,
                                lambda stage, message: self.emit(phase='browser_ready' if stage == 'ready' else 'browser_setup',
                                                                 browser_stage=stage, message=message), internet_guard=self.internet)
                        except BrowserSetupCancelled:
                            logging.info('Instalación del navegador detenida. Los BL pendientes se conservan.')
                        else:
                            try:
                                factory = lambda worker: TicaSession(browser, self.config, self.stats)
                                await self.rounds(queue, n_workers, attempts, factory)
                            finally:
                                await browser.close()
            self.store.close_pending_queue()
            self.summary = self.store.finish_run(stopped=self.stop_event.is_set())
            self.summary['output_csv'] = str(csv_path)
            exports = [('exported', csv_path, lambda: self.store.export(csv_path)),
                       ('empty_exported', folder / 'CSV' / 'BLs_sin_lineas.csv',
                        lambda: self.store.export_review(folder / 'CSV' / 'BLs_sin_lineas.csv', empty=True)),
                       ('pending_exported', folder / 'CSV' / 'BLs_pendientes.csv',
                        lambda: self.store.export_review(folder / 'CSV' / 'BLs_pendientes.csv'))]
            errors = []
            for key, path, export in exports:
                self.summary[key + '_csv'] = str(path)
                try:
                    self.summary[key] = export()
                except OSError as exc:
                    errors.append(f'{path.name}: {exc}')
                    logging.error('CSV bloqueado; los datos guardados permanecen en SQLite: %s', exc)
            if errors:
                self.summary['export_error'] = '\n'.join(errors)
            if self.internet:
                self.stats['internet_pauses'] = self.internet.pauses
                self.stats['internet_checks'] = self.internet.checks
            self.emit(phase='finished', output_folder=str(folder))
            return self.summary
        except BaseException:
            try:
                self.store.cancel_running('La ejecución terminó antes de confirmar este BL')
                self.store.finish_run(failed=True)
            except Exception:
                logging.exception('No se pudo confirmar la recuperación; se intentará al reabrir SQLite')
            raise
        finally:
            self.store.close()
            self.store = None

    @staticmethod
    def job_event(ordinal, payload, state, attempts, result_count, error):
        import json
        record = json.loads(payload) if isinstance(payload, str) else payload
        return {'ordinal': ordinal, 'bl': record['BL original'], 'manifest': record['IDManifiesto'],
                'state': state, 'attempts': attempts, 'result_count': result_count, 'error': error}

    async def rounds(self, queue, workers, attempts, factory):
        for attempt in range(attempts):
            if attempt:
                count, queue = self.store.pending_queue(transient_only=True)
                if not count or self.stop_event.is_set():
                    return
                await asyncio.sleep(min(2 ** attempt, 5))
            self.emit(phase='download', round=attempt + 1)
            tasks = [asyncio.create_task(self.worker(queue, factory, worker + 1)) for worker in range(workers)]
            async def watch_stop():
                while not self.stop_event.is_set():
                    await asyncio.sleep(.1)
                for task in tasks:
                    task.cancel()
            watcher = asyncio.create_task(watch_stop())
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                if not self.stop_event.is_set():
                    raise
            finally:
                watcher.cancel()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(watcher, *tasks, return_exceptions=True)
            if self.stop_event.is_set():
                return

    async def worker(self, queue, factory, worker_id):
        session = factory(worker_id)
        try:
            while not self.stop_event.is_set():
                if self.internet:
                    try:
                        await self.internet.wait_until_online()
                    except ConnectionWaitStopped:
                        return
                try:
                    key, ordinal, record = next(queue)
                except StopIteration:
                    return
                token = self.store.claim(key)
                self.summary['pending'] -= 1
                self.summary['running'] += 1
                self.summary['attempts'] += 1
                self.stats['attempted_this_run'] += 1
                number = self.store.db.execute('SELECT attempts FROM jobs WHERE id=?', (key,)).fetchone()[0]
                self.emit('job', job=self.job_event(ordinal, record, 'Descargando', number, 0, ''))
                logging.info('[W%02d] Fila %d · BL=%s · intento %d', worker_id, ordinal, record['BL original'], number)
                try:
                    while True:
                        generation = self.internet.generation if self.internet else None
                        try:
                            result = await session.query(record)
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            if self.internet and await self.internet.recover_if_offline(exc, generation=generation):
                                continue  # El corte no consume otro intento ni cambia el BL.
                            result = {'status': 'invalid_response' if isinstance(exc, InvalidResponse) else 'transient', 'error': str(exc)}
                            break
                except (asyncio.CancelledError, ConnectionWaitStopped):
                    self.store.fail(key, token, 'Consulta interrumpida; BL original conservado', 'interrupted')
                    self.summary['running'] -= 1
                    self.summary['pending'] += 1
                    raise asyncio.CancelledError() from None
                if result['status'] == 'success':
                    # Fuera del manejo de errores de red: un fallo de disco detiene el motor.
                    self.store.save(key, token, result['columns'], result['rows'])
                    self.summary['saved'] += 1
                    if not result['rows']:
                        self.summary['empty_saved'] += 1
                    self.summary['result_rows'] += len(result['rows'])
                    state, error, rows = 'Guardado', '', len(result['rows'])
                else:
                    error = result.get('error', result['status'])
                    self.store.fail(key, token, error, result['status'])
                    self.summary['pending'] += 1
                    state, rows = 'Pendiente', 0
                    logging.warning('[W%02d] Fila %d permanece pendiente: %s', worker_id, ordinal, error)
                self.summary['running'] -= 1
                self.emit('job', job=self.job_event(ordinal, record, state, number, rows, error))
        finally:
            await session.close()
