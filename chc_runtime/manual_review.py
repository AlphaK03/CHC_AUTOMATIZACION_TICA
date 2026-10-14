"""Un intento visible; deja el navegador abierto y nunca escribe en la cola."""
import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from threading import Event, Thread
from urllib.parse import urljoin, urlsplit
import uuid

from .manual_review_data import DUA_MODULES, load_selection
from .identifiers import dua_fields, normalize_dua

ROOT = Path(__file__).resolve().parents[1]


def check_link(base, link, suffix):
    target = urljoin(base, link)
    a, b = urlsplit(base), urlsplit(target)
    if (a.scheme,a.netloc) != (b.scheme,b.netloc) or not b.path.lower().endswith('/'+suffix):
        raise ValueError('El enlace no corresponde a la pantalla esperada de TICA.')
    return target


async def navigate_dua(browser, selection, fixture=False):
    from bs4 import BeautifulSoup
    from .profiles import load_profile
    from .captcha import load_captcha_lookup
    profile = load_profile(selection['module'])
    flow = profile['flow']()
    flow.fields = profile['fields']
    config = {**selection['config'], 'headless':False, 'lightweight_details':False}
    timeout = max(5, min(120, int(config.get('timeout',30))))
    config['timeout'] = timeout
    processor = profile['processor'](config, {}, flow, load_captcha_lookup(), Event())
    if fixture:
        if selection['module'] == 'duas_transito':
            from .transit import install_offline_fixture
        else:
            from .import_fixture import install_offline_fixture
            if selection['module'] == 'detalles':
                flow.module_id = 'detalles'
                flow.table_id = 'ReviewDetailContainerTbl'
                flow.raw_columns = 5
        install_offline_fixture(profile['processor'])
    context = await browser.new_context(no_viewport=True)
    page = await context.new_page()
    await processor._fetch_page_result(page, dua_fields(selection['dua']))
    module = selection['module']
    if module == 'talon':
        await page.locator('[name="LIQDUA"]').click(timeout=timeout*1000)
        await page.wait_for_selector('#Sftributos1ContainerTbl',state='attached',timeout=timeout*1000)
    elif module == 'duas_transito':
        await processor._click_result(page, '[name="LINEAS"]', timeout*1000)
    html = await page.content()
    soup = BeautifulSoup(html,'html.parser')
    suffix = '_0001' if module == 'talon' else ''
    actual = '-'.join(soup.select_one('#span_'+k+suffix).get_text(strip=True)
                      for k in ('CODI_ADUAN','ANO_PRESE','NUME_CORRE'))
    if normalize_dua(actual) != selection['dua']:
        raise ValueError('La pantalla corresponde a otro DUA; no se confirmó la consulta.')
    if module == 'detalles':
        return page, {'outcome':'opened','message':'Detalle del DUA abierto. Puedes revisarlo en el navegador.'}
    table_id = {'talon':'Sftributos1ContainerTbl','duas_transito':'SeriesContainerTbl','xmovimientos':'SubstkContainerTbl'}[module]
    await page.wait_for_selector('#'+table_id,state='attached',timeout=timeout*1000)
    soup = BeautifulSoup(await page.content(),'html.parser')
    if any(el.get_text(strip=True) for el in soup.select('#ERROR, [id$="gxErrorViewer"]')):
        raise ValueError('TICA muestra un mensaje de error en la consulta.')
    table = soup.select_one('#'+table_id)
    rows = [row for row in table.find_all('tr')[1:] if row.find_all('td')]
    if not rows:
        if not table.select('th'):
            raise ValueError('La respuesta no contiene un encabezado verificable.')
        noun = 'tributos' if module == 'talon' else 'movimientos' if module == 'xmovimientos' else 'líneas'
        return page, {'outcome':'empty_page','rows':0,'message':f'Sin {noun} en la página abierta. Puedes revisar TICA manualmente.'}
    return page, {'outcome':'has_rows','rows':len(rows),'message':f'La página abierta contiene {len(rows)} filas. Puedes revisar las demás páginas en TICA.'}


async def navigate_bls(browser, selection, fixture=False, portals=None):
    sys.path.insert(0,str(ROOT/'bots/bls/src'))
    from core.tica import TicaSession
    from config_manager import DEFAULTS
    from .bls_search import select_detail
    from .bls_pages import parse_page
    config = {**DEFAULTS, 'block_resources':False, 'timeout':min(120,selection['config'].get('timeout',30))}
    if fixture:
        from .bls_page_fixture import BLSPagePortal
        portal = BLSPagePortal(search_get=True)
        portals.append(portal)
        config['target_url'] = portal.url
    session = TicaSession(browser,config,{'contexts_created':0,'browser_requests':0,'http_requests':0})
    selected, _ = await select_detail(session,selection['record'])
    page = session.page
    if selected is None:
        raise ValueError('No se encontró el manifiesto/BL/secuencia exactos en la búsqueda. La página queda abierta para revisión.')
    target = check_link(page.url,selected['href'],'hcglineas.aspx')
    response = await page.goto(target,wait_until='domcontentloaded')
    if response is None or response.status != 200:
        raise ValueError('TICA no devolvió la página de líneas correctamente.')
    data = parse_page(await page.content(),selection['record'],selected['sequence'])
    message = f'El BL tiene {len(data.rows)} líneas en esta página.' if data.rows else 'El BL no tiene líneas en esta página.'
    return page, {'outcome':'has_rows' if data.rows else 'empty_page', 'rows':len(data.rows),
                  'more_pages':not data.eof,'message':message+' El navegador queda abierto para revisión.'}


async def navigate_manifest(browser, selection, fixture=False, portals=None):
    sys.path.insert(0,str(ROOT/'bots/manifiestos/src'))
    from manifest_scraper import ManifestScraper
    from conocimientos import parse_main_rows, FormInputs, IDENTITY
    flow, scope, mid = selection['flow'],selection['scope'],selection['manifest']
    mode = scope.get('mode', (scope.get('modes') or ['maritimo'])[0])
    timeout = min(120,selection['config'].get('timeout',30))
    context = await browser.new_context(no_viewport=True)
    page = await context.new_page()
    page.set_default_timeout(timeout*1000)
    address = ManifestScraper.URL
    if fixture:
        from .manifest_fixture import FixturePortal
        portal = FixturePortal(mode,scope);portals.append(portal);address = portal.url
    response = await page.goto(address,wait_until='domcontentloaded',timeout=timeout*1000)
    if response is None or response.status != 200:
        raise ValueError('No se abrió el formulario de manifiestos.')
    await page.select_option('#vVTRANS',ManifestScraper.MODE_MAP[mode])
    if mid != 'listado':
        parts = mid.split('-')
        if len(parts) != 5:
            raise ValueError('El manifiesto no tiene un identificador válido.')
        dates = [parts[4],parts[4]]
        await page.fill('#vVCGNROMIC',parts[2])
    else:
        import calendar
        year,month = scope['year'],scope['month']
        dates = [datetime.strptime(scope.get('start') or scope.get('desde') or f'{year}-{month:02d}-01','%Y-%m-%d').strftime('%d/%m/%y'),
                 datetime.strptime(scope.get('end') or scope.get('hasta') or f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]}','%Y-%m-%d').strftime('%d/%m/%y')]
    for name,value in zip(('vVFCH1','vVFCHF'),dates):
        await page.fill('#'+name,value)
        await page.locator('#'+name).press('Tab')
    async with page.expect_response(lambda r:urlsplit(r.url).path.lower()==urlsplit(address).path.lower() and r.request.method=='POST',timeout=timeout*1000) as received:
        await page.locator('[name="BTN_ENTER"]').click()
    response = await received.value
    if response.status != 200:raise ValueError('TICA devolvió un error al buscar el manifiesto.')
    payload = await response.json()
    if any(v for v in payload.get('gxMessages',{}).values()):raise ValueError('TICA devolvió un mensaje al buscar el manifiesto.')
    if mid == 'listado':
        return page, {'outcome':'opened','message':'Listado de manifiestos abierto para revisar el período.'}
    fields = {'conocimientos':('vVCONS','hcgcons.aspx'),'duas':('vVDUAS','hcgduama.aspx'),
              'movimientos':('vVMOVSTK','hcgmovi.aspx'),'contenedores':('vVCONTE','hcgkonte.aspx')}
    link_field, endpoint = fields[flow]
    grid = next(g for g in payload['gxGrids'] if g['GridName']=='Grid1')
    candidates = [href for href,info,_ in parse_main_rows(grid,payload['gxHiddens']['Grid1ContainerDataV'],address,link_field)
                  if '-'.join(info.values())==mid and href]
    if len(candidates)!=1:raise ValueError('No se encontró un enlace inequívoco para el manifiesto. El formulario queda abierto.')
    response = await page.goto(check_link(address,candidates[0],endpoint),wait_until='domcontentloaded',timeout=timeout*1000)
    if response is None or response.status!=200:raise ValueError('TICA no abrió el procedimiento del manifiesto.')
    scraper = ManifestScraper({'timeout_manifest':timeout},browser)
    state = json.loads(FormInputs(await page.content()).values.get('GXState','{}'))
    actual = '-'.join(str(state[k]).strip() for k in IDENTITY) if all(k in state for k in IDENTITY) else await scraper.obtener_identificador_manifiesto(page)
    if actual!=mid:raise ValueError('La página no confirma la identidad del manifiesto seleccionado.')
    if flow=='contenedores':await scraper._apply_contenedores_filter_llenos(page)
    return page, {'outcome':'opened','message':'Procedimiento del manifiesto abierto. Puedes observar el resultado en TICA.'}


async def review(root, module, request, stop, emit, fixture=False):
    from playwright.async_api import async_playwright
    from .async_operations import bounded_result, close_browser_resource
    selection = load_selection(root,module,request)
    folder = root/'data/manual_reviews'/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    manager = async_playwright();pw=browser=None;portals=[]
    try:
        if stop.is_set():return
        pw = await bounded_result(manager.start(),timeout=30)
        if stop.is_set():return
        browser = await bounded_result(pw.chromium.launch(headless=fixture),timeout=30)
        if stop.is_set():return
        async def navigate():
            if module in DUA_MODULES:return await navigate_dua(browser,selection,fixture)
            if module=='bls':return await navigate_bls(browser,selection,fixture,portals)
            return await navigate_manifest(browser,selection,fixture,portals)
        async def stopped():
            while not stop.is_set() and browser.is_connected():await asyncio.sleep(.1)
        navigation = asyncio.create_task(bounded_result(navigate(),timeout=4*min(120,selection['config'].get('timeout',30))))
        watcher = asyncio.create_task(stopped())
        done,_ = await asyncio.wait([navigation,watcher],return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            navigation.cancel();return
        watcher.cancel()
        try:
            page,result = navigation.result()
            emit('result',**result)
        except Exception as exc:
            if stop.is_set() or not browser.is_connected():return
            result = {'outcome':'error','message':str(exc) or type(exc).__name__}
            emit('error',message='La automatización no terminó: '+result['message']+' Puedes continuar en el navegador.')
            page = next((p for c in browser.contexts for p in c.pages),None)
        report = {'module':module,'request':request,'result':result,'checked_at':datetime.now().isoformat()}
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if page and not page.is_closed():
            try:(folder/'page.html').write_text(await bounded_result(page.content(),timeout=3),encoding='utf-8')
            except Exception:pass
        while not stop.is_set() and browser.is_connected() and any(c.pages for c in browser.contexts):
            await asyncio.sleep(.1)
    finally:
        if browser:await close_browser_resource(browser.close)
        if pw:await close_browser_resource(pw.stop)
        for portal in portals:portal.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',choices=(*DUA_MODULES,'bls','manifiestos'),required=True)
    parser.add_argument('--storage-root',type=Path,required=True)
    parser.add_argument('--offline-fixture',action='store_true')
    args=parser.parse_args()
    # NumPy/las extensiones de los parsers deben cargarse antes de bloquear
    # otro hilo leyendo stdin en Windows, igual que en los workers del lote.
    if args.module in DUA_MODULES:
        from .profiles import load_profile
        load_profile(args.module)
    else:
        sys.path.insert(0,str(ROOT/'bots'/args.module/'src'))
        if args.module=='bls':
            from core.tica import TicaSession
        else:
            from manifest_scraper import ManifestScraper
    sys.stdout.reconfigure(encoding='utf-8',line_buffering=True)
    sys.stdin.reconfigure(encoding='utf-8')
    def emit(event,**data):print(json.dumps({'event':event,**data},ensure_ascii=False),flush=True)
    pending_input=b''
    while b'\n' not in pending_input:
        chunk=os.read(sys.stdin.fileno(),4096)
        if not chunk:raise ValueError('No se recibió una consulta para revisar.')
        pending_input+=chunk
    first,pending_input=pending_input.split(b'\n',1)
    request=json.loads(first)
    if args.offline_fixture and args.storage_root.resolve()==(ROOT/'bots'/args.module).resolve():
        raise ValueError('El portal local exige almacenamiento separado.')
    stop=Event()
    def commands():
        buffered=pending_input
        while True:
            while b'\n' in buffered:
                line,buffered=buffered.split(b'\n',1)
                if json.loads(line).get('command')=='close':
                    stop.set();return
            chunk=os.read(sys.stdin.fileno(),4096)
            if not chunk:break
            buffered+=chunk
        stop.set()
    Thread(target=commands,daemon=True).start()
    loop=asyncio.new_event_loop();asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(review(args.storage_root.resolve(),args.module,request,stop,emit,args.offline_fixture))
    except Exception as exc:
        emit('error',message=str(exc) or type(exc).__name__)
        return 1
    finally:
        pending=asyncio.all_tasks(loop)
        for task in pending:task.cancel()
        if pending:loop.run_until_complete(asyncio.wait(pending,timeout=5))
        loop.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
