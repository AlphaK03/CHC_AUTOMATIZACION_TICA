"""Formulario verificado por navegador y líneas por HTTP con su misma sesión."""
import json
import logging
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse

from core.inputs import query_dates
from core.tables import InvalidResponse, parse_detail, parse_search


URL = 'https://ticaconsultas.hacienda.go.cr/Tica/hcgconocimientos.aspx'


class TicaSession:
    def __init__(self, browser, config, stats):
        self.browser, self.config, self.stats = browser, config, stats
        self.context = self.page = None
        self.created, self.uses = 0, 0

    async def route(self, route):
        if route.request.resource_type in {'image', 'media', 'font', 'stylesheet'}:
            await route.abort()
        else:
            await route.continue_()

    async def ensure(self):
        if self.context is not None and (self.uses >= 100 or time.monotonic() - self.created >= 600):
            await self.close()
        if self.context is None:
            self.context = await self.browser.new_context(accept_downloads=False, service_workers='block')
            if self.config.get('block_resources', True):
                await self.context.route('**/*', self.route)
            self.context.on('request', lambda request: self._request())
            self.page = await self.context.new_page()
            self.page.set_default_timeout(float(self.config.get('timeout', 30)) * 1000)
            self.page.set_default_navigation_timeout(float(self.config.get('timeout', 30)) * 1000)
            self.created, self.uses = time.monotonic(), 0
            self.stats['contexts_created'] += 1
        url = self.config.get('target_url', URL)
        if self.page.url.lower().split('?')[0] != url.lower().split('?')[0]:
            response = await self.page.goto(url, wait_until='domcontentloaded')
            if response is None or response.status != 200:
                raise RuntimeError(f'HTTP {response.status if response else "sin respuesta"} abriendo el formulario')
        await self.page.locator('#vCGNROCON').wait_for(state='visible')
        await self.page.wait_for_function('() => window.gx && gx.evt && gx.evt.execEvt && gx.O')
        await self.wait_idle()

    async def wait_idle(self):
        await self.page.wait_for_function('() => !gx.ajax || !gx.ajax.iscallactive || !gx.ajax.iscallactive()')

    def _request(self):
        self.stats['browser_requests'] += 1

    def matches_response(self, response, record, dates):
        if response.request.method != 'POST' or urlparse(response.url).path.lower().split('/')[-1] != 'hcgconocimientos.aspx':
            return False
        fields = parse_qs(response.request.post_data or '')
        logging.debug('Respuesta de búsqueda: BL=%r fechas=%r/%r evento=%r', fields.get('vCGNROCON'),
                      fields.get('vVFCH1'), fields.get('vVFCHF'),
                      re.findall(r'"_EventName"\s*:\s*"([^"]*)"', fields.get('GXState', [''])[0]))
        return (fields.get('vCGNROCON') == [record['BL original']] and fields.get('vVFCH1') == [dates[0]]
                and fields.get('vVFCHF') == [dates[1]]
                and bool(re.search(r'"_EventName"\s*:\s*"EENTER\."', fields.get('GXState', [''])[0])))

    async def query(self, record):
        try:
            await self.ensure()
            dates = query_dates(record, self.config)
            values = {'vVFCH1': dates[0], 'vVFCHF': dates[1], 'vCGNROCON': record['BL original']}
            for name, value in values.items():
                locator = self.page.locator('#' + name)
                if await locator.count() != 1:
                    raise InvalidResponse('El formulario contiene campos ausentes o duplicados')
                await locator.fill(value)
            await self.page.locator('#vCGNROCON').press('Tab')
            await self.wait_idle()
            submitted = await self.page.evaluate("""() => Object.fromEntries(
                ['vVFCH1','vVFCHF','vCGNROCON'].map(id => [id,document.getElementById(id).value]))""")
            if submitted != values:
                raise InvalidResponse('El formulario cambió los filtros o el BL original')
            async with self.page.expect_response(lambda response: self.matches_response(response, record, dates)) as pending:
                await self.page.locator('[name="BTN_ENTER1"]').click()
            response = await pending.value
            if response.status != 200:
                raise RuntimeError(f'HTTP {response.status} consultando el BL')
            payload = await response.json()
            selected, manifests = parse_search(payload, record, dates)
            await self.page.locator('#Grid2ContainerTbl').wait_for(state='attached')
            if selected is None:
                # No aceptar como final una página de búsqueda que aún tiene NEXT.
                if await self.next_button() is not None:
                    raise InvalidResponse('La búsqueda tiene más páginas; no se confirma una ausencia parcial')
                return {'status': 'no_match', 'error': 'No se encontró la identidad exacta del BL. Encontrados: ' + ', '.join(manifests)}
            href = urljoin(self.page.url, selected['href'])
            origin, target = urlparse(self.page.url), urlparse(href)
            if (target.scheme, target.netloc) != (origin.scheme, origin.netloc) or not target.path.lower().endswith('/hcglineas.aspx'):
                raise InvalidResponse('El enlace de líneas no pertenece al portal esperado')
            if self.config.get('detail_strategy', 'http') == 'http':
                self.stats['http_requests'] += 1
                detail = await self.context.request.get(href, timeout=float(self.config.get('timeout', 30)) * 1000)
                try:
                    if detail.status != 200 or not urlparse(detail.url).path.lower().endswith('/hcglineas.aspx'):
                        raise RuntimeError(f'HTTP {detail.status} descargando líneas del BL')
                    html = await detail.text()
                    columns, rows = parse_detail(html, record, selected['sequence'])
                    # Si existe paginación, se completa mediante el navegador que posee la sesión.
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    if soup.select('.PagingButtonsNext'):
                        columns, rows = await self.browser_detail(selected, record)
                finally:
                    await detail.dispose()
            else:
                columns, rows = await self.browser_detail(selected, record)
            self.uses += 1
            return {'status': 'success', 'columns': columns + ['manifiesto', 'bls'],
                    'rows': [[value.replace(',', '').replace('"', '') for value in row] +
                             [record['IDManifiesto'], record['BL original']] for row in rows]}
        except BaseException:
            await self.close()
            raise
        finally:
            if not self.config.get('reuse_context', True):
                await self.close()

    async def next_button(self):
        buttons = self.page.locator('.PagingButtonsNext')
        for index in range(await buttons.count()):
            button = buttons.nth(index)
            classes = (await button.get_attribute('class') or '').lower()
            if await button.is_visible() and await button.is_enabled() and 'disabled' not in classes:
                return button
        return None

    async def browser_detail(self, selected, record):
        await self.page.wait_for_function("""({id,href}) =>
            document.getElementById(id)?.closest('a')?.getAttribute('href') === href""", arg=selected)
        async with self.page.expect_response(lambda response: response.request.method == 'GET'
                and urlparse(response.url).path.lower().endswith('/hcglineas.aspx')) as pending:
            await self.page.locator('#' + selected['id']).click()
        response = await pending.value
        if response.status != 200:
            raise RuntimeError(f'HTTP {response.status} navegando al detalle')
        await self.page.locator('#Grid1ContainerTbl').wait_for(state='attached')
        html = await self.page.content()
        columns, rows = parse_detail(html, record, selected['sequence'])
        if await self.next_button() is not None:
            raise InvalidResponse('Detalle paginado: no se confirma una tabla parcial')
        return columns, rows

    async def close(self):
        context, self.context = self.context, None
        self.page = None
        if context is not None:
            await context.close()
