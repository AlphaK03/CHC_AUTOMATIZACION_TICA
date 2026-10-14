"""Búsqueda BLs: respuesta POST clásica y refresco GET confirmado por GeneXus."""
import json

FIELDS = ('CGTPOTRANS','CGTPOMIC','CGNROMIC','RGDEPID','CGFCHARR','vVIAJES','vVLIN',
          'CGNROCONDNA','CGNROCON','CGCOURIER','vVCATEGORIA','CGTPOCON','CGGARACON',
          'vVGARANOM','CGPTODESCA','vDESCDESCARGA','vMASTER','CGPTOEMBAR','vDESCEMBARQUE',
          'vCGCODDOC','vCGCONCONSIG','vCGRSOCCONSIG','CGCONEST','CGNROCONMTR')


def parse_search_response(payload, record, dates):
    from core.tables import InvalidResponse, parse_search
    try:
        messages = payload['gxMessages']
        if not isinstance(messages,dict) or messages.get('MAIN')!=[] or any(v!=[] for v in messages.values()):
            raise InvalidResponse('TICA devolvió un mensaje en la búsqueda del BL')
        if 'GXH_vCGNROCON' in payload.get('gxHiddens',{}):
            return parse_search(payload,record,dates)
        scopes = [v for v in payload['gxValues'] if v.get('CmpContext')=='' and
                  str(v.get('IsMasterPage','')).lower()=='false']
        if len(scopes)!=1:
            raise InvalidResponse('El refresco GET no acredita los filtros de la búsqueda')
        scope = scopes[0]
        if (scope['AV5CGNroCon']!=record['BL original'] or
                (scope['AV15vFch1'],scope['AV16VfchF'])!=dates):
            raise InvalidResponse('El refresco GET corresponde a otro BL o período')
        grids = [g for g in payload['gxGrids'] if g.get('GridName')=='Grid2']
        if len(grids)!=1:
            raise InvalidResponse('El refresco GET no contiene una tabla de búsqueda inequívoca')
        grid = grids[0]
        count = int(grid['Count'])
        keys = sorted(int(k) for k in grid if k.isdigit())
        if count<0 or keys!=list(range(count)) or len(grid['Columns'])!=len(FIELDS):
            raise InvalidResponse('El refresco GET contiene filas o columnas incompletas')
        rows = []
        for index in range(count):
            props = grid[str(index)]['Props']
            if (len(props)!=len(FIELDS) or any(not isinstance(p,list) or len(p)<2 or
                    not isinstance(p[0],str) or not isinstance(p[1],str) for p in props) or
                    tuple(p[0].rsplit('_',1)[0] for p in props)!=FIELDS):
                raise InvalidResponse('Cambió el esquema de la búsqueda GET de BLs')
            rows.append([p[1] for p in props])
        # DataV puede ser [[]] en el refresco. Se usan las propiedades completas
        # de la respuesta del servidor y sus filtros, nunca el DOM anterior.
        normalized = {**payload,'gxHiddens':{'GXH_vCGNROCON':scope['AV5CGNroCon'],
            'GXH_vVFCH1':scope['AV15vFch1'],'GXH_vVFCHF':scope['AV16VfchF'],
            'nRC_Grid2':str(count),'Grid2ContainerDataV':json.dumps(rows)}}
        return parse_search(normalized,record,dates)
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        if isinstance(exc,InvalidResponse):raise
        raise InvalidResponse('Respuesta de búsqueda incompleta: '+str(exc)) from exc


async def select_detail(session, record):
    """Buscar con los filtros exactos; reutilizable sin descargar ni confirmar filas."""
    import asyncio
    from urllib.parse import urlparse
    from core.inputs import query_dates
    from core.tables import InvalidResponse
    await session.ensure()
    page = session.page
    dates = query_dates(record, session.config)
    address = urlparse(page.url)
    replies = asyncio.Queue()
    def receive(response):
        actual = urlparse(response.url)
        if ((actual.scheme,actual.netloc,actual.path.lower()) ==
                (address.scheme,address.netloc,address.path.lower()) and
                response.request.method in ('GET','POST') and
                response.request.resource_type in ('xhr','fetch')):
            replies.put_nowait(response)
    page.on('response', receive)
    try:
        values = {'vVFCH1':dates[0], 'vVFCHF':dates[1], 'vCGNROCON':record['BL original']}
        for name, value in values.items():
            locator = page.locator('#'+name)
            if await locator.count() != 1:
                raise InvalidResponse('El formulario contiene campos ausentes o duplicados')
            await locator.fill(value)
        await page.locator('#vCGNROCON').press('Tab')
        await session.wait_idle()
        submitted = await page.evaluate("""() => Object.fromEntries(
            ['vVFCH1','vVFCHF','vCGNROCON'].map(id => [id,document.getElementById(id).value]))""")
        if submitted != values:
            raise InvalidResponse('El formulario cambió los filtros o el BL original')
        selected = manifests = None
        rejected = []
        async def accept(response):
            if response.status != 200:
                raise RuntimeError(f'HTTP {response.status} buscando el BL')
            try:
                return parse_search_response(await response.json(), record, dates)
            except InvalidResponse as exc:
                rejected.append(str(exc))
                return None
        while not replies.empty():
            result = await accept(replies.get_nowait())
            if result is not None:
                selected, manifests = result
                break
        if manifests is None:
            await page.locator('[name="BTN_ENTER1"]').click()
            try:
                async with asyncio.timeout(float(session.config.get('timeout', 30))):
                    while manifests is None:
                        result = await accept(await replies.get())
                        if result is not None:
                            selected, manifests = result
            except TimeoutError as exc:
                reason = rejected[-1] if rejected else 'no llegó una respuesta de búsqueda GET/POST'
                raise TimeoutError(f'No se confirmó la búsqueda de {record["BL original"]}: {reason}. El BL conserva su progreso y queda pendiente.') from exc
        return selected, manifests
    finally:
        page.remove_listener('response', receive)
