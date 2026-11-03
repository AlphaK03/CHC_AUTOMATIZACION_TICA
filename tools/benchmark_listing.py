"""Listado GeneXus grande sintético: medir RAM estable y verificar extracción.

Portal 127.0.0.1, seis consultas, seis manifiestos seleccionados de un listado
grande. Datos temporales; no abre bases ni realiza consultas a TICA.
"""
import argparse
import asyncio
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from urllib.parse import urlencode

from process_memory import Sampler, sample_tree


async def run(repo, count):
    sys.path.insert(0,str(repo))
    sys.path.insert(0,str(repo/'bots/manifiestos/src'))
    if (repo/'chc_runtime/numeric_runtime.py').is_file():
        from chc_runtime.numeric_runtime import configure
        configure()
    from playwright.async_api import async_playwright
    from conocimientos import IDENTITY
    from chc_runtime.manifest_adapters import WorkbenchManifestScraper
    from chc_runtime.manifest_fixture import FixturePortal

    class LargeListing(FixturePortal):
        def main(self):
            grid={'GridName':'Grid1','Count':count}
            rows=[]
            fields=IDENTITY+['vVCONS','vVDUAS','vVMOVSTK','vVCONTE']
            for n in range(1,count+1):
                parts=['1','0',str(20260000+n),'P027','01/10/26']
                mid='-'.join(parts)
                links=[endpoint+'?'+urlencode({'id':mid,'n':n}) for endpoint in
                       ('hcgcons.aspx','hcgduama.aspx','hcgmovi.aspx','hcgkonte.aspx')]
                row=parts+links; rows.append(row)
                grid[str(n-1)]={'Props':[[field+'_0001',value] for field,value in zip(fields,row)]}
            return grid,rows

        def response(self,path,query,post,form):
            body,content=super().response(path,query,post,form)
            if path=='/hcicgmic.aspx' and not post:
                # Más columnas de presentación simulan el DOM pesado del portal.
                body=body.replace('</tr>', ('<td>Texto descriptivo del listado GeneXus</td>'*15)+'</tr>')
            return body,content

    spec={'year':2026,'month':10,'start':'2026-10-01','end':'2026-10-31'}
    portal=LargeListing('maritimo',spec)
    try:
        with tempfile.TemporaryDirectory(prefix='CHC-listing-') as folder:
            root=Path(folder)
            async with async_playwright() as pw:
                browser=await pw.chromium.launch(headless=True)
                scraper=WorkbenchManifestScraper({'timeout_manifest':30,'headless':True,
                    'workbench_release_listing':True,'omitir_organizacion_legacy':True,
                    'conocimientos_concurrencia':6,'conocimientos_limite_manifiestos':6,
                    'conocimientos_exportar_csv':False,'app_data_folder':str(root/'internal'),
                    'resultados_folder':str(root/'public')},browser)
                scraper.URL=portal.url
                scraper.init_conoc_output('maritimo',10,2026)
                scraper._conoc_mode='maritimo'; scraper._conoc_link_lock=asyncio.Lock(); scraper._conoc_link_refreshed=0
                try:
                    with Sampler(os.getpid()) as sampler:
                        started=time.perf_counter()
                        await scraper.open_page(); await scraper._query_conoc_main()
                        await asyncio.sleep(.7)  # Dejar terminar el cierre del renderer anterior.
                        rows=sample_tree(os.getpid())
                        steady=dict(resident_mib=round(sum(x['resident_mib'] for x in rows),2),
                                    committed_mib=round(sum(x['committed_mib'] for x in rows),2))
                        await scraper.process_conocimientos_links()
                        elapsed=time.perf_counter()-started
                        progress=scraper.conoc_store.progress()
                        with closing(sqlite3.connect(scraper.conoc_store.db_path)) as db:
                            values=db.execute('SELECT manifest,sequence,data FROM rows ORDER BY manifest,sequence').fetchall()
                        assert (progress['saved'],progress['pending'],len(values))==(5,1,12),progress
                    return dict(listed=count,selected=6,workers=6,steady=steady,seconds=round(elapsed,3),
                        saved=5,pending_invalid=1,rows=len(values),
                        sha256=hashlib.sha256(json.dumps(values,ensure_ascii=False).encode()).hexdigest(),**sampler.summary())
                finally:
                    scraper.conoc_store.close()
                    await browser.close()
    finally:
        portal.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rows',type=int,default=2000)
    args=parser.parse_args()
    if not 6 <= args.rows <= 5000: parser.error('Entre 6 y 5000 filas sintéticas.')
    result=asyncio.run(run(args.code_root.resolve(),args.rows))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__': main()
