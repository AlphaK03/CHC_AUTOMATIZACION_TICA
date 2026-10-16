"""Comprobación local del prototipo; navegador aislado y sin red."""
from pathlib import Path
import json

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'runtime/investigacion_dashboard'


def main():
    sample=json.loads((OUT/'muestra.json').read_text(encoding='utf-8'))
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,args=['--disable-background-networking'])
        context=browser.new_context(viewport={'width':1536,'height':1040},locale='es-CR',offline=True)
        page=context.new_page()
        errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(request.url))
        page.goto((OUT/'index.html').as_uri())
        page.wait_for_selector('#preview-table tbody tr')
        assert page.locator('#k-duas').inner_text()==str(len(sample['datasets']['detalles']))
        expected=sum(row['_cents'] for row in sample['datasets']['talon'] if row['_cents'] is not None)
        # La cifra se valida también contra la suma de filas antes de otras uniones.
        actual=page.evaluate("D.talon.filter(r=>D.detalles.some(d=>d.numero_del_dua===r.numero_del_dua)).reduce((a,r)=>a+(r._cents??0),0)")
        assert actual==expected,(actual,expected)
        page.screenshot(path=str(OUT/'panorama.png'),full_page=True)
        tax_id=sample['datasets']['talon'][0]['numero_del_dua']
        page.locator('#search').fill(tax_id)
        assert page.locator('#preview-table tbody tr').count()==1
        page.locator('#preview-table button').first.click()
        assert page.locator('#drawer-title').inner_text()==tax_id
        assert page.locator('#drawer-overlay').is_visible()
        page.screenshot(path=str(OUT/'detalle-dua.png'),full_page=True)
        page.keyboard.press('Escape')
        assert page.locator('#drawer-overlay').is_hidden()
        page.locator('#search').fill('inexistente')
        assert page.locator('#k-duas').inner_text()=='0'
        page.locator('#reset').click()
        page.locator('#period').select_option('2026-09')
        assert page.locator('#k-duas').inner_text()=='0'
        assert page.locator('#k-bls').inner_text()==str(len(sample['datasets']['bl_jobs']))
        page.locator('#reset').click()
        page.locator('[data-view="relations"]').click()
        assert page.locator('#filters').is_hidden()
        page.locator('[data-node="bls"]').click()
        assert 'secuencia' in page.locator('#node-description').inner_text().lower()
        page.screenshot(path=str(OUT/'relaciones.png'),full_page=True)
        page.locator('[data-view="explorer"]').click()
        page.locator('#cargo-table tbody tr').first.click()
        assert page.locator('#drawer-title').inner_text().startswith('BL ')
        page.keyboard.press('Escape')
        page.locator('[data-view="research"]').click()
        assert page.locator('#view-research a').count()>=5
        page.locator('[data-view="overview"]').click()
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'), 'Desbordamiento móvil'
        page.screenshot(path=str(OUT/'movil.png'),full_page=True)
        assert not errors,errors
        assert not [url for url in requests if url.startswith(('http:','https:'))],requests
        browser.close()
    result={'ok':True,'checks':['carga local','sumas sin multiplicación','filtros','detalle DUA','detalle BL',
        'rango temporal','navegación','fuentes','vista móvil sin desbordamiento','sin solicitudes HTTP'],
        'screenshots':['panorama.png','detalle-dua.png','relaciones.png','movil.png']}
    (OUT/'VALIDACION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
