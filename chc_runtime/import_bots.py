"""Talón y XMovimientos: navegación propia y parsers v2 sobre la cola común."""
import asyncio
import json
import math
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .identifiers import normalize_dua
from .multirow import MultiRowJobStore
from .playwright_processor import PlaywrightDUAProcessor

TALON_FIELDS = ['Codigo_Aduana', 'Año', 'Numero', 'Tributo', 'Descripcion_tributo', 'Valor_MN', 'numero_del_dua']
# Orden producido por el groupby original, conservado también en el CSV.
MOVEMENT_FIELDS = ['Deposito', 'Año', 'Movimiento', 'Tipo_de_Movimiento', 'numero_del_dua', 'Cantidad_de_Bultos_asociada']


class TalonJobStore(MultiRowJobStore):
    fields = TALON_FIELDS

    @classmethod
    def validate_rows(cls, rows, expected):
        rows = super().validate_rows(rows, expected)
        for row in rows:
            if normalize_dua('-'.join(row[key] for key in ('Codigo_Aduana', 'Año', 'Numero'))) != normalize_dua(expected):
                raise ValueError('La identidad de un tributo no corresponde al DUA solicitado.')
        return rows


class MovementsJobStore(MultiRowJobStore):
    fields = MOVEMENT_FIELDS

    @classmethod
    def validate_rows(cls, rows, expected):
        rows = super().validate_rows(rows, expected)
        keys = set()
        for row in rows:
            key = tuple(row[name] for name in cls.fields[:4])
            if key in keys or not math.isfinite(float(row['Cantidad_de_Bultos_asociada'])):
                raise ValueError('Los movimientos no están agrupados o tienen cantidades inválidas.')
            keys.add(key)
        return rows


class ImportRowsProcessor(PlaywrightDUAProcessor):
    async def _extract_record(self, page, row):
        timeout = int(self.machine.get('timeout', 30)) * 1000
        await self._fetch_page_result(page, row)
        if self._flow.module_id == 'talon':
            await page.wait_for_selector('[name="LIQDUA"]', timeout=timeout)
            await page.locator('[name="LIQDUA"]').click(timeout=timeout)
        table_id = self._flow.table_id
        merged = None
        seen = set()
        while True:
            await page.wait_for_selector('#' + table_id, state='attached', timeout=timeout)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            error = soup.select_one('#ERROR')
            if error and error.get_text(strip=True):
                raise ValueError('TICA devolvió un mensaje: ' + error.get_text(strip=True))
            # El parser original comprueba identidad y ausencia de registros.
            data = self._flow.extract_data(html)
            records = data.astype(str).to_dict(orient='records')
            self._flow.store.validate_rows(records, row['NroDUA'])
            table = soup.find('table', id=table_id)
            raw_rows = table.find_all('tr')[1:]
            if any(len(tr.find_all('td')) < self._flow.raw_columns for tr in raw_rows):
                raise ValueError('Hay filas incompletas; no se guardó un resultado parcial.')
            values = [[td.get_text(strip=True) for td in tr.find_all('td')] for tr in raw_rows]
            signature = json.dumps(values, ensure_ascii=False)
            if signature in seen:
                raise ValueError('El portal repitió una página sin final confirmado; el DUA queda pendiente.')
            seen.add(signature)
            if merged is None:
                merged = soup
            else:
                target = merged.find('table', id=table_id)
                for tr in raw_rows:
                    target.append(tr.extract())
            deadline = getattr(page, '_dua_attempt_deadline', None)
            if deadline is not None:
                deadline.reschedule(asyncio.get_running_loop().time() + 4 * int(self.machine.get('timeout', 30)))
            following = page.locator('[name="SIGUIENTE"]')
            if not await following.count() or not await following.is_visible() or not await following.is_enabled():
                break
            owner = table if table.get('gxgridid') else table.find_parent(attrs={'gxgridid': True})
            control = soup.select_one('[name="SIGUIENTE"]')
            grid_event = re.search(r'setGridEvt\(\s*(\d+)', control.get('onclick', '')) if control else None
            if owner is not None and grid_event and owner['gxgridid'] != grid_event.group(1):
                # LIQDUA tiene otro grid de impuestos por artículo. Ese botón
                # no pagina el resumen Sftributos1 que solicita Talón v2.
                break
            if await self._next_page(page, row['NroDUA'], values, timeout):
                break
        # Agrupar XMovimientos UNA vez sobre todas las páginas, con el parser v2.
        rows = self._flow.extract_data(str(merged)).astype(str).to_dict(orient='records')
        self._flow.store.validate_rows(rows, row['NroDUA'])
        return {**rows[0], 'rows': rows}

    async def _next_page(self, page, dua, values, timeout):
        address = urlsplit(page.url)
        before = await page.locator('#' + self._flow.table_id).inner_html()
        def relevant(response):
            other = urlsplit(response.url)
            return (other.netloc == address.netloc and other.path.lower() == address.path.lower()
                    and (response.request.method == 'POST' or response.request.is_navigation_request()))
        async with page.expect_response(relevant, timeout=timeout) as received:
            await page.locator('[name="SIGUIENTE"]').click(timeout=timeout)
        response = await received.value
        if response.status >= 400:
            raise RuntimeError(f'TICA respondió HTTP {response.status} al cambiar de página.')
        try:
            payload = await response.json()
        except ValueError:
            payload = None
        if self._confirmed_end(payload, dua, values):
            return True
        await page.wait_for_function('args => {const t=document.getElementById(args.id); '
                                     'return !!t && t.innerHTML !== args.before;}',
                                     arg={'id': self._flow.table_id, 'before': before}, timeout=timeout)
        return False

    def _confirmed_end(self, payload, dua, values):
        try:
            hidden = payload['gxHiddens']
            messages = payload['gxMessages']
            if messages.get('MAIN') != [] or any(v != [] for v in messages.values()):
                return False
            suffix = '_0001' if self._flow.module_id == 'talon' else ''
            if normalize_dua('-'.join(hidden[k + suffix] for k in ('CODI_ADUAN', 'ANO_PRESE', 'NUME_CORRE'))) != normalize_dua(dua):
                return False
            grid = self._flow.table_id.removesuffix('ContainerTbl')
            if str(hidden[grid.upper() + '_nEOF']) != '1' or int(hidden['nRC_' + grid]) != len(values):
                return False
            grids = [g for g in payload['gxGrids'] if g.get('GridName') == grid]
            if len(grids) != 1 or int(grids[0]['Count']) != len(values):
                return False
            actual = hidden[grid + 'ContainerDataV']
            actual = json.loads(actual) if isinstance(actual, str) else actual
            return actual == values
        except (KeyError, TypeError, ValueError, AttributeError):
            return False
