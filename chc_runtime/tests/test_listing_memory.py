"""Liberar el listado no cambia filas, sesiones ni renovación de enlaces."""
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'bots/manifiestos/src'))

from playwright.async_api import async_playwright
from chc_runtime.manifest_adapters import WorkbenchManifestScraper
from chc_runtime.manifest_fixture import FixturePortal
from conocimientos import parse_main_rows


class ListingMemory(unittest.IsolatedAsyncioTestCase):
    async def extract(self, folder, release):
        spec = {'year':2026,'month':10,'start':'2026-10-01','end':'2026-10-31'}
        portal = FixturePortal('maritimo', spec)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                scraper = WorkbenchManifestScraper({'timeout_manifest':5,'headless':True,
                    'workbench_release_listing':release,'omitir_organizacion_legacy':True,
                    'conocimientos_concurrencia':6,'conocimientos_exportar_csv':False,
                    'app_data_folder':str(folder/'internal'),'resultados_folder':str(folder/'public')}, browser)
                scraper.URL = portal.url
                scraper.init_conoc_output('maritimo',10,2026)
                scraper._conoc_mode = 'maritimo'
                scraper._conoc_link_lock = asyncio.Lock()
                scraper._conoc_link_refreshed = 0
                try:
                    await scraper.open_page()
                    context, previous = scraper.context, scraper.page
                    await context.add_cookies([{'name':'session-proof','value':'preserved','url':portal.url}])
                    await scraper._query_conoc_main()
                    self.assertIs(scraper.context,context)
                    self.assertEqual(previous.is_closed(),release)
                    self.assertEqual(scraper.page.url=='about:blank',release)
                    self.assertEqual((await context.cookies())[0]['value'],'preserved')
                    before = list(parse_main_rows(scraper.conoc_main_grid,scraper.conoc_main_values,scraper.URL))
                    first_id = '-'.join(before[0][1].values())
                    href = await scraper._renew_conoc_link(first_id)
                    self.assertEqual(href,before[0][0])
                    self.assertEqual(before,list(parse_main_rows(scraper.conoc_main_grid,scraper.conoc_main_values,scraper.URL)))
                    # Seis trabajadores; incluye páginas múltiples, vacío confirmado
                    # y esquema inválido. Solo los dos primeros pueden ser Guardado.
                    await scraper.process_conocimientos_links()
                    state = scraper.conoc_store.progress()
                    with closing(sqlite3.connect(scraper.conoc_store.db_path)) as db:
                        rows = db.execute('SELECT manifest,sequence,data FROM rows ORDER BY manifest,sequence').fetchall()
                        jobs = db.execute('SELECT id,state,attempts,kept_count FROM jobs ORDER BY ordinal').fetchall()
                    self.assertEqual((state['saved'],state['pending']), (2,1))
                    self.assertEqual(len(rows),3)
                    self.assertEqual(json.loads(rows[0][2])[2],'00001234567890123456789')
                    self.assertFalse(list(folder.rglob('*.CSV')))
                    return rows,jobs
                finally:
                    scraper.conoc_store.close()
                    if scraper.context: await scraper.context.close()
                    await browser.close()
        finally:
            portal.close()

    async def test_same_results_and_renewal_after_releasing_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            before = await self.extract(root/'before',False)
            after = await self.extract(root/'after',True)
            self.assertEqual(after,before)


if __name__=='__main__': unittest.main()
