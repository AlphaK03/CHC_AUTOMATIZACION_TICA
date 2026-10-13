"""xmovimientos_flow.py — Flujo para consultar los MOVIMIENTOS de una DUA en el portal TICA.

Implementa BaseFlow para la URL:
    https://ticaconsultas.hacienda.go.cr/Tica/hcimppon.aspx

Navegación:
  1. Formulario principal (Aduana / Año / Número / CAPTCHA) → click MANAERMAR
  2. Espera la tabla SubstkContainerTbl (resultados de movimientos)
  3. Extrae las filas: Deposito, Año, Movimiento, Tipo_de_Movimiento,
     Cantidad_de_Bultos_asociada — agrupa y suma por combinación única.

Diferencias respecto a DetallesFlow:
  - Botón: MANAERMAR (no DETALLE)
  - No hay página intermedia — la tabla aparece directamente
  - Retorna múltiples filas por DUA (una por movimiento)
"""
import logging

import pandas as pd
from bs4 import BeautifulSoup

from flows.base_flow import BaseFlow


class NoMovimientosError(Exception):
    """DUA válido pero sin filas en la tabla de movimientos."""


class XMovimientosFlow(BaseFlow):

    _START_URL = 'https://ticaconsultas.hacienda.go.cr/Tica/hcimppon.aspx'

    @staticmethod
    def _clean(text: str) -> str:
        """Elimina caracteres que rompen el CSV: saltos de línea, tabulaciones, comas y punto y coma."""
        import re
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = text.replace(',', ' ')
        text = text.replace(';', ' ')
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    @property
    def start_url(self) -> str:
        return self._START_URL

    def extract_data(self, page_source: str) -> pd.DataFrame:
        soup = BeautifulSoup(page_source, 'html.parser')

        # ── Número del DUA ────────────────────────────────────────────────
        codigo_el = soup.find('span', id='span_CODI_ADUAN')
        ano_el    = soup.find('span', id='span_ANO_PRESE')
        numero_el = soup.find('span', id='span_NUME_CORRE')

        if not all([codigo_el, ano_el, numero_el]):
            raise ValueError("No se pudo extraer el número del DUA de la página.")

        numero_del_dua = (
            f"{codigo_el.get_text(strip=True)}-"
            f"{ano_el.get_text(strip=True)}-"
            f"{numero_el.get_text(strip=True)}"
        )

        # ── Tabla de movimientos ──────────────────────────────────────────
        table = soup.find('table', {'id': 'SubstkContainerTbl'})
        if table is None:
            raise ValueError(
                f"Tabla 'SubstkContainerTbl' no encontrada para DUA {numero_del_dua}."
            )

        rows = table.find_all('tr')[1:]  # Omitir fila de encabezado
        if not rows:
            raise NoMovimientosError(numero_del_dua)

        extracted = []
        for tr in rows:
            cols = tr.find_all('td')
            if len(cols) < 5:
                logging.warning("Fila con menos de 5 columnas omitida en DUA %s.", numero_del_dua)
                continue
            extracted.append({
                'Deposito':                    self._clean(cols[0].get_text(strip=True)),
                'Año':                         self._clean(cols[1].get_text(strip=True)),
                'Movimiento':                  self._clean(cols[2].get_text(strip=True)),
                'Tipo_de_Movimiento':          self._clean(cols[3].get_text(strip=True)),
                'Cantidad_de_Bultos_asociada': cols[4].get_text(strip=True),  # comas = separador de miles, se limpian más adelante
                'numero_del_dua':              numero_del_dua,
            })

        if not extracted:
            raise ValueError(f"DUA {numero_del_dua}: no se extrajeron filas válidas de la tabla.")

        df = pd.DataFrame(extracted)

        # Convertir cantidad a float (el portal usa comas como separador de miles)
        df['Cantidad_de_Bultos_asociada'] = (
            df['Cantidad_de_Bultos_asociada']
            .str.replace(',', '', regex=False)
            .astype(float)
        )

        # Agrupar y sumar bultos por combinación única de movimiento
        df = df.groupby(
            ['Deposito', 'Año', 'Movimiento', 'Tipo_de_Movimiento', 'numero_del_dua'],
            as_index=False,
        ).agg({'Cantidad_de_Bultos_asociada': 'sum'})

        return df
