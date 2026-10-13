"""DUAs y Movimientos utilizan la cola, el seguimiento y la recuperación común."""
import asyncio
import calendar
from copy import deepcopy
import logging
import time
from datetime import datetime

from conocimientos import extract_table, validate_concurrency
from organizar_resultados import organize_results
from resultados import output_paths
from tablas_manifiesto import ManifestTableStore, LINK_FIELDS, parse_table


class IsolatedTableRequest:
    """Una consulta lenta no retiene el bloqueo de sesión ASP.NET de las demás."""
    def __init__(self, factory, browser_context, user_agent):
        self.factory, self.browser_context, self.user_agent = factory, browser_context, user_agent
        self.client = None

    async def refresh(self):
        await self.close()
        cookies = deepcopy(await self.browser_context.cookies())
        # Conservar GX y las cookies de acceso necesarias para el enlace cifrado.
        cookies = [cookie for cookie in cookies if cookie['name'] != 'ASP.NET_SessionId']
        self.client = await self.factory.new_context(
            storage_state={'cookies': cookies, 'origins': []}, user_agent=self.user_agent)

    async def get(self, *args, **kwargs):
        if self.client is None:
            await self.refresh()
        return await self.client.get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        if self.client is None:
            await self.refresh()
        return await self.client.post(*args, **kwargs)

    async def close(self):
        if self.client is not None:
            client, self.client = self.client, None
            await client.dispose()


class ManifestTablesFlow:
    async def run_tracked_table(self, flow, mode, month, year):
        # Configuración independiente por procedimiento; el resto del bot conserva sus ajustes.
        self.config = dict(self.config)
        for option, default in [('concurrencia', 4), ('timeout_total', 0),
                                ('refresco_segundos', 600), ('exportar_csv', True),
                                ('fecha_inicio', None), ('fecha_fin', None),
                                ('manifest_ids', []), ('limite_manifiestos', None),
                                ('progress_callback', None)]:
            self.config['conocimientos_' + option] = self.config.get(flow + '_' + option, default)
        if flow == 'duas':
            # La tabla sin paginación puede tardar varios minutos en generarse.
            self.config['conocimientos_timeout_total'] = 0
        validate_concurrency(self.config['conocimientos_concurrencia'])
        self.config['conocimientos_courier'] = None
        self.table_flow = flow
        self._conoc_mode = mode
        self._conoc_link_lock = asyncio.Lock()
        self._conoc_link_refreshed = 0
        self.conoc_failed_rows, self.conoc_stats = [], []
        start = self.config['conocimientos_fecha_inicio'] or f'{year:04d}-{month:02d}-01'
        end = self.config['conocimientos_fecha_fin'] or f'{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]}'
        self.conoc_dates = [datetime.strptime(value, '%Y-%m-%d') for value in (start, end)]
        if self.conoc_dates[0] > self.conoc_dates[1] or any(d.year != year or d.month != month for d in self.conoc_dates):
            raise ValueError('El intervalo debe estar dentro del mes seleccionado')
        records = organize_results(self.config, only=(flow, mode, month, year))
        if any(r['state'] == 'Pospuesto' for r in records):
            raise RuntimeError('La salida anterior está en uso; cierre esa ejecución antes de continuar')
        paths = output_paths(self.config, flow, mode, month, year)
        scope = {'version': 1, 'flow': flow, 'mode': mode, 'month': month, 'year': year,
                 'url': self.URL, 'desde': start, 'hasta': end,
                 'ids': sorted(set(self.config['conocimientos_manifest_ids'] or [])),
                 'limit': self.config['conocimientos_limite_manifiestos']}
        self.conoc_output_path, self.conoc_failed_output_path = str(paths.csv), str(paths.failures)
        self.conoc_store = ManifestTableStore(paths.csv, scope, db_path=paths.database)
        logging.info('[%s] Iniciando %s %s/%s; salida: %s', flow, mode, month, year, paths.period)
        try:
            await self.open_page()
            await self._query_conoc_main()
            self.table_user_agent = await self.page.evaluate('navigator.userAgent')
            await self.process_conocimientos_links(link_field=LINK_FIELDS[flow], fetch_result=self._fetch_tracked_result)
        finally:
            try:
                self.write_conoc_failures()
            finally:
                self.conoc_store.close()
                if self.context:
                    await self.context.close()

    async def _fetch_tracked_result(self, href, ordinal, info):
        mid = '-'.join(info[k] for k in ('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha'))
        start = time.perf_counter()
        if self.request_factory is None:
            raise RuntimeError('No se configuró el cliente HTTP para las consultas independientes')
        request = IsolatedTableRequest(self.request_factory, self.context, self.table_user_agent)
        async def renew():
            link = await self._renew_conoc_link(mid)
            await request.refresh()
            return link
        unlimited = self.table_flow == 'duas'
        try:
            rows, stats = await extract_table(request, href, mid, 0 if unlimited else self.timeout,
                progress_callback=lambda stats: self._page_progress(mid, stats),
                checkpoint=self.conoc_store,
                refresh_seconds=float(self.config['conocimientos_refresco_segundos']),
                renew_link=renew,
                parse_html=lambda html, expected: parse_table(html, expected, self.table_flow),
                sequence_key=lambda row, position: position, sort_rows=False,
                request_attempts=1 if unlimited else 3, recover_errors=not unlimited,
                expected_status=200 if unlimited else None,
                parse_in_thread=True,
                activity_callback=lambda event: self._table_activity(mid, ordinal, event))
        finally:
            await request.close()
        stats['seconds'] = round(time.perf_counter() - start, 3)
        return mid, rows, stats

    def _table_activity(self, mid, ordinal, event):
        stage = event['stage']
        if stage in ('request', 'waiting'):
            elapsed = int(event['elapsed'])
            limit = f"límite {event['timeout']} s" if event['timeout'] else 'sin límite de tiempo; Detener sigue disponible'
            message = f'Esperando respuesta HTTP · {elapsed} s · {limit}'
        elif stage == 'response':
            message = f"Respuesta HTTP {event['status']} recibida; leyendo y validando contenido"
        else:
            message = ('Reintentando: ' if stage == 'retry' else 'Error HTTP: ') + event.get('error', '')
        self.conoc_store.activity(mid, message)
        self._notify_conoc(mid)
        logging.info('[%s] Fila %s | %s | %s', self.table_flow.upper(), ordinal, mid, message)
