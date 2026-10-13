"""Verificación local del ejecutable, sin consultas al portal."""
import asyncio
import json
import logging
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from threading import Event

from openpyxl import Workbook
import pandas as pd
from playwright.async_api import async_playwright
from core.engine import BLSProcessor
from core.browser_runtime import configure_browser_cache, launch_chromium
from core.inputs import batch_scope
from core.store import JobStore
from core.internet import InternetGuard, probe_internet
from playwright.async_api import TimeoutError as PlaywrightTimeout
from data_reader import leer_bls
from input_cache import load_input_cache, save_input_cache
from input_files import BLS_COLUMNS, input_sheets, load_input_file


async def check():
    configure_browser_cache()
    browser_stages = []
    async with async_playwright() as pw:
        browser_stop = Event()
        browser_guard = InternetGuard(lambda: probe_internet(pw), browser_stop)
        browser = await launch_chromium(pw, True, Event(), lambda stage, message: browser_stages.append(stage),
                                       internet_guard=browser_guard,
                                       args=['--disable-background-networking', '--disable-component-update'])
        try:
            page = await browser.new_page()
            await page.set_content('<span id="test">Chromium disponible</span>')
            assert await page.locator('#test').inner_text() == 'Chromium disponible'
        finally:
            await browser.close()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'base.xlsx'
        wb = Workbook()
        wb.active.title = 'BLS'
        wb.active.append(['IDManifiesto', 'Secuencia Tica', 'BL original', 'Fecha Manifiesto', 'Mes'])
        wb.active.append(['4-0-26000125-P010-01/04/26', '001', '00001234567890123456789', '01/04/2026', '2026-04'])
        wb.save(path)
        wb.close()
        data = leer_bls(path, 'BLS')
        cache = Path(folder) / 'base.sqlite3'
        save_input_cache(data, cache, path, sheet_name='BLS')
        cached_data = load_input_cache(cache)
        assert cached_data['BL original'].tolist() == data['BL original'].tolist()
        assert batch_scope(cached_data, {'sheet_name': 'BLS'}) == batch_scope(data, {'sheet_name': 'BLS'})
        assert input_sheets(cache) == ['BLS']
        assert load_input_file(cache)['BL original'].tolist() == load_input_file(path)['BL original'].tolist()
        generated = Path(folder) / 'conocimientos.sqlite3'
        with closing(sqlite3.connect(generated)) as db:
            with db:
                columns = ','.join('"' + name + '" TEXT NOT NULL' for name in BLS_COLUMNS)
                db.execute(f'CREATE TABLE BLS ({columns})')
                db.executemany('INSERT INTO BLS VALUES (?,?,?,?,?)',
                               data[BLS_COLUMNS].itertuples(index=False, name=None))
        generated_data = load_input_file(generated)
        assert input_sheets(generated) == ['BLS']
        assert generated_data.to_dict('records') == data.to_dict('records')
        assert batch_scope(generated_data, {'sheet_name': 'BLS'}) == batch_scope(data, {'sheet_name': 'BLS'})
        calls = []
        class Session:
            async def query(self, record):
                calls.append(record['BL original'])
                assert record['BL original'] == '00001234567890123456789'
                return {'status': 'success', 'columns': ['BL', 'Aduana'], 'rows': [[record['BL original'], '013']]}
            async def close(self):
                pass
        config = {'sheet_name': 'BLS', 'output_base_path': folder, 'cant_hilos': 1, 'max_retries': 1}
        result = await BLSProcessor(config, Event()).run_async(data, session_factory=lambda worker: Session())
        assert result['saved'] == 1
        assert result['pending_exported'] == 0 and result['empty_exported'] == 0
        assert Path(result['pending_exported_csv']).exists() and Path(result['empty_exported_csv']).exists()
        # Reanudar desde SQLite debe recuperar el lote que se empezó desde XLSX.
        await BLSProcessor(config, Event()).run_async(generated_data, session_factory=lambda worker: Session())
        assert len(calls) == 1
        queue_data = pd.concat([data.assign(**{'BL original': '000' + str(i)}) for i in range(20)], ignore_index=True)
        signature, scope = batch_scope(queue_data, config)
        database = Path(folder) / 'queue.sqlite3'
        store = JobStore(database, signature, scope)
        try:
            store.prepare(queue_data)
            count, queue = store.pending_queue()
            assert count == 20
            next(queue)
        finally:
            store.close()
        # La cola continúa referenciada: el cierre debe liberar SQLite por sí solo.
        with closing(sqlite3.connect(database, timeout=.1)) as probe:
            with probe:
                probe.execute("UPDATE metadata SET value=value WHERE key='signature'")
        queue.close()
    connectivity = iter(['offline', 'online'])
    async def simulated_probe():
        await asyncio.sleep(0)
        return next(connectivity)
    guard = InternetGuard(simulated_probe, Event(), interval=.001)
    resumed = await asyncio.gather(*[guard.recover_if_offline(PlaywrightTimeout('Corte simulado')) for _ in range(3)])
    assert resumed == [True] * 3 and guard.pauses == 1
    return {'ready': True, 'chromium': True, 'browser_downloaded': 'installing' in browser_stages,
            'browser_install_stages': browser_stages, 'sqlite_and_resume': True, 'sqlite_queue_released': True,
            'internet_pause_resume': True, 'review_csvs': True,
            'excel_zeroes': True, 'input_cache': True, 'input_formats': True,
            'knowledge_sqlite': True, 'cross_format_resume': True,
            'frozen': bool(getattr(sys, 'frozen', False))}


def verify(destination):
    path = Path(destination).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(path.with_suffix('.log')), level=logging.INFO,
                        encoding='utf-8', format='%(asctime)s %(levelname)s %(message)s')
    try:
        report = asyncio.run(check())
    except Exception as exc:
        logging.exception('Falló la verificación local del ejecutable')
        report = {'ready': False, 'error': str(exc)}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
