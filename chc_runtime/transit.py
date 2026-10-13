"""Extracción de líneas de Tránsito v2 sobre la cola y navegación comunes."""
from html import escape
import logging
from urllib.parse import parse_qs, urlencode, urlsplit

from .identifiers import normalize_dua
from .job_store import JobStore, atomic_output
from .playwright_processor import PlaywrightDUAProcessor

FIELDS = ['Item', 'Partida', 'Descripción_Comercial', 'Bultos', 'Tipo_de_Bulto',
          'Nombre_del_consignatario', 'Declaración_de_origen_de_China', 'numero_del_dua']


def validate_rows(rows, expected):
    expected = normalize_dua(expected)
    if not rows:
        raise ValueError('No hay líneas confirmadas para el DUA.')
    items = set()
    for row in rows:
        if set(row) != set(FIELDS) or any(not isinstance(value, str) for value in row.values()):
            raise ValueError('La extracción no contiene los ocho campos de Tránsito.')
        if normalize_dua(row['numero_del_dua']) != expected:
            raise ValueError('La identidad de una línea no corresponde al DUA solicitado.')
        item = row['Item'].strip()
        if not item or item in items:
            raise ValueError('El portal repitió una línea o una página; la extracción queda pendiente.')
        items.add(item)
        row['numero_del_dua'] = expected
    return rows


class TransitJobStore(JobStore):
    def complete(self, job, result):
        rows = validate_rows(result.get('rows', []), job['dua'])
        # Todas las líneas y el éxito del DUA se confirman en una sola transacción.
        super().complete(job, {**rows[0], 'rows': rows})

    def result_rows(self, result):
        return validate_rows(result.get('rows', []), result['numero_del_dua'])

    def migrate_csv(self, path, fields):
        # El CSV/índice anterior no acredita haber terminado todas las páginas.
        if path:
            logging.info('CSV anterior conservado como referencia; no acredita extracción completa de líneas.')
        return 0

    def export(self, paths, fields):
        super().export(paths, fields)
        if 'no_rows_duas' in paths:
            with self.lock, atomic_output(paths['no_rows_duas']) as stream:
                for row in self.db.execute("SELECT dua FROM jobs WHERE status!='succeeded' AND error_kind='NoRowsException'"):
                    stream.write(row[0] + '\n')


class TransitProcessor(PlaywrightDUAProcessor):
    async def _click_result(self, page, selector, timeout_ms):
        origin = urlsplit(page.url).netloc
        def is_response(response):
            return (urlsplit(response.url).netloc == origin and
                    '.aspx' in urlsplit(response.url).path.lower() and
                    (response.request.is_navigation_request() or response.request.method == 'POST'))
        async with page.expect_response(is_response, timeout=timeout_ms) as response_info:
            await page.locator(selector).click(timeout=timeout_ms)
        response = await response_info.value
        await response.finished()
        if response.status >= 400:
            raise RuntimeError(f'Portal respondió HTTP {response.status} al consultar líneas.')
        await page.wait_for_load_state('domcontentloaded', timeout=timeout_ms)
        errors = page.locator('#ERROR, [id$="gxErrorViewer"]')
        for message in await errors.all_text_contents():
            if message.strip():
                raise ValueError('TICA devolvió un mensaje al consultar líneas: ' + message.strip())

    async def _extract_record(self, page, row):
        timeout_ms = int(self.machine.get('timeout', 30)) * 1000
        await self._fetch_page_result(page, row)
        await page.wait_for_selector('[name="LINEAS"]', timeout=timeout_ms)
        await self._click_result(page, '[name="LINEAS"]', timeout_ms)
        rows, seen_pages = [], set()
        while True:
            await page.wait_for_selector('#SeriesContainerTbl', state='attached', timeout=timeout_ms)
            signature = await page.locator('#SeriesContainerTbl').inner_html()
            if signature in seen_pages:
                raise ValueError('SIGUIENTE devolvió la misma página; el DUA queda pendiente.')
            seen_pages.add(signature)
            count = await page.locator('#SeriesContainerTbl tr[id^="SeriesContainerRow_"]').count()
            # Parser original: mismos ocho campos, orden y limpieza de texto.
            data = self._flow.extract_data(await page.content())
            part = data.to_dict(orient='records')
            if len(part) != count:
                raise ValueError('Hay líneas incompletas; no se guardó un resultado parcial.')
            rows.extend(part)
            validate_rows(rows, row['NroDUA'])
            following = page.locator('[name="SIGUIENTE"]')
            if count < 50 or not await following.count() or not await following.is_visible() or not await following.is_enabled():
                break
            if self.stop_event.is_set():
                raise RuntimeError('Extracción detenida antes de completar las páginas.')
            await self._click_result(page, '[name="SIGUIENTE"]', timeout_ms)
            await page.wait_for_function('before => document.getElementById("SeriesContainerTbl")?.innerHTML !== before',
                                         arg=signature, timeout=timeout_ms)
        return {**rows[0], 'rows': rows}


def install_offline_fixture(processor_class):
    """Fixture explícita: navegación local simulada y rechazo de cualquier red externa."""
    async def local_detail(processor, page, row):
        dua = row['NroDUA']
        origin = 'http://127.0.0.1'
        async def handle(route):
            request = route.request
            parsed = urlsplit(request.url)
            if parsed.netloc != '127.0.0.1' or parsed.path != '/hcimppon.aspx':
                await route.abort()
                return
            query = parse_qs(parsed.query)
            stage = query.get('stage', ['detail'])[0]
            page_number = int(query.get('page', ['1'])[0])
            header = ''.join(f'<span id="{key}">{value}</span>' for key, value in
                             [('span_CODI_ADUAN', row['Aduana']), ('span_ANO_PRESE', row['Año']), ('span_NUME_CORRE', row['Número'])])
            if stage == 'detail':
                target = '/hcimppon.aspx?' + urlencode({'stage': 'lines', 'page': 1})
                html = header + f'<button name="LINEAS" onclick="location.href=\'{target}\'">Líneas</button>'
            else:
                if dua.endswith('999998') and page_number == 2:
                    await route.fulfill(status=503, body='Error simulado después de la primera página')
                    return
                start, end = (1, 51) if page_number == 1 else (51, 53)
                cells = []
                for item in range(start, end):
                    values = [str(item), '00001234', '', 'Descripción, con; texto\noriginal', '02', 'CAJA',
                              'Consignatario de prueba', '', '', '', '', '', 'Sí']
                    cells.append(f'<tr id="SeriesContainerRow_{item}">' + ''.join('<td>'+escape(value)+'</td>' for value in values) + '</tr>')
                html = header + '<table id="SeriesContainerTbl">' + ''.join(cells) + '</table>'
                target = '/hcimppon.aspx?' + urlencode({'stage': 'lines', 'page': page_number + 1})
                html += f'<button name="SIGUIENTE" {"disabled" if page_number > 1 else ""} onclick="location.href=\'{target}\'">Siguiente</button>'
            await route.fulfill(status=200, content_type='text/html; charset=utf-8', body='<!doctype html><meta charset="utf-8">'+html)
        await page.route('**/*', handle)
        await page.goto(origin + '/hcimppon.aspx', wait_until='domcontentloaded')
        return await page.content()
    processor_class._fetch_page_result = local_detail
