"""Portal local explícito para Talón/XMovimientos; nunca consulta la red externa."""
from html import escape
import json
from urllib.parse import parse_qs, urlencode, urlsplit


def install_offline_fixture(processor_class):
    original = processor_class._fetch_page_result
    async def local_form(processor, page, row):
        flow = processor._flow
        flow._START_URL = 'http://127.0.0.1/hcimppon.aspx'
        dua = row['NroDUA']
        code, year, number = dua.split('-')
        talon = flow.module_id == 'talon'
        image, word = next(iter(processor.captcha_lookup.items()))
        async def handle(route):
            request = route.request
            parsed = urlsplit(request.url)
            if parsed.netloc != '127.0.0.1' or parsed.path != '/hcimppon.aspx':
                await route.abort()
                return
            query = parse_qs(parsed.query)
            stage = query.get('stage', ['form'])[0]
            page_number = int(query.get('page', ['1'])[0])
            if stage == 'form' and request.method == 'GET':
                html = '<script>window.gx={O:{ServerClass:"hcimppon"}};</script>'
                html += f'<div id="captchaImage"><img src="http://127.0.0.1/Tica/Captcha/images/{image}.jpg"></div>'
                html += '<form method="post" action="/hcimppon.aspx">'
                html += ''.join(f'<input id="{name}" name="{name}">' for name in ('vVCODI_ADUA','vVANO_PRE','vVNUME_CORR'))
                html += '<input id="_cfield" name="cfield">'
                html += '<button name="DETALLE" value="1">Detalle</button><button name="MANAERMAR" value="1">Movimientos</button></form>'
            else:
                if stage == 'form':
                    posted = parse_qs(request.post_data or '')
                    expected = {'vVCODI_ADUA': code, 'vVANO_PRE': year, 'vVNUME_CORR': number, 'cfield': word,
                                'DETALLE' if talon else 'MANAERMAR': '1'}
                    if any(posted.get(k) != [v] for k,v in expected.items()):
                        await route.fulfill(status=400, body='Campos o acción incorrectos')
                        return
                    stage = 'detail' if talon else 'rows'
                suffix = '_0001' if talon and stage == 'rows' else ''
                header = ''.join(f'<span id="{name}{suffix}">{value}</span>' for name,value in
                                 [('span_CODI_ADUAN',code),('span_ANO_PRESE',year),('span_NUME_CORRE',number)])
                if stage == 'detail':
                    target = '/hcimppon.aspx?' + urlencode({'stage':'rows','page':1})
                    html = header + f'<button name="LIQDUA" onclick="location.href=\'{target}\'">Liquidación</button>'
                else:
                    if number == '999998' and page_number == 2:
                        await route.fulfill(status=503, body='Fallo después de la primera página')
                        return
                    multiple = number in ('000050','999998')
                    if number == '999997':
                        values = []
                    elif multiple:
                        start,end = (1,51) if page_number == 1 else (51,53)
                        values = [[code,year,number,f'{i:04}','Tributo de prueba','1.000 00'] if talon else
                                  ['0001',year,f'{i:06}','INGRESO','1,000'] for i in range(start,end)]
                    elif talon:
                        values = [[code,year,number,'001','Impuesto, de; prueba','1,234.50'],
                                  [code,year,number,'002','Otro tributo','25.00']]
                    else:
                        values = [['0001',year,'000001','INGRESO','1,200'],
                                  ['0001',year,'000001','INGRESO','3.5'],
                                  ['0002',year,'000002','SALIDA','2']]
                    html = header + f'<div gxgridid="42"><table id="{flow.table_id}"><tr>' + '<th>Campo</th>'*flow.raw_columns + '</tr>'
                    html += ''.join('<tr>'+''.join('<td>'+escape(value)+'</td>' for value in line)+'</tr>' for line in values)+'</table></div>'
                    if multiple:
                        target = '/hcimppon.aspx?' + urlencode({'stage':'rows','page':page_number+1})
                        html += f'<button name="SIGUIENTE" {"disabled" if page_number > 1 else ""} onclick="/* gx.evt.setGridEvt(42,null) */ location.href=\'{target}\'">Siguiente</button>'
                    elif talon:
                        html += '<button name="SIGUIENTE" onclick="gx.evt.setGridEvt(19,null)">Siguiente del desglose por artículo</button>'
            await route.fulfill(status=200,content_type='text/html; charset=utf-8',
                                body='<!doctype html><meta charset="utf-8">'+html)
        await page.route('**/*', handle)
        return await original(processor, page, row)
    processor_class._fetch_page_result = local_form
