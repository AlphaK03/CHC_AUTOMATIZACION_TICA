"""Extracción de líneas de Tránsito v2 sobre la cola y navegación comunes."""
from html import escape
import asyncio
import json
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


def confirmed_last_page(payload, rows, clean):
    """TICA puede repetir la última página llena; exigir su EOF y todas sus líneas."""
    try:
        hidden = payload['gxHiddens']
        messages = payload['gxMessages']
        if not rows or not isinstance(messages, dict) or messages.get('MAIN') != []:
            return False
        if any(value != [] for value in messages.values()):
            return False
        identity = normalize_dua('-'.join(hidden[key] for key in ('CODI_ADUAN', 'ANO_PRESE', 'NUME_CORRE')))
        if identity != rows[0]['numero_del_dua'] or str(hidden['SERIES_nEOF']) != '1':
            return False
        grids = [grid for grid in payload['gxGrids'] if grid.get('GridName') == 'Series']
        if len(grids) != 1 or int(grids[0]['Count']) != len(rows) or int(hidden['nRC_Series']) != len(rows):
            return False
        values = hidden['SeriesContainerDataV']
        values = json.loads(values) if isinstance(values, str) else values
        if not isinstance(values, list) or len(values) != len(rows):
            return False
        indices = (0, 1, 3, 4, 5, 6, 12)
        for values_row, row in zip(values, rows):
            if not isinstance(values_row, list) or len(values_row) < 13:
                return False
            record = {field: clean(values_row[index]) for field, index in zip(FIELDS[:-1], indices)}
            record['numero_del_dua'] = identity
            if record != row:
                return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


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
    async def _click_result(self, page, selector, timeout_ms, current_rows=None):
        if selector == '[name="LINEAS"]':
            # Igual que v2: el POST puede preceder a otra navegación. Su respuesta
            # no acredita que la página de líneas ya haya cargado.
            async with page.expect_navigation(wait_until='domcontentloaded', timeout=timeout_ms) as navigation:
                await page.locator(selector).click(timeout=timeout_ms)
            response = await navigation.value
            if response and response.status >= 400:
                raise RuntimeError(f'Portal respondió HTTP {response.status} al consultar líneas.')
            await page.wait_for_selector('#SeriesContainerTbl', state='attached', timeout=timeout_ms)
            await self._check_line_errors(page)
            return
        before = await page.locator('#SeriesContainerTbl').inner_html()
        target = urlsplit(page.url)
        def is_response(response):
            address = urlsplit(response.url)
            return (address.netloc == target.netloc and address.path.lower() == target.path.lower() and
                    (response.request.is_navigation_request() or response.request.method == 'POST'))
        async with page.expect_response(is_response, timeout=timeout_ms) as response_info:
            await page.locator(selector).click(timeout=timeout_ms)
        response = await response_info.value
        await response.finished()
        if response.status >= 400:
            raise RuntimeError(f'Portal respondió HTTP {response.status} al consultar líneas.')
        try:
            payload = await response.json()
        except ValueError:
            payload = None
        if current_rows and confirmed_last_page(payload, current_rows, self._flow._clean):
            return True
        await page.wait_for_function('before => !!document.getElementById("SeriesContainerTbl") && '
                                     'document.getElementById("SeriesContainerTbl").innerHTML !== before',
                                     arg=before, timeout=timeout_ms)
        await self._check_line_errors(page)

    async def _check_line_errors(self, page):
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
            deadline = getattr(page, '_dua_attempt_deadline', None)
            if deadline is not None:
                # Un DUA con muchas páginas puede tardar más mientras avance.
                deadline.reschedule(asyncio.get_running_loop().time() + 4 * int(self.machine.get('timeout', 30)))
            following = page.locator('[name="SIGUIENTE"]')
            if count < 50 or not await following.count() or not await following.is_visible() or not await following.is_enabled():
                break
            if self.stop_event.is_set():
                raise RuntimeError('Extracción detenida antes de completar las páginas.')
            if await self._click_result(page, '[name="SIGUIENTE"]', timeout_ms, current_rows=part):
                break
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
