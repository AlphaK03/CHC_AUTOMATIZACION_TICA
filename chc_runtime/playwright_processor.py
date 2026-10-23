"""Navegación concurrente con cola durable y reintentos por rondas completas."""
from .distribution import chromium_options
import asyncio
import logging
import os
import sys
import time
import json
from pathlib import Path
from threading import Event
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page

from .captcha import resolve_captcha
from .identifiers import dua_fields, validate_result
from .portal_form import fill_and_submit, wait_form_ready
from .messages import pending_reason
from .detail_navigation import install_lightweight_detail
from .async_operations import AttemptDeadline, bounded_result, close_browser_resource
from .activity import stage, observed


def dua_subject(self, page, row):
    return row['NroDUA']


class ExtraStepRequired(RuntimeError):
    """Caso reservado para diagnóstico posterior; no se hace el clic adicional."""


class PlaywrightDUAProcessor:
    def __init__(self, machine_config, output_paths, flow, captcha_lookup, stop_event: Event):
        self.machine = dict(machine_config)
        self.output_paths = output_paths
        self._flow = flow
        self.captcha_lookup = captcha_lookup
        self.stop_event = stop_event
        self.fields = list(flow.fields) if hasattr(flow, 'fields') else list(flow.extract_data('').columns)
        self._last_export = time.monotonic()
        self._last_notification = 0.0

    def run(self, store, progress_callback):
        for key, default in [('cant_hilos', 1), ('max_retries', 3), ('timeout', 30)]:
            if int(self.machine.get(key, default)) < 1:
                raise ValueError(f'{key} debe ser mayor que cero')
        store.begin_run()
        self._notify(store, progress_callback, force=True)
        try:
            # asyncio.run() espera sin límite a tareas que ignoran cancelación.
            # El supervisor limita también esa limpieza del bucle.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._run_async(store, progress_callback))
            finally:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    _, unfinished = loop.run_until_complete(asyncio.wait(pending, timeout=5))
                    if unfinished:
                        logging.warning('Se descartaron tareas del navegador sin respuesta; los DUAs permanecen pendientes.',
                                        extra={'technical_only': True})
                        for task in unfinished:
                            task._log_destroy_pending = False
                loop.close()
                asyncio.set_event_loop(None)
            summary = store.summary()
            logging.info('%s %d DUAs guardados; %d pendientes.',
                         'Proceso detenido.' if self.stop_event.is_set() else 'Consultas terminadas.',
                         summary['succeeded'], summary['total'] - summary['succeeded'] - summary.get('empty', 0))
            if summary.get('empty'):
                logging.info('%d DUAs consultados sin movimientos (Vacío).', summary['empty'])
        finally:
            # SQLite ya confirmó cada resultado. CSV solo por petición del usuario.
            self._notify(store, progress_callback, force=True)

    async def _run_async(self, store, callback):
        summary = store.summary()
        if self.stop_event.is_set() or summary.get('automatic_ready') == 0 or summary['total'] == summary['succeeded'] + summary['invalid'] + summary.get('empty', 0):
            return
        if getattr(sys, 'frozen', False):
            os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',
                                  os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright'))
        manager = async_playwright()
        playwright = browser = None
        timeout = int(self.machine.get('timeout', 30))
        try:
            with stage('Iniciando navegador de consultas'):
                playwright = await bounded_result(manager.start(), timeout=timeout)
                browser = await bounded_result(playwright.chromium.launch(headless=self.machine.get('headless', True), **chromium_options()), timeout=timeout)
            try:
                for round_number in range(1, int(self.machine.get('max_retries', 3)) + 1):
                    if self.stop_event.is_set():
                        break
                    logging.info('Consultando los DUAs pendientes.' if round_number == 1 else
                                 'Reintentando automáticamente los DUAs que quedaron pendientes.')
                    await self._run_round(store, browser, round_number, callback)
                    summary = store.summary()
                    if summary.get('automatic_ready') == 0 or summary['succeeded'] + summary['invalid'] + summary.get('empty', 0) == summary['total']:
                        break
                    if round_number < int(self.machine.get('max_retries', 3)):
                        await self._cooldown(min(2 ** round_number, 30))
            finally:
                with stage('Cerrando navegador de consultas'):
                    await close_browser_resource(browser.close)
        finally:
            if playwright is not None:
                stopped = await close_browser_resource(playwright.stop)
            else:
                stopped = await close_browser_resource(lambda: manager.__aexit__(None, None, None))
            if not stopped:
                # Último recurso del driver de ESTE motor, sin tocar otros bots.
                connection = getattr(manager, '_connection', None)
                transport = getattr(connection, '_transport', None)
                process = getattr(transport, '_proc', None)
                if process is not None and process.returncode is None:
                    process.kill()
                    await close_browser_resource(process.wait)

    async def _run_round(self, store, browser, round_number, callback):
        concurrency = int(self.machine.get('cant_hilos', 1))
        workers = [asyncio.create_task(self._worker(store, browser, round_number, callback))
                   for _ in range(concurrency)]
        group = asyncio.gather(*workers)

        async def stopped():
            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)

        watcher = asyncio.create_task(stopped())
        try:
            done, _ = await asyncio.wait([group, watcher], return_when=asyncio.FIRST_COMPLETED)
            if watcher in done:
                for worker in workers:
                    worker.cancel()
            await group
        except asyncio.CancelledError:
            if not self.stop_event.is_set():
                raise
        finally:
            watcher.cancel()
            for worker in workers:
                if not worker.done():
                    worker.cancel()
            await asyncio.gather(*workers, watcher, return_exceptions=True)

    async def _worker(self, store, browser, round_number, callback):
        context = page = None
        created, uses = 0.0, 0
        reuse = bool(self.machine.get('reuse_context', True))
        try:
            while not self.stop_event.is_set():
                job = store.claim(round_number)
                if job is None:
                    return
                logging.info('Consultando DUA %s · ronda %s/%s', job['dua'], round_number, self.machine.get('max_retries',3))
                resolved, discard = False, False
                try:
                    try:
                        # El límite cubre TODO el intento, no solo cada acción.
                        # Una espera interna no puede retener la reserva indefinidamente.
                        deadline = AttemptDeadline(4 * int(self.machine.get('timeout', 30)))
                        if context is None:
                            context = await bounded_result(browser.new_context(), deadline=deadline)
                            page = await bounded_result(context.new_page(), deadline=deadline)
                            page.set_default_timeout(int(self.machine.get('timeout', 30)) * 1000)
                            await bounded_result(self._block_static(page), deadline=deadline)
                            created, uses = time.monotonic(), 0
                        # El resultado solo lo confirma el supervisor; una tarea
                        # abandonada no puede guardar tarde ni tomar otro DUA.
                        uses += 1
                        page._dua_attempt_deadline = deadline
                        with stage('Intento de consulta DUA', job['dua']):
                            record = await bounded_result(self._extract_record(page, dua_fields(job['dua'])), deadline=deadline)
                    except Exception as exc:
                        discard = True
                        evidence = await self._save_evidence(page, job['dua'])
                        kind = 'extra_step' if isinstance(exc, ExtraStepRequired) else type(exc).__name__
                        store.retry(job, exc, kind, evidence)
                        resolved = True
                        last_round = round_number >= int(self.machine.get('max_retries', 3))
                        next_step = 'Queda guardado como pendiente.' if last_round else 'Se reintentará al final.'
                        logging.warning('DUA %s: %s %s', job['dua'], pending_reason(kind, str(exc)), next_step)
                        logging.warning('[%s] Ronda %d: %s: %s', job['dua'], round_number, kind, exc,
                                        extra={'technical_only': True})
                    else:
                        # Los errores de disco siguen siendo fatales y no se reintentan como red.
                        store.complete(job, record)
                        resolved = True
                        logging.info('DUA %s: Vacío, sin movimientos por ahora.' if record.get('empty') else 'DUA %s guardado.',
                                     job['dua'], extra={'tag': 'INFO' if record.get('empty') else 'SUCCESS'})
                    self._notify(store, callback)
                finally:
                    if not resolved:
                        store.retry(job, 'Intento interrumpido; se retomará al iniciar.',
                                    'interrupted', cancelled=True)
                    if context is not None and (discard or not reuse or uses >= 100 or time.monotonic() - created >= 600):
                        try:
                            await close_browser_resource(context.close)
                        finally:
                            context = page = None
        finally:
            if context is not None:
                await close_browser_resource(context.close)

    def _notify(self, store, callback, force=False):
        now = time.monotonic()
        if not force and now - self._last_notification < 0.25:
            return
        self._last_notification = now
        callback(store.summary())

    @observed('Pausa entre rondas de reintento', lambda self,seconds:f'{seconds} s')
    async def _cooldown(self, seconds):
        until = time.monotonic() + seconds
        while not self.stop_event.is_set() and time.monotonic() < until:
            await asyncio.sleep(0.1)

    @observed('Consultando y validando DUA', dua_subject)
    async def _extract_record(self, page, row):
        html = await self._fetch_result(page, row)
        return validate_result(self._flow.extract_data(html), row['NroDUA'])

    async def _fetch_result(self, page: Page, row) -> str:
        hook = None
        if self.machine.get('lightweight_details', True):
            hook = await install_lightweight_detail(page, self._flow, row['NroDUA'],
                                                    int(self.machine.get('timeout', 30)) * 1000)
        try:
            return await self._fetch_page_result(page, row)
        finally:
            if hook:
                await asyncio.wait_for(page.unroute(*hook), timeout=5)

    async def _fetch_page_result(self, page: Page, row) -> str:
        # Tránsito también entra directamente aquí, sin el wrapper de Detalles.
        # Reiniciar por consulta evita atributos ausentes y HTML de un DUA anterior.
        page._dua_raw_detail = None
        page._dua_form_snapshot = None
        timeout_ms = int(self.machine.get('timeout', 30)) * 1000
        page.set_default_timeout(timeout_ms)
        with stage('Abriendo formulario de TICA', row['NroDUA']):
            response = await page.goto(self._flow.start_url, timeout=timeout_ms, wait_until='domcontentloaded')
        if response and response.status >= 400:
            raise RuntimeError(f'Portal respondió HTTP {response.status}')
        extra = page.locator('input[name="SALIR"][value="OK"]')
        if await extra.count():
            raise ExtraStepRequired('Página intermedia: requiere clic adicional')
        with stage('Esperando formulario de consulta', row['NroDUA']):
            await wait_form_ready(page, timeout_ms)
        captcha_text = await self._resolve_captcha(page, timeout_ms)
        try:
            with stage('Enviando consulta y esperando respuesta de TICA', row['NroDUA']):
                await fill_and_submit(page, row, captcha_text, timeout_ms,
                                      captcha_source=page._dua_captcha_source,
                                      button_name=getattr(self._flow, 'submit_button', 'DETALLE'))
        except Exception:
            if await extra.count():
                raise ExtraStepRequired('El resultado requiere clic adicional') from None
            raise
        if await extra.count():
            raise ExtraStepRequired('El resultado requiere clic adicional')
        return page._dua_raw_detail or await page.content()

    @observed('Leyendo CAPTCHA del formulario')
    async def _resolve_captcha(self, page, timeout_ms):
        img = await page.wait_for_selector('#captchaImage img', state='attached', timeout=timeout_ms)
        src = await img.get_attribute('src')
        page._dua_captcha_source = src
        return resolve_captcha(urljoin(page.url, src or ''), self.captcha_lookup)

    @staticmethod
    async def _block_static(page):
        async def route_request(route):
            if route.request.resource_type in ('stylesheet', 'font', 'image', 'media'):
                await route.abort()
            else:
                await route.continue_()
        await page.route('**/*', route_request)

    @staticmethod
    def _validate(data, dua_number):
        return validate_result(data, dua_number)

    def _evidence_document(self, html, dua, snapshot, url):
        return html, snapshot

    @observed('Guardando diagnóstico del intento', lambda self,page,dua,**kwargs:dua)
    async def _save_evidence(self, page, dua, *, source_html=None):
        if page is None or 'diagnostics' not in self.output_paths:
            return ''
        folder = Path(self.output_paths['diagnostics'])
        try:
            folder.mkdir(parents=True, exist_ok=True)
            html = source_html if source_html is not None else await bounded_result(page.content(), timeout=3)
            snapshot = getattr(page, '_dua_form_snapshot', None)
            html, snapshot = self._evidence_document(html, dua, snapshot, getattr(page, 'url', ''))
            from .job_store import atomic_output
            with atomic_output(folder / f'{dua}.html', newline='') as stream:
                stream.write(html)
            if snapshot:
                (folder / f'{dua}.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
            return str(folder / f'{dua}.html')
        except Exception:
            logging.warning('No se pudo guardar evidencia para %s.', dua, extra={'technical_only': True})
            return ''
