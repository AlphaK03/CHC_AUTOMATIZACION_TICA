# manifest_scraper.py — Playwright async implementation

import os
import calendar
from datetime import datetime

import pandas as pd
import logging
import asyncio
import json
import unicodedata

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from utils import load_config, setup_logging
from conocimientos_flow import ConocimientosFlow
from tablas_flow import ManifestTablesFlow
from resultados import output_paths


class ManifestScraper(ManifestTablesFlow, ConocimientosFlow):
    #URL = "https://portaltica.hacienda.go.cr/ticaexterno/hcicgmic.aspx"
    URL = "https://ticaconsultas.hacienda.go.cr/Tica/hcicgmic.aspx"

    MODE_MAP = {
        "maritimo": "1",
        "aereo": "4",
        "terrestre": "7",
    }

    MESES_ES = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }

    CONOCIMIENTOS_COLS_ORDER = [
        "IDManifiesto", "Secuencia Tica", "BL original", "Courier",
        "Categoria", "Tipo", "RUC del garante", "Razón social",
        "Descarga", "Desc Descarga", "Master", "Embarque",
        "Desc Embarque", "Estado", "Nro de Conocimiento Master",
    ]

    CONT_OUT_COLS = [
        "IDManifiesto", "Contenedor", "Calificador", "Tamano",
        "PesoContenedor", "Viaje", "EstadoViaje", "LlenoVacio",
        "Marchamo1", "Destino", "EstadoContenedor", "DepositoRevision",
        "BLOriginal", "SecuenciaTica", "Linea", "Bultos", "Tipo", "EstadoMercancia",
    ]

    def __init__(self, config: dict, browser: Browser, request_factory=None):
        self.config = config
        self.browser = browser
        self.request_factory = request_factory
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.timeout = self.config.get("timeout_manifest", 60)

        self.duas_output_path = None
        self.duas_index_counter = 0
        self.duas_failed_rows: list = []
        self.duas_failed_output_path = None

        self.mov_output_path = None
        self.mov_index_counter = 0
        self.mov_failed_rows: list = []
        self.mov_failed_output_path = None

        self.conoc_output_path = None
        self.conoc_index_counter = 0
        self.conoc_failed_rows: list = []
        self.conoc_failed_output_path = None

        self.cont_output_path = None
        self.cont_index_counter = 0
        self.cont_failed_rows: list = []
        self.cont_failed_output_path = None

    # ── Resource blocking ──────────────────────────────────────────────────────

    @staticmethod
    async def _block_static(page: Page) -> None:
        await page.route(
            "**/*.{css,woff,woff2,ttf,eot}",
            lambda route: route.abort(),
        )

    # ── Page lifecycle ─────────────────────────────────────────────────────────

    async def open_page(self):
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        await self._block_static(self.page)
        timeout_ms = self.timeout * 1000
        try:
            await self.page.goto(self.URL, timeout=timeout_ms)
            await self.page.wait_for_selector("#vVTRANS", timeout=timeout_ms)
            logging.info("Página hcicgmic.aspx cargada correctamente.")
        except Exception as e:
            logging.error(f"No se pudo cargar la página principal: {e}")
            raise

    async def _open_sub_page(self, href: str) -> Page:
        sub_page = await self.context.new_page()
        await self._block_static(sub_page)
        await sub_page.goto(href, timeout=self.timeout * 1000)
        return sub_page

    # ── Text helpers ───────────────────────────────────────────────────────────

    def normalizar_texto(self, texto: str) -> str:
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
        return texto.lower().strip()

    # ── Calendar ───────────────────────────────────────────────────────────────

    async def seleccionar_mes(self, page: Page, mes_esperado: str, anio_esperado: int, es_inicio: bool = False):
        esperado = self.normalizar_texto(f"{mes_esperado}, {anio_esperado}")
        logging.info(f"Buscando mes '{mes_esperado}, {anio_esperado}' en calendario.")
        await page.wait_for_selector("div.calendar", timeout=10_000)

        for intento in range(12):
            cal = page.locator("div.calendar").first if es_inicio else page.locator("div.calendar").last
            titulo = (await cal.locator("td.calendartitle").text_content() or "").strip()
            if self.normalizar_texto(titulo) == esperado:
                logging.info("Mes/año encontrado.")
                return
            logging.info(f"[{intento}] Calendario: '{titulo}'")
            try:
                nav_btns = cal.locator("td[class*='calendar-nav']")
                count = await nav_btns.count()
                for i in range(count):
                    btn = nav_btns.nth(i)
                    if "‹" in (await btn.text_content() or ""):
                        await btn.click()
                        await page.wait_for_timeout(400)
                        break
            except Exception as e:
                logging.error(f"Error navegando calendario: {e}")
                return

        logging.warning("No se alcanzó el mes deseado en el calendario.")

    async def seleccionar_dia(self, page: Page, dia: int, es_inicio: bool):
        cal = page.locator("div.calendar").first if es_inicio else page.locator("div.calendar").last
        for day_el in await cal.locator("td.day").all():
            if (await day_el.text_content() or "").strip() == str(dia):
                await day_el.click()
                break
        logging.info(f"Día {dia} seleccionado.")
        input_id = "vVFCH1" if es_inicio else "vVFCHF"
        valor = await page.get_attribute(f"#{input_id}", "value")
        logging.info(f"Campo {input_id} tras seleccionar: '{valor}'")

    async def seleccionar_fecha(self, page: Page, mes: str, anio: int, dia: int, es_inicio: bool):
        await self.seleccionar_mes(page, mes, anio, es_inicio=es_inicio)
        await self.seleccionar_dia(page, dia, es_inicio=es_inicio)

    # ── Main navigation ────────────────────────────────────────────────────────

    async def set_filters(self, mode: str, month: int, year: int):
        page = self.page
        mode_value = self.MODE_MAP[mode.lower()]
        await page.select_option("#vVTRANS", mode_value)
        logging.info(f"Modalidad: {mode} -> value={mode_value}")
        await page.fill("#vVCGNROMIC", "")

        last_day_num = calendar.monthrange(year, month)[1]
        year_2d = year % 100
        start_str = f"01/{month:02d}/{year_2d:02d}"
        end_str = f"{last_day_num:02d}/{month:02d}/{year_2d:02d}"

        for field_id, value in [("vVFCH1", start_str), ("vVFCHF", end_str)]:
            await page.evaluate(
                """([id, val]) => {
                    const el = document.getElementById(id);
                    el.value = val;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('blur',   {bubbles: true}));
                }""",
                [field_id, value],
            )
        logging.info(f"Fechas: {start_str} - {end_str}")

    async def submit_form(self):
        await self.page.click('[name="BTN_ENTER"]')
        logging.info("Botón Confirmar clickeado. Esperando resultados...")
        try:
            await self.wait_for_results_table(self.page, self.timeout)
            logging.info("Tabla de resultados encontrada.")
        except Exception:
            logging.warning("No se encontró tabla de resultados en el tiempo esperado.")

    async def wait_for_results_table(self, page: Page, timeout: int = None):
        if timeout is None:
            timeout = self.config.get("timeout_manifest", 60)
        t = timeout * 1000
        await page.wait_for_selector("#Grid1ContainerTbl", timeout=t)
        await page.wait_for_selector("#Grid1ContainerTbl tbody tr", timeout=t)

    # ── Hidden grid helpers ────────────────────────────────────────────────────

    async def _read_hidden_grid(self, page: Page) -> str:
        try:
            return await page.evaluate(
                '(document.querySelector("[name=Grid1ContainerDataV]") || {value:""}).value || ""'
            )
        except Exception:
            return ""

    async def _read_hidden_grid_stable(
        self, page: Page, prev_hidden: str = "", wait_time: int = None, stable_hits: int = 2
    ) -> str:
        if wait_time is None:
            wait_time = self.timeout
        loop = asyncio.get_event_loop()
        deadline = loop.time() + wait_time
        prev = (prev_hidden or "").strip()
        last: str | None = None
        hits = 0
        while loop.time() < deadline:
            raw = await self._read_hidden_grid(page)
            if not raw or raw in ("[]", "[[]]"):
                last, hits = None, 0
                await asyncio.sleep(0.2)
                continue
            if raw == prev:
                last, hits = raw, 0
                await asyncio.sleep(0.2)
                continue
            if last == raw:
                hits += 1
            else:
                last, hits = raw, 1
            if hits >= stable_hits:
                return raw
            await asyncio.sleep(0.2)
        return ""

    async def _parse_hidden_grid_to_df(
        self, page: Page, id_manifiesto: str, wait_time: int = None, expected_hidden: str = None
    ) -> pd.DataFrame:
        if wait_time is None:
            wait_time = self.timeout
        loop = asyncio.get_event_loop()
        deadline = loop.time() + wait_time
        exp = (expected_hidden or "").strip()

        while loop.time() < deadline:
            raw = await self._read_hidden_grid(page)
            if not raw or raw in ("[]", "[[]]"):
                await asyncio.sleep(0.2)
                continue
            if expected_hidden is not None and raw == exp:
                await asyncio.sleep(0.2)
                continue
            try:
                data = json.loads(raw)
            except Exception:
                await asyncio.sleep(0.2)
                continue
            if not isinstance(data, list) or not data or not isinstance(data[0], list) or not data[0]:
                await asyncio.sleep(0.2)
                continue

            num_cols = len(data[0])
            try:
                ths = await page.query_selector_all("#Grid1ContainerTbl thead tr th")
                headers = [(await th.text_content() or "").replace("\xa0", " ").strip() for th in ths]
            except Exception:
                headers = []
            if not headers:
                headers = [f"Col_{i+1}" for i in range(num_cols)]
            elif len(headers) < num_cols:
                headers += [f"Col_{i+1}" for i in range(len(headers), num_cols)]
            else:
                headers = headers[:num_cols]

            df = pd.DataFrame(data, columns=headers)
            if id_manifiesto:
                df.insert(0, "IDManifiesto", id_manifiesto)
            return df

        return pd.DataFrame()

    # ── Common helpers ─────────────────────────────────────────────────────────

    async def obtener_identificador_manifiesto(self, page: Page) -> str:
        try:
            parts = []
            for span_id in ["span_CGTPOTRANS", "span_CGTPOMIC", "span_CGNROMIC", "span_RGDEPID", "span_CGFCHARR"]:
                parts.append((await page.text_content(f"#{span_id}") or "").strip())
            return "-".join(parts)
        except Exception:
            logging.warning("[ID] No se pudieron leer los spans del encabezado.")
        try:
            text = (await page.text_content("#TABLE1") or "").strip()
            if text:
                return text
        except Exception:
            pass
        return ""

    async def extract_main_row_info(self, row, headers: list) -> dict:
        cells = await row.query_selector_all("td")
        values = [(await c.text_content() or "").strip() for c in cells]
        desired = ["Trans.", "Ing Sal", "Manifiesto", "Cod Ubicacion", "Ubicacion", "Aduana", "Fecha"]
        info = {}
        for col in desired:
            try:
                idx = headers.index(col)
                if idx < len(values):
                    info[col] = values[idx]
            except ValueError:
                continue
        return info

    def _append_df_to_csv(self, df: pd.DataFrame, csv_path: str):
        if df is None or df.empty:
            return
        folder = os.path.dirname(csv_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        file_exists = os.path.exists(csv_path)
        df.to_csv(csv_path, mode="a" if file_exists else "w", header=not file_exists,
                  index=False, encoding="utf-8-sig")

    async def _snapshot_main_table_links(self, page: Page, css_selector: str, headers: list) -> list:
        desired = ["Trans.", "Ing Sal", "Manifiesto", "Cod Ubicacion", "Ubicacion", "Aduana", "Fecha"]
        raw = await page.evaluate(
            """([sel, desired]) => {
                const hdrs = Array.from(
                    document.querySelectorAll('#Grid1ContainerTbl thead tr th')
                ).map(th => th.textContent.replace(/\\u00a0/g, ' ').trim());
                return Array.from(
                    document.querySelectorAll('#Grid1ContainerTbl tbody tr')
                ).map(row => {
                    const link = row.querySelector(sel);
                    if (!link) return null;
                    const tds = Array.from(row.querySelectorAll('td'))
                                     .map(td => td.textContent.trim());
                    const info = {};
                    desired.forEach(col => {
                        const i = hdrs.indexOf(col);
                        if (i >= 0 && i < tds.length) info[col] = tds[i];
                    });
                    return [link.href, info];
                });
            }""",
            [css_selector, desired],
        )
        return [tuple(item) if item is not None else None for item in raw]

    # ── Flow 1: Tabla CSV ──────────────────────────────────────────────────────

    async def extract_table(self, timeout: int = 60, max_retries: int = 3) -> pd.DataFrame:
        page = self.page
        t = timeout * 1000
        for attempt in range(1, max_retries + 1):
            try:
                await page.wait_for_selector("#Grid1ContainerTbl", timeout=t)
                await page.wait_for_selector("#Grid1ContainerTbl tbody tr", timeout=t)

                # Single JS call — evita acumular miles de ElementHandles en tablas grandes
                headers, rows_data = await page.evaluate("""() => {
                    const ths = document.querySelectorAll('#Grid1ContainerTbl thead tr th');
                    const headers = Array.from(ths).map(th =>
                        th.textContent.replace(/\\u00a0/g, ' ').trim());
                    const rows = Array.from(
                        document.querySelectorAll('#Grid1ContainerTbl tbody tr')
                    ).map(row =>
                        Array.from(row.querySelectorAll('td'))
                            .map(td => td.textContent.trim())
                    ).filter(r => r.some(v => v));
                    return [headers, rows];
                }""")

                logging.info(f"Encabezados: {headers}")
                logging.info(f"Filas tbody: {len(rows_data)}")
                if not rows_data:
                    return pd.DataFrame(columns=headers)
                num_cols = max(len(r) for r in rows_data)
                if len(headers) < num_cols:
                    headers += [f"Col_{i+1}" for i in range(len(headers), num_cols)]
                else:
                    headers = headers[:num_cols]
                df = pd.DataFrame(rows_data, columns=headers)
                logging.info(f"DataFrame: {df.shape}")
                return df
            except Exception as e:
                if attempt < max_retries:
                    logging.warning(f"Reintentando extract_table ({attempt}/{max_retries}): {e}")
                    await page.wait_for_timeout(1000)
                else:
                    raise RuntimeError(f"No se pudo extraer la tabla: {e}")
        return pd.DataFrame()

    async def run_for_mode(self, mode: str, month: int, year: int, output_path: str):
        logging.info(f"Iniciando consulta: modo={mode}, mes={month}, año={year}")
        try:
            await self.open_page()
            await self.set_filters(mode, month, year)
            await self.submit_form()
            df = await self.extract_table()
            if df.empty:
                logging.warning(f"No hay registros para {mode} {month}/{year}")
            else:
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                df.to_csv(output_path, index=False, encoding="utf-8-sig")
                logging.info(f"Datos guardados en: {output_path}")
        except Exception as e:
            logging.exception(f"Error en run_for_mode({mode}): {e}")
        finally:
            logging.info(f"Finalizado modo={mode}")

    # ── Flow 2: DUAs ──────────────────────────────────────────────────────────

    def init_duas_output(self, mode: str, month: int, year: int):
        folder = self.config.get("output_manifest_duas_folder", "output_manifest_duas")
        os.makedirs(folder, exist_ok=True)
        self.duas_output_path = os.path.join(folder, f"duas_{mode}_{year:04d}_{month:02d}.csv")
        self.duas_failed_output_path = os.path.join(folder, f"duas_fallidas_{mode}_{year:04d}_{month:02d}.csv")
        self.duas_index_counter = 0
        if os.path.exists(self.duas_output_path):
            try:
                existing = pd.read_csv(self.duas_output_path)
                if "index_flujo_duas" in existing.columns and not existing.empty:
                    self.duas_index_counter = int(existing["index_flujo_duas"].max())
                    logging.info(f"[DUAs] CSV existente. Último index={self.duas_index_counter}")
            except Exception as e:
                logging.warning(f"[DUAs] No se pudo leer CSV existente: {e}")

    def register_dua_failure(self, row_info: dict, reason: str, manifest_id: str = "", row_index: int = None):
        data = dict(row_info) if row_info else {}
        if manifest_id:
            data["manifiesto_pagina_duas"] = manifest_id
        if row_index is not None:
            data["fila_origen"] = row_index
        data["motivo_fallo"] = reason
        self.duas_failed_rows.append(data)
        if not self.duas_failed_output_path:
            return
        try:
            df = pd.DataFrame([data])
            fe = os.path.exists(self.duas_failed_output_path)
            df.to_csv(self.duas_failed_output_path, mode="a" if fe else "w",
                      header=not fe, index=False, encoding="utf-8-sig")
            logging.warning(f"[DUAs] Fila fallida {row_index}: {reason}")
        except Exception as e:
            logging.error(f"[DUAs] Error guardando fallo: {e}")

    def write_dua_failures(self):
        if not self.duas_failed_rows or not self.duas_failed_output_path:
            logging.info("[DUAs] No hay filas fallidas.")
            return
        df = pd.DataFrame(self.duas_failed_rows)
        fe = os.path.exists(self.duas_failed_output_path)
        try:
            df.to_csv(self.duas_failed_output_path, mode="a" if fe else "w",
                      header=not fe, index=False, encoding="utf-8-sig")
            logging.info(f"[DUAs] {len(df)} filas fallidas escritas.")
        except Exception as e:
            logging.error(f"[DUAs] Error escribiendo CSV fallos: {e}")

    async def extract_duas_table(self, page: Page, manifest_id: str) -> pd.DataFrame:
        t = self.timeout * 1000
        try:
            await page.wait_for_selector('[name="Grid1ContainerDataV"]', timeout=t, state="attached")
            raw = (await self._read_hidden_grid(page)).strip()
            if not raw or raw in ("[]", "[[]]"):
                return pd.DataFrame()
            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                return pd.DataFrame()
            num_cols = len(data[0]) if isinstance(data[0], list) else 0
            logging.info(f"[DUAs] {len(data)} filas en Grid1ContainerDataV")
            try:
                await page.wait_for_selector("#Grid1ContainerTbl", timeout=t, state="attached")
                ths = await page.query_selector_all("#Grid1ContainerTbl thead tr th")
                headers = [(await th.text_content() or "").strip().replace("\xa0", " ") for th in ths]
            except Exception:
                headers = []
            if not headers:
                headers = [f"Col_{i+1}" for i in range(num_cols)]
            elif len(headers) < num_cols:
                headers += [f"Col_{i+1}" for i in range(len(headers), num_cols)]
            else:
                headers = headers[:num_cols]
            df = pd.DataFrame(data, columns=headers[:num_cols])
            df["manifiesto"] = manifest_id
            return df
        except Exception as e:
            logging.error(f"[DUAs] Error extrayendo tabla: {e}")
            return pd.DataFrame()

    async def _fetch_dua_result(self, href: str, row_index: int, row_info: dict):
        sub_page: Page | None = None
        try:
            sub_page = await self._open_sub_page(href)
            try:
                await sub_page.wait_for_selector("body", timeout=self.timeout * 1000)
            except Exception:
                return None, f"[fila {row_index}] Timeout cargando pagina DUAs"
            manifest_id = await self.obtener_identificador_manifiesto(sub_page)
            if not manifest_id:
                return None, f"[fila {row_index}] No se pudo determinar el identificador"
            df = await self.extract_duas_table(sub_page, manifest_id)
            if df.empty:
                return None, f"[fila {row_index}] Tabla DUAs vacia ({manifest_id})"
            return df, None
        except Exception as e:
            return None, f"[fila {row_index}] {e}"
        finally:
            if sub_page:
                try:
                    await sub_page.close()
                except Exception:
                    pass

    async def process_duas_links(self):
        page = self.page
        try:
            await self.wait_for_results_table(page, self.timeout)
        except Exception:
            logging.warning("[DUAs] No se encontro la tabla de resultados.")
            return
        ths = await page.query_selector_all("#Grid1ContainerTbl thead tr th")
        headers = [(await th.text_content() or "").strip().replace("\xa0", " ") for th in ths]
        row_data = await self._snapshot_main_table_links(page, "a[href^='hcgduama.aspx']", headers)
        logging.info(f"[DUAs] {len(row_data)} filas en tabla.")

        sem = asyncio.Semaphore(self.config.get("max_concurrent_pages", 5))

        async def bounded(h, i, ri):
            async with sem:
                return await self._fetch_dua_result(h, i, ri)

        indices, row_infos, coros = [], [], []
        for idx, item in enumerate(row_data, start=1):
            if item is None:
                continue
            href, row_info = item
            indices.append(idx)
            row_infos.append(row_info)
            coros.append(bounded(href, idx, row_info))

        if not coros:
            return

        results = await asyncio.gather(*coros, return_exceptions=True)

        all_dfs = []
        for orig_idx, ri, result in zip(indices, row_infos, results):
            if isinstance(result, Exception):
                self.register_dua_failure(ri, str(result), row_index=orig_idx)
            else:
                df, reason = result
                if reason:
                    self.register_dua_failure(ri, reason, row_index=orig_idx)
                elif df is not None and not df.empty:
                    all_dfs.append(df)

        if not all_dfs:
            logging.info("[DUAs] Sin datos validos para guardar.")
            return

        combined = pd.concat(all_dfs, ignore_index=True)
        start = self.duas_index_counter + 1
        end = start + len(combined) - 1
        combined.insert(0, "index_flujo_duas", range(start, end + 1))
        self.duas_index_counter = end
        fe = os.path.exists(self.duas_output_path)
        combined.to_csv(self.duas_output_path, mode="a" if fe else "w",
                        header=not fe, index=False, encoding="utf-8-sig")
        logging.info(f"[DUAs] {len(combined)} filas guardadas (index {start}-{end}). "
                     f"{len(indices) - len(all_dfs)} fallidas de {len(indices)}.")

    async def run_duas_for_mode(self, mode: str, month: int, year: int):
        return await self.run_tracked_table('duas', mode, month, year)

    # ── Flow 3: Movimientos ────────────────────────────────────────────────────

    def init_mov_output(self, mode: str, month: int, year: int):
        folder = self.config.get("output_manifest_movimientos_folder", "output_manifest_movimientos")
        os.makedirs(folder, exist_ok=True)
        self.mov_output_path = os.path.join(folder, f"movimientos_{mode}_{year:04d}_{month:02d}.csv")
        self.mov_failed_output_path = os.path.join(folder, f"movimientos_fallidos_{mode}_{year:04d}_{month:02d}.csv")
        self.mov_index_counter = 0
        self.mov_failed_rows = []
        if os.path.exists(self.mov_output_path):
            try:
                existing = pd.read_csv(self.mov_output_path)
                if "index_flujo_movimientos" in existing.columns and not existing.empty:
                    self.mov_index_counter = int(existing["index_flujo_movimientos"].max())
                    logging.info(f"[MOV] CSV existente. Último index={self.mov_index_counter}")
            except Exception as e:
                logging.warning(f"[MOV] No se pudo leer CSV existente: {e}")

    def register_mov_failure(self, row_info: dict, reason: str, manifest_id: str = "", row_index: int = None):
        data = dict(row_info) if row_info else {}
        if manifest_id:
            data["manifiesto_pagina_movimientos"] = manifest_id
        if row_index is not None:
            data["fila_origen"] = row_index
        data["motivo_fallo"] = reason
        self.mov_failed_rows.append(data)
        if not self.mov_failed_output_path:
            return
        try:
            df = pd.DataFrame([data])
            fe = os.path.exists(self.mov_failed_output_path)
            df.to_csv(self.mov_failed_output_path, mode="a" if fe else "w",
                      header=not fe, index=False, encoding="utf-8-sig")
            logging.warning(f"[MOV] Fila fallida {row_index}: {reason}")
        except Exception as e:
            logging.error(f"[MOV] Error guardando fallo: {e}")

    def write_mov_failures(self):
        if not self.mov_failed_rows or not self.mov_failed_output_path:
            logging.info("[MOV] No hay filas fallidas.")
            return
        df = pd.DataFrame(self.mov_failed_rows)
        fe = os.path.exists(self.mov_failed_output_path)
        try:
            df.to_csv(self.mov_failed_output_path, mode="a" if fe else "w",
                      header=not fe, index=False, encoding="utf-8-sig")
            logging.info(f"[MOV] {len(df)} filas fallidas escritas.")
        except Exception as e:
            logging.error(f"[MOV] Error escribiendo CSV fallos: {e}")

    async def extract_movimientos_table(self, page: Page, manifest_id: str) -> pd.DataFrame:
        t = self.timeout * 1000
        try:
            await page.wait_for_selector('[name="Grid1ContainerDataV"]', timeout=t, state="attached")
            raw = (await self._read_hidden_grid(page)).strip()
            if not raw or raw in ("[]", "[[]]"):
                return pd.DataFrame()
            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                return pd.DataFrame()
            num_cols = len(data[0]) if isinstance(data[0], list) else 0
            logging.info(f"[MOV] {len(data)} filas en Grid1ContainerDataV")
            try:
                ths = await page.query_selector_all("#Grid1ContainerTbl thead tr th")
                headers = [(await th.text_content() or "").strip().replace("\xa0", " ") for th in ths]
            except Exception:
                headers = []
            if not headers:
                headers = [f"Col_{i+1}" for i in range(num_cols)]
            elif len(headers) < num_cols:
                headers += [f"Col_{i+1}" for i in range(len(headers), num_cols)]
            else:
                headers = headers[:num_cols]
            df = pd.DataFrame(data, columns=headers[:num_cols])
            df["manifiesto"] = manifest_id
            return df
        except Exception as e:
            logging.error(f"[MOV] Error extrayendo tabla: {e}")
            return pd.DataFrame()

    async def _fetch_mov_result(self, href: str, row_index: int, row_info: dict):
        sub_page: Page | None = None
        try:
            sub_page = await self._open_sub_page(href)
            try:
                await sub_page.wait_for_selector("body", timeout=self.timeout * 1000)
            except Exception:
                return None, f"[fila {row_index}] Timeout cargando pagina Movimientos"
            manifest_id = await self.obtener_identificador_manifiesto(sub_page)
            if not manifest_id:
                return None, f"[fila {row_index}] No se pudo determinar el identificador"
            df = await self.extract_movimientos_table(sub_page, manifest_id)
            if df.empty:
                return None, f"[fila {row_index}] Tabla Movimientos vacia ({manifest_id})"
            return df, None
        except Exception as e:
            return None, f"[fila {row_index}] {e}"
        finally:
            if sub_page:
                try:
                    await sub_page.close()
                except Exception:
                    pass

    async def process_movimientos_links(self):
        page = self.page
        try:
            await self.wait_for_results_table(page, self.timeout)
        except Exception:
            logging.warning("[MOV] No se encontro la tabla de resultados.")
            return
        ths = await page.query_selector_all("#Grid1ContainerTbl thead tr th")
        headers = [(await th.text_content() or "").strip().replace("\xa0", " ") for th in ths]
        row_data = await self._snapshot_main_table_links(page, "a[href*='mov']", headers)
        logging.info(f"[MOV] {len(row_data)} filas en tabla.")

        sem = asyncio.Semaphore(self.config.get("max_concurrent_pages", 5))

        async def bounded(h, i, ri):
            async with sem:
                return await self._fetch_mov_result(h, i, ri)

        indices, row_infos, coros = [], [], []
        for idx, item in enumerate(row_data, start=1):
            if item is None:
                continue
            href, row_info = item
            indices.append(idx)
            row_infos.append(row_info)
            coros.append(bounded(href, idx, row_info))

        if not coros:
            return

        results = await asyncio.gather(*coros, return_exceptions=True)

        all_dfs = []
        for orig_idx, ri, result in zip(indices, row_infos, results):
            if isinstance(result, Exception):
                self.register_mov_failure(ri, str(result), row_index=orig_idx)
            else:
                df, reason = result
                if reason:
                    self.register_mov_failure(ri, reason, row_index=orig_idx)
                elif df is not None and not df.empty:
                    all_dfs.append(df)

        if not all_dfs:
            logging.info("[MOV] Sin datos validos para guardar.")
            return

        combined = pd.concat(all_dfs, ignore_index=True)
        start = self.mov_index_counter + 1
        end = start + len(combined) - 1
        combined.insert(0, "index_flujo_movimientos", range(start, end + 1))
        self.mov_index_counter = end
        fe = os.path.exists(self.mov_output_path)
        combined.to_csv(self.mov_output_path, mode="a" if fe else "w",
                        header=not fe, index=False, encoding="utf-8-sig")
        logging.info(f"[MOV] {len(combined)} filas guardadas (index {start}-{end}). "
                     f"{len(indices) - len(all_dfs)} fallidas de {len(indices)}.")

    async def run_movimientos_for_mode(self, mode: str, month: int, year: int):
        return await self.run_tracked_table('movimientos', mode, month, year)

    # ── Flow 4: Conocimientos ──────────────────────────────────────────────────

    # Implementado en ConocimientosFlow.

    # ── Flow 5: Contenedores ───────────────────────────────────────────────────

    def init_cont_output(self, mode: str, month: int, year: int):
        from organizar_resultados import organize_results
        organize_results(self.config, only=('contenedores', mode, month, year))
        paths = output_paths(self.config, 'contenedores', mode, month, year)
        self.cont_output_path = str(paths.csv)
        self.cont_failed_output_path = str(paths.failures)
        paths.failures.parent.mkdir(parents=True, exist_ok=True)
        self.cont_index_counter = 0
        self.cont_failed_rows = []
        if os.path.exists(self.cont_output_path):
            try:
                existing = pd.read_csv(self.cont_output_path)
                if "index_flujo_contenedores" in existing.columns and not existing.empty:
                    self.cont_index_counter = int(existing["index_flujo_contenedores"].max())
                    logging.info(f"[CONT] CSV existente. Último index={self.cont_index_counter}")
            except Exception as e:
                logging.warning(f"[CONT] No se pudo leer CSV existente: {e}")

    def register_cont_failure(self, row_info: dict, reason: str, manifest_id: str = "", row_index: int = None):
        data = dict(row_info) if row_info else {}
        if manifest_id:
            data["manifiesto_pagina_contenedores"] = manifest_id
        if row_index is not None:
            data["fila_origen"] = row_index
        data["motivo_fallo"] = reason
        self.cont_failed_rows.append(data)
        if not self.cont_failed_output_path:
            return
        try:
            df = pd.DataFrame([data])
            fe = os.path.exists(self.cont_failed_output_path)
            df.to_csv(self.cont_failed_output_path, mode="a" if fe else "w",
                      header=not fe, index=False, encoding="utf-8-sig")
            logging.warning(f"[CONT] Fila fallida {row_index}: {reason}")
        except Exception as e:
            logging.error(f"[CONT] Error guardando fallo: {e}")

    def write_cont_failures(self):
        if not self.cont_failed_rows or not self.cont_failed_output_path:
            logging.info("[CONT] No hay filas fallidas.")
            return
        df = pd.DataFrame(self.cont_failed_rows)
        fe = os.path.exists(self.cont_failed_output_path)
        try:
            df.to_csv(self.cont_failed_output_path, mode="a" if fe else "w",
                      header=not fe, index=False, encoding="utf-8-sig")
            logging.info(f"[CONT] {len(df)} filas fallidas escritas.")
        except Exception as e:
            logging.error(f"[CONT] Error escribiendo CSV fallos: {e}")

    async def _apply_contenedores_filter_llenos(self, page: Page):
        await page.wait_for_selector("#vCGLLENVAC", timeout=5_000)
        await page.select_option("#vCGLLENVAC", "1")
        logging.info("[CONT] Filtro Llenos aplicado.")
        await page.click('[name="BTN_ENTER1"]')
        try:
            await page.wait_for_selector("#span_vTOTALCONTENEDORES", timeout=3_000)
        except Exception:
            pass

    async def _is_contenedores_empty_fast(self, page: Page) -> bool:
        try:
            total_txt = (await page.text_content("#span_vTOTALCONTENEDORES") or "").replace("\xa0", " ").strip()
            if total_txt and int(total_txt) == 0:
                return True
        except Exception:
            pass
        try:
            raw = await self._read_hidden_grid(page)
            if raw in ("[]", "", "null", "NULL"):
                return True
        except Exception:
            pass
        try:
            rows = await page.query_selector_all('#Grid1ContainerTbl tbody tr[id^="Grid1ContainerRow_"]')
            return len(rows) == 0
        except Exception:
            return True

    async def _read_contenedores_rows(self, page: Page) -> list[dict]:
        try:
            await page.wait_for_selector("#Grid1ContainerTbl", timeout=5_000)
        except Exception:
            return []
        return await page.evaluate("""() => {
            const rows = document.querySelectorAll('#Grid1ContainerTbl tbody tr[id^="Grid1ContainerRow_"]');
            return Array.from(rows).map(row => {
                const tds = row.querySelectorAll('td');
                const td = i => tds[i] ? tds[i].textContent.trim() : '';
                const a = tds[0] ? tds[0].querySelector('a[href^="hcgkonli.aspx"]') : null;
                return {
                    merc_href: a ? a.href : '',
                    base: {
                        Contenedor: td(1), Calificador: td(2), Tamano: td(3),
                        PesoContenedor: td(4), Viaje: td(5), EstadoViaje: td(6),
                        LlenoVacio: td(7), Marchamo1: td(8), Destino: td(17),
                        EstadoContenedor: td(18), DepositoRevision: td(20)
                    }
                };
            });
        }""") or []

    async def extract_mercancia_table(self, page: Page, manifest_id: str) -> pd.DataFrame:
        t = self.timeout * 1000
        try:
            await page.wait_for_selector('[name="Grid1ContainerDataV"]', timeout=t, state="attached")
            raw = (await self._read_hidden_grid(page)).strip()
        except Exception:
            return pd.DataFrame()
        if not raw or raw in ("[]", "[[]]"):
            return pd.DataFrame()
        try:
            data = json.loads(raw)
        except Exception as e:
            logging.error(f"[CONT] Error parseando mercancía JSON: {e}")
            return pd.DataFrame()
        if not isinstance(data, list) or not data:
            return pd.DataFrame()
        cols = ["BLOriginal", "SecuenciaTica", "Linea", "ContenedorMerc", "Bultos", "Tipo", "EstadoMercancia"]
        df = pd.DataFrame(data, columns=cols[:len(data[0])])
        df.insert(0, "IDManifiesto", manifest_id)
        return df

    async def _fetch_cont_result(self, href: str, row_index: int, row_info: dict):
        cont_page: Page | None = None
        try:
            cont_page = await self._open_sub_page(href)
            try:
                await cont_page.wait_for_selector("body", timeout=self.timeout * 1000)
            except Exception:
                return None, f"[fila {row_index}] Timeout cargando pagina Contenedores"
            manifest_id = await self.obtener_identificador_manifiesto(cont_page)
            if not manifest_id:
                return None, f"[fila {row_index}] No se pudo determinar el identificador"
            try:
                await self._apply_contenedores_filter_llenos(cont_page)
                if await self._is_contenedores_empty_fast(cont_page):
                    return pd.DataFrame(), None  # sin llenos, no es falla
            except Exception as e:
                return None, f"Error aplicando filtro Llenos: {e}"
            try:
                cont_rows = await self._read_contenedores_rows(cont_page)
            except Exception as e:
                return None, f"Error leyendo grid: {e}"
            if not cont_rows:
                return None, "Grid contenedores vacio (Llenos)"

            all_out = []
            for item in cont_rows:
                merc_href = item["merc_href"]
                base = dict(item["base"])
                base["IDManifiesto"] = manifest_id
                if not merc_href:
                    continue
                df_m = pd.DataFrame()
                merc_page: Page | None = None
                try:
                    merc_page = await self._open_sub_page(merc_href)
                    df_m = await self.extract_mercancia_table(merc_page, manifest_id)
                except Exception:
                    pass
                finally:
                    if merc_page:
                        try:
                            await merc_page.close()
                        except Exception:
                            pass
                if df_m is None or df_m.empty:
                    continue
                df_base = pd.DataFrame([base] * len(df_m))
                merged = pd.concat([df_base.reset_index(drop=True), df_m.reset_index(drop=True)], axis=1)
                merged = merged.rename(columns={"ContenedorMerc": "ContenedorMercancia"})
                for c in self.CONT_OUT_COLS:
                    if c not in merged.columns:
                        merged[c] = ""
                all_out.append(merged[self.CONT_OUT_COLS])

            if not all_out:
                return None, f"[fila {row_index}] Sin filas generadas (mercancia vacia o sin links)"
            return pd.concat(all_out, ignore_index=True), None
        except Exception as e:
            return None, f"[fila {row_index}] {e}"
        finally:
            if cont_page:
                try:
                    await cont_page.close()
                except Exception:
                    pass

    async def process_contenedores_links(self):
        page = self.page
        try:
            await self.wait_for_results_table(page, self.timeout)
        except Exception:
            logging.warning("[CONT] No se encontro la tabla de resultados.")
            return
        desired = ["Trans.", "Ing Sal", "Manifiesto", "Cod Ubicacion", "Ubicacion", "Aduana", "Fecha"]
        raw = await page.evaluate(
            """(desired) => {
                const hdrs = Array.from(
                    document.querySelectorAll('#Grid1ContainerTbl thead tr th')
                ).map(th => th.textContent.replace(/\\u00a0/g, ' ').trim());
                return Array.from(
                    document.querySelectorAll('#Grid1ContainerTbl tbody tr')
                ).map(row => {
                    let link = row.querySelector("a[href^='hcgkonte.aspx']");
                    if (!link) {
                        const img = row.querySelector("img[id^='vVCONTE_']");
                        if (img) link = img.closest('a');
                    }
                    if (!link) return null;
                    const tds = Array.from(row.querySelectorAll('td'))
                                     .map(td => td.textContent.trim());
                    const info = {};
                    desired.forEach(col => {
                        const i = hdrs.indexOf(col);
                        if (i >= 0 && i < tds.length) info[col] = tds[i];
                    });
                    return [link.href, info];
                });
            }""",
            desired,
        )
        row_data = [tuple(item) if item is not None else None for item in raw]
        logging.info(f"[CONT] {len(row_data)} filas en tabla.")

        sem = asyncio.Semaphore(self.config.get("max_concurrent_pages", 5))

        async def bounded(h, i, ri):
            async with sem:
                return await self._fetch_cont_result(h, i, ri)

        indices, row_infos, coros = [], [], []
        for idx, item in enumerate(row_data, start=1):
            if item is None:
                continue
            href, row_info = item
            indices.append(idx)
            row_infos.append(row_info)
            coros.append(bounded(href, idx, row_info))

        if not coros:
            return

        results = await asyncio.gather(*coros, return_exceptions=True)

        all_dfs = []
        for orig_idx, ri, result in zip(indices, row_infos, results):
            if isinstance(result, Exception):
                self.register_cont_failure(ri, str(result), row_index=orig_idx)
            else:
                df, reason = result
                if reason:
                    self.register_cont_failure(ri, reason, row_index=orig_idx)
                elif df is not None and not df.empty:
                    all_dfs.append(df)

        if not all_dfs:
            logging.info("[CONT] Sin datos validos para guardar.")
            return

        combined = pd.concat(all_dfs, ignore_index=True)
        start = self.cont_index_counter + 1
        end = start + len(combined) - 1
        combined.insert(0, "index_flujo_contenedores", range(start, end + 1))
        self.cont_index_counter = end
        fe = os.path.exists(self.cont_output_path)
        combined.to_csv(self.cont_output_path, mode="a" if fe else "w",
                        header=not fe, index=False, encoding="utf-8-sig")
        logging.info(f"[CONT] {len(combined)} filas guardadas (index {start}-{end}). "
                     f"{len(indices) - len(all_dfs)} fallidas de {len(indices)}.")

    async def run_contenedores_for_mode(self, mode: str, month: int, year: int):
        logging.info(f"[CONT] Iniciando: modo={mode}, mes={month}, año={year}")
        try:
            self.init_cont_output(mode, month, year)
            await self.open_page()
            await self.set_filters(mode, month, year)
            await self.submit_form()
            await self.process_contenedores_links()
            self.write_cont_failures()
        except Exception as e:
            logging.exception(f"[CONT] Error: {e}")
        finally:
            logging.info(f"[CONT] Finalizado modo={mode}")


# ── Module-level async entry points ───────────────────────────────────────────

def _launch_browser_and_run(coro_factory, config: dict, log_key: str, default_log: str):
    setup_logging(config.get(log_key, default_log))
    headless = config.get("headless", False)

    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=headless)
            logging.info(f"Chromium iniciado (headless={headless})")
            try:
                await coro_factory(browser)
            finally:
                await browser.close()
                logging.info("Chromium cerrado.")

    asyncio.run(_run())


async def run_manifest_bot(modes, month: int, year: int):
    config = load_config()
    setup_logging(config.get("log_file", "logs/manifest_bot.log"))
    headless = config.get("headless", False)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        logging.info(f"Chromium iniciado (headless={headless})")
        try:
            for mode in modes:
                mode = mode.lower()
                if mode not in ManifestScraper.MODE_MAP:
                    logging.warning(f"Modo desconocido: {mode}. Omitido.")
                    continue
                from organizar_resultados import organize_results
                organize_results(config, only=('tabla', mode, month, year))
                output_path = str(output_paths(config, 'tabla', mode, month, year).csv)
                logging.info(f"=== Ciclo modo={mode} ===")
                scraper = ManifestScraper(config, browser)
                await scraper.run_for_mode(mode, month, year, output_path)
        finally:
            await browser.close()
            logging.info("Chromium cerrado.")


async def _run_tracked_bot(flow, modes, month, year, config_overrides=None):
    config = load_config()
    config.update(config_overrides or {})
    setup_logging(config.get('log_file_' + flow, 'logs/manifest_bot_' + flow + '.log'))
    summaries = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.get('headless', False))
        try:
            for mode in modes:
                mode = mode.lower()
                if mode not in ManifestScraper.MODE_MAP:
                    continue
                scraper = ManifestScraper(config, browser, request_factory=pw.request)
                await scraper.run_tracked_table(flow, mode, month, year)
                summaries.append({'mode': mode, **scraper.conoc_progress})
            return summaries
        finally:
            await browser.close()


async def run_manifest_duas_bot(modes, month: int, year: int, config_overrides=None):
    return await _run_tracked_bot('duas', modes, month, year, config_overrides)


async def run_manifest_movimientos_bot(modes, month: int, year: int, config_overrides=None):
    return await _run_tracked_bot('movimientos', modes, month, year, config_overrides)


async def run_manifest_conocimientos_bot(modes, month: int, year: int, config_overrides=None):
    config = load_config()
    config.update(config_overrides or {})
    setup_logging(config.get("log_file_conocimientos", "logs/manifest_bot_conocimientos.log"))
    headless = config.get("headless", False)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        logging.info(f"Chromium iniciado (headless={headless})")
        summaries = []
        try:
            for mode in modes:
                mode = mode.lower()
                if mode not in ManifestScraper.MODE_MAP:
                    logging.warning(f"[CONS] Modo desconocido: {mode}. Omitido.")
                    continue
                logging.info(f"[CONS] === Ciclo modo={mode} ===")
                scraper = ManifestScraper(config, browser)
                await scraper.run_conocimientos_for_mode(mode, month, year)
                summaries.append({'mode': mode, **scraper.conoc_progress})
            return summaries
        finally:
            await browser.close()
            logging.info("[CONS] Chromium cerrado.")


async def run_manifest_contenedores_bot(modes, month: int, year: int):
    config = load_config()
    setup_logging(config.get("log_file_contenedores", "logs/manifest_bot_contenedores.log"))
    headless = config.get("headless", False)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        logging.info(f"Chromium iniciado (headless={headless})")
        try:
            for mode in modes:
                mode = mode.lower()
                if mode not in ManifestScraper.MODE_MAP:
                    logging.warning(f"[CONT] Modo desconocido: {mode}. Omitido.")
                    continue
                logging.info(f"[CONT] === Ciclo modo={mode} ===")
                scraper = ManifestScraper(config, browser)
                await scraper.run_contenedores_for_mode(mode, month, year)
        finally:
            await browser.close()
            logging.info("[CONT] Chromium cerrado.")
