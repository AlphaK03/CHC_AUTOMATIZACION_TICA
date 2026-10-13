"""Integración del flujo de conocimientos; no cambia los otros cuatro procesos."""
import asyncio
import calendar
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from conocimientos import (COLUMNS, KnowledgeStore, extract_table, parse_main_rows,
                           DEFAULT_CONCURRENCY, validate_concurrency, PortalErrorPage)
from resultados import output_paths
from organizar_resultados import organize_results


class ConocimientosFlow:
    def init_conoc_output(self, mode, month, year):
        if not self.config.get('omitir_organizacion_legacy', False):
            records = organize_results(self.config, only=('conocimientos', mode, month, year))
            if any(r['state'] == 'Pospuesto' for r in records):
                raise RuntimeError('La salida anterior está en uso o tiene un journal pendiente; cierre esa ejecución para continuar')
        paths = output_paths(self.config, 'conocimientos', mode, month, year)
        self.conoc_output_path = str(paths.csv)
        self.conoc_failed_output_path = str(paths.failures)
        courier = self.config.get('conocimientos_courier')
        if courier not in (None, 'N', 'S'):
            raise ValueError('conocimientos_courier debe ser N, S o null')
        start = self.config.get('conocimientos_fecha_inicio') or f'{year:04d}-{month:02d}-01'
        end = self.config.get('conocimientos_fecha_fin') or f'{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]}'
        self.conoc_dates = [datetime.strptime(value, '%Y-%m-%d') for value in (start, end)]
        if self.conoc_dates[0] > self.conoc_dates[1] or any(d.year != year or d.month != month for d in self.conoc_dates):
            raise ValueError('El intervalo debe estar ordenado y dentro del mes seleccionado')
        limit = self.config.get('conocimientos_limite_manifiestos')
        if limit is not None and int(limit) < 1:
            raise ValueError('El límite de manifiestos debe ser positivo')
        scope = {'version': 1, 'mode': mode, 'month': month, 'year': year,
                 'courier': courier, 'url': self.URL, 'desde': start, 'hasta': end,
                 'ids': sorted(set(self.config.get('conocimientos_manifest_ids') or [])),
                 'limit': limit}
        self.conoc_store = KnowledgeStore(self.conoc_output_path, scope, db_path=paths.database)
        self.conoc_failed_rows = []
        self.conoc_stats = []

    def write_conoc_failures(self):
        if self.config.get('conocimientos_exportar_csv', True):
            self.conoc_store.export(self.conoc_failed_output_path)

    def _notify_conoc(self, mid=None, snapshot=False):
        callback = self.config.get('conocimientos_progress_callback')
        if callback:
            event = {'progress': self.conoc_store.progress(),
                     'database': str(self.conoc_store.db_path)}
            if snapshot:
                event['jobs'] = self.conoc_store.jobs()
            elif mid:
                event['job'] = self.conoc_store.job(mid)
            callback(event)

    def _page_progress(self, mid, stats):
        self.conoc_store.page_progress(mid, stats)
        self._notify_conoc(mid)
        if stats['pages'] == 1 or stats['pages'] % 10 == 0:
            job = self.conoc_store.job(mid)
            logging.info('[CONS] Fila %s/%s | %s | página %s | %s registros leídos',
                         job['ordinal'], self.conoc_store.progress()['selected'], mid,
                         stats['pages'], stats['read'])

    async def extract_conocimientos_all_pages(self, page, id_manifiesto):
        rows, stats = await extract_table(
            page.context.request, page.url, id_manifiesto, self.timeout,
            self.config.get('conocimientos_courier'), first_html=await page.content())
        return pd.DataFrame(rows, columns=COLUMNS)

    async def _fetch_conoc_result(self, href, row_index, row_info):
        started = time.perf_counter()
        manifest_id = '-'.join(row_info.get(k, '').strip() for k in
                               ('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha'))
        rows, stats = await extract_table(
            self.context.request, href, manifest_id, self.timeout,
            self.config.get('conocimientos_courier'),
            progress_callback=lambda stats: self._page_progress(manifest_id, stats),
            checkpoint=self.conoc_store,
            refresh_seconds=float(self.config.get('conocimientos_refresco_segundos', 600)),
            renew_link=lambda: self._renew_conoc_link(manifest_id))
        stats['seconds'] = round(time.perf_counter() - started, 3)
        return manifest_id, rows, stats

    async def process_conocimientos_links(self, link_field='vVCONS', fetch_result=None):
        concurrency = validate_concurrency(self.config.get('conocimientos_concurrencia', DEFAULT_CONCURRENCY))
        fetch_result = fetch_result or self._fetch_conoc_result
        self._conoc_link_field = link_field
        # El formulario responde por AJAX. GXState en el DOM conserva los filtros
        # anteriores; tomar los enlaces de la respuesta confirmada evita esa carrera.
        snapshot = parse_main_rows(self.conoc_main_grid, self.conoc_main_values, self.URL, link_field)
        allowed = set(self.config.get('conocimientos_manifest_ids') or [])
        limit = self.config.get('conocimientos_limite_manifiestos')
        jobs, seen, corrections = [], set(), []
        for ordinal, item in enumerate(snapshot, 1):
            if item is None:
                continue
            href, info, old_id = item
            parts = [info.get(k, '').strip() for k in
                     ('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha')]
            if not all(parts):
                raise ValueError(f'Identificación incompleta en fila {ordinal}: {info}')
            manifest_id = '-'.join(parts)
            if manifest_id in seen:
                continue
            seen.add(manifest_id)
            if old_id != manifest_id:
                corrections.append((old_id, manifest_id, ordinal))
            if allowed and manifest_id not in allowed and old_id not in allowed:
                continue
            jobs.append((ordinal, href, info, manifest_id))
        missing = allowed - seen - {old for old, new, ordinal in corrections}
        if missing and not self.conoc_store.selection_ready():
            raise ValueError('No se encontraron los manifiestos solicitados: ' + ', '.join(sorted(missing)))
        if limit:
            jobs = jobs[:int(limit)]
        self.conoc_store.prepare_selection(jobs)
        self.conoc_store.start_run()
        changed = self.conoc_store.reconcile_identities(corrections, seen)
        for old_id, new_id in changed:
            logging.warning('[CONS] Identificador pendiente corregido desde los valores de TICA: %s -> %s', old_id, new_id)
        selected = self.conoc_store.jobs()
        pending = [job for job in selected if job['state'] == 'Pendiente']
        current = {mid: (href, info) for ordinal, href, info, mid in jobs}
        total = len(selected)
        totals = self.conoc_store.progress()
        logging.info('[CONS] %s seleccionados; %s guardados; %s excluidos; %s pendientes',
                     total, totals['saved'], totals['excluded'], len(pending))
        logging.info('[CONS] Descargas simultáneas configuradas: %s; trabajadores activos: %s',
                     concurrency, min(concurrency, len(pending)))
        self._notify_conoc(snapshot=True)
        queue = asyncio.Queue()
        for job in pending:
            queue.put_nowait(job)

        async def worker(worker_id):
            while True:
                try:
                    job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                mid, ordinal = job['id'], job['ordinal']
                try:
                    self.conoc_store.claim(mid)
                    self._notify_conoc(mid)
                    logging.info('[CONS] Fila %s/%s | trabajador %s | intento %s | Descargando | %s',
                                 ordinal, total, worker_id, job['attempts'] + 1, mid)
                    deadline = None
                    try:
                        href, info = current.get(mid, (None, None))
                        if not href:
                            raise ValueError('No hay enlace vigente para esta fila; pendiente de reintento')
                        total_timeout = float(self.config.get('conocimientos_timeout_total', 0))
                        deadline = asyncio.timeout(total_timeout if total_timeout > 0 else None)
                        async with deadline:
                            actual_id, rows, stats = await fetch_result(href, ordinal, info)
                        if actual_id != mid:
                            raise ValueError('El resultado corresponde a otro manifiesto')
                        self.conoc_store.save(mid, ordinal, rows, stats)
                        self.conoc_stats.append({'IDManifiesto': mid, **stats})
                    except Exception as exc:
                        if deadline is not None and deadline.expired():
                            exc = RuntimeError('Se alcanzó el límite total configurado para el manifiesto; '
                                               'avance parcial conservado en SQLite')
                        if isinstance(exc, PortalErrorPage) and getattr(self, 'table_flow', None) == 'duas':
                            self.conoc_store.exclude(mid, ordinal, str(exc))
                        else:
                            self.conoc_store.fail(mid, ordinal, str(exc) or type(exc).__name__)
                        self.conoc_failed_rows.append(mid)
                    state = self.conoc_store.job(mid)
                    progress = self.conoc_store.progress()
                    logging.info('[CONS] Fila %s/%s | %s | %s | procesados %s/%s en este intento | error=%s',
                                 ordinal, total, state['state'], mid, progress['processed_run'],
                                 len(pending), state['error'] or '-')
                    self._notify_conoc(mid)
                finally:
                    queue.task_done()

        tasks = [asyncio.create_task(worker(i + 1)) for i in range(min(concurrency, len(pending)))]
        try:
            await asyncio.gather(*tasks)
            self.conoc_progress = self.conoc_store.finish_run(len(pending))
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.conoc_store.interrupt('Ejecución interrumpida; pendiente de reintento.')
            self._notify_conoc(snapshot=True)
            raise
        self.conoc_summary = self.conoc_store.summary()
        logging.info('[CONS] Contabilidad final: %s seleccionados = %s guardados + %s pendientes + %s excluidos; '
                     '%s/%s pendientes intentados; %s descargando', total,
                     self.conoc_progress['saved'], self.conoc_progress['pending'],
                     self.conoc_progress['excluded'],
                     self.conoc_progress['processed_run'], len(pending), self.conoc_progress['active'])
        self._notify_conoc(snapshot=True)
        logging.info('[CONS] Resultado: %s', self.conoc_summary)

    async def run_conocimientos_for_mode(self, mode, month, year):
        logging.info('[CONS] Iniciando: modo=%s, mes=%s, año=%s', mode, month, year)
        self.init_conoc_output(mode, month, year)
        self._conoc_mode = mode
        self._conoc_link_lock = asyncio.Lock()
        self._conoc_link_refreshed = 0
        try:
            await self.open_page()
            await self._query_conoc_main()
            await self.process_conocimientos_links()
            if self.conoc_progress['pending']:
                logging.warning('[CONS] Finalizado con %s pendientes. Al iniciar solo se reintentarán esos.',
                                self.conoc_progress['pending'])
        finally:
            try:
                self.write_conoc_failures()
            finally:
                self.conoc_store.close()
                if self.context:
                    await self.context.close()
            logging.info('[CONS] Finalizado modo=%s', mode)

    async def _renew_conoc_link(self, manifest_id):
        # Solo una renovación de la lista a la vez; los demás trabajadores
        # reutilizan sus enlaces y no se cierra el contexto compartido.
        async with self._conoc_link_lock:
            if time.monotonic() - self._conoc_link_refreshed > 30:
                await self.page.goto(self.URL, timeout=self.timeout * 1000)
                await self._query_conoc_main()
                self._conoc_link_refreshed = time.monotonic()
            for href, info, _ in parse_main_rows(self.conoc_main_grid, self.conoc_main_values, self.URL,
                                               getattr(self, '_conoc_link_field', 'vVCONS')):
                if '-'.join(info.values()) == manifest_id and href:
                    return href
            raise ValueError('No hay enlace vigente para reanudar este manifiesto')

    async def _query_conoc_main(self):
        # No consultar el mes antes de aplicar el intervalo: una sola búsqueda.
        await self.page.select_option('#vVTRANS', self.MODE_MAP[self._conoc_mode])
        await self.page.fill('#vVCGNROMIC', '')
        for field, value in zip(('vVFCH1', 'vVFCHF'), self.conoc_dates):
            await self.page.fill('#' + field, value.strftime('%d/%m/%y'))
            await self.page.locator('#' + field).press('Tab')
        async with self.page.expect_response(
            lambda r: 'hcicgmic.aspx' in r.url and r.request.method == 'POST',
            timeout=self.timeout * 1000,
        ) as pending:
            await self.page.locator('[name="BTN_ENTER"]').click()
        response = await pending.value
        if not response.ok:
            raise RuntimeError(f'Error HTTP {response.status} consultando manifiestos')
        payload = await response.json()
        self.conoc_main_grid = next(g for g in payload['gxGrids'] if g['GridName'] == 'Grid1')
        self.conoc_main_values = payload['gxHiddens']['Grid1ContainerDataV']
