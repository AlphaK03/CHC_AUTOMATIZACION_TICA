"""playwright_processor.py — Motor de procesamiento DUA usando Playwright (browser compartido).

Un único proceso Chromium compartido entre todos los workers.
Cada worker tiene un BrowserContext aislado (cookies, sesión independientes).
Concurrencia gestionada con asyncio.Semaphore.
"""
import asyncio
import logging
import os
from threading import Event
from typing import Callable

import pandas as pd
import requests

from flows.base_flow import BaseFlow
from flows.xmovimientos_flow import NoMovimientosError


async def _wait_for_portal_async(url: str, interval: int = 10) -> None:
    """Bloquea hasta que el portal responda con HTTP 200."""
    loop = asyncio.get_event_loop()
    while True:
        try:
            ok = await loop.run_in_executor(
                None,
                lambda: requests.get(url, timeout=5).status_code == 200,
            )
            if ok:
                logging.info("Portal disponible nuevamente.")
                return
        except Exception:
            pass
        logging.warning("Portal no disponible, reintentando en %ds...", interval)
        await asyncio.sleep(interval)


class PlaywrightDUAProcessor:
    """
    Procesa DUAs con Playwright: un Chromium compartido, N contextos aislados.
    Punto de entrada: .run() — maneja asyncio internamente.
    """

    def __init__(
        self,
        machine_config: dict,
        output_paths: dict,
        flow: BaseFlow,
        names_df: pd.DataFrame,
        stop_event: Event,
    ):
        self.machine = machine_config
        self.output_paths = output_paths
        self.flow = flow
        self.names_df = names_df
        self.stop_event = stop_event
        self._processed_duas: set = set()

    def run(self, df: pd.DataFrame, start_from: int, progress_callback: Callable) -> None:
        """Punto de entrada sincrónico. Bloquea hasta que terminen todos los DUAs."""
        asyncio.run(self._run_async(df, start_from, progress_callback))

    # ── Async core ────────────────────────────────────────────────────────────

    async def _run_async(self, df: pd.DataFrame, start_from: int, progress_callback: Callable) -> None:
        self._lock = asyncio.Lock()
        self._load_processed_from_log()

        n_workers = self.machine.get('cant_hilos', 1)
        headless  = self.machine.get('headless', False)

        import sys
        if getattr(sys, 'frozen', False):
            local_appdata = os.environ.get('LOCALAPPDATA', '')
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.join(local_appdata, 'ms-playwright')

        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)
            try:
                sem   = asyncio.Semaphore(n_workers)
                tasks = []
                for idx, row in df.iterrows():
                    if self.stop_event.is_set():
                        break
                    if idx <= start_from:
                        continue
                    tasks.append(
                        asyncio.create_task(
                            self._process_one(browser, sem, idx, row, progress_callback)
                        )
                    )
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                await browser.close()

    async def _process_one(self, browser, sem, idx: int, row, progress_callback: Callable) -> None:
        """Procesa un DUA con reintentos dentro de un contexto Playwright aislado."""
        if self.stop_event.is_set():
            return

        dua_number  = row['NroDUA']
        max_retries = self.machine.get('max_retries', 3)
        timeout_ms  = self.machine.get('timeout', 10) * 1000
        _last_no_rows = False

        async with sem:
            for attempt in range(1, max_retries + 1):
                if self.stop_event.is_set():
                    return

                context = None
                try:
                    context = await browser.new_context()
                    page    = await context.new_page()

                    await self._navigate(page, timeout_ms)
                    captcha_text = await self._resolve_captcha(page, timeout_ms)
                    await self._fill_form(page, row, captcha_text, timeout_ms)
                    await self._wait_result(page, timeout_ms)

                    data = self.flow.extract_data(await page.content())
                    self._validate(data, dua_number)

                    extracted_dua = data.iloc[0]['numero_del_dua'].strip()

                    async with self._lock:
                        if extracted_dua in self._processed_duas:
                            logging.warning("DUA %s ya procesado. Omitido.", extracted_dua)
                            progress_callback(idx, 'skipped')
                            return
                        self._processed_duas.add(extracted_dua)
                        self._write_csv(data)
                        self._log_processed(extracted_dua)

                    logging.info("DUA %s guardado.", extracted_dua, extra={'tag': 'SUCCESS'})
                    progress_callback(idx, 'success')
                    return

                except NoMovimientosError:
                    _last_no_rows = True
                    logging.warning("[%s] Sin movimientos (intento %d/%d).",
                                    dua_number, attempt, max_retries)
                except Exception as e:
                    _last_no_rows = False
                    logging.warning("[%s] Intento %d/%d: %s: %s",
                                    dua_number, attempt, max_retries, type(e).__name__, e)
                finally:
                    if context:
                        await context.close()

            # Reintentos agotados
            if _last_no_rows:
                logging.warning("[%s] Sin movimientos tras %d intentos. Registrado.",
                                dua_number, max_retries)
                self._log_no_rows(dua_number)
            else:
                logging.error("[%s] Reintentos agotados.", dua_number)
                self._log_failed(dua_number)
            progress_callback(idx, 'failed')

    # ── Playwright helpers ────────────────────────────────────────────────────

    async def _navigate(self, page, timeout_ms: int) -> None:
        try:
            await page.goto(self.flow.start_url, timeout=timeout_ms, wait_until='domcontentloaded')
        except Exception as e:
            if 'ERR_NAME_NOT_RESOLVED' in str(e) or 'net::ERR' in str(e):
                logging.warning("Error de red al navegar. Esperando portal...")
                await _wait_for_portal_async(self.flow.start_url)
                await page.goto(self.flow.start_url, timeout=timeout_ms, wait_until='domcontentloaded')
            else:
                raise

    async def _resolve_captcha(self, page, timeout_ms: int) -> str:
        """Espera que GeneXus JS inyecte la imagen del CAPTCHA y la resuelve por lookup."""
        img = await page.wait_for_selector('#captchaImage img', timeout=timeout_ms)
        url = await img.get_attribute('src')
        matches = self.names_df.loc[self.names_df['Path'] == url, 'Word'].values
        return str(matches[0]) if len(matches) > 0 else ''

    async def _fill_form(self, page, row, captcha_text: str, timeout_ms: int) -> None:
        """Llena el formulario del portal TICA con los datos del DUA."""
        # Descartar página de rectificación de GeneXus si aparece (snapshot sin espera)
        if await page.locator('[name="Volver"]').is_visible():
            await page.click('[name="Volver"]')
            await page.wait_for_selector('#vVCODI_ADUA', timeout=timeout_ms)

        await page.evaluate("document.body.style.zoom='25%'")
        await page.wait_for_selector('#vVCODI_ADUA', timeout=timeout_ms)

        for selector, value in [
            ('#vVCODI_ADUA', str(row['Aduana'])),
            ('#vVANO_PRE',   str(row['Año'])),
            ('#vVNUME_CORR', str(row['Número'])),
            ('#_cfield',     captcha_text),
        ]:
            await page.fill(selector, value)

        await page.click('[name="MANAERMAR"]')

    async def _wait_result(self, page, timeout_ms: int) -> None:
        """Espera a que la tabla de movimientos y el número de DUA estén presentes."""
        await page.wait_for_selector('#SubstkContainerTbl', timeout=timeout_ms)
        await page.wait_for_selector('#span_CODI_ADUAN', timeout=timeout_ms)

    # ── Helpers sincrónicos ───────────────────────────────────────────────────

    def _validate(self, data: pd.DataFrame, dua_number: str) -> None:
        if (data is None or data.empty
                or 'numero_del_dua' not in data.columns
                or data['numero_del_dua'].iloc[0].strip() == ''):
            raise ValueError(f"Datos vacíos para DUA {dua_number}")

    def _load_processed_from_log(self) -> None:
        log_path = self.output_paths.get('processed_log', '')
        if not log_path or not os.path.exists(log_path):
            return
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    dua = line.strip()
                    if dua:
                        self._processed_duas.add(dua)
            logging.info("Cargados %d DUAs previos desde log.", len(self._processed_duas))
        except Exception as e:
            logging.error("No se pudo cargar DUAs previos: %s", e)

    def _write_csv(self, data: pd.DataFrame) -> None:
        path = self.output_paths['output_csv']
        header = not os.path.exists(path)
        data.to_csv(path, mode='a', header=header, index=False, encoding='utf-8-sig')

    def _log_processed(self, dua_number: str) -> None:
        with open(self.output_paths['processed_log'], 'a', encoding='utf-8') as f:
            f.write(f"{dua_number}\n")

    def _log_no_rows(self, dua_number: str) -> None:
        with open(self.output_paths['no_rows_duas'], 'a', encoding='utf-8') as f:
            f.write(f"{dua_number}\n")

    def _log_failed(self, dua_number: str) -> None:
        with open(self.output_paths['failed_duas'], 'a', encoding='utf-8') as f:
            f.write(f"{dua_number}\n")
