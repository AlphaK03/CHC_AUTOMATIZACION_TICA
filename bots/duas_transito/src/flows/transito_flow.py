# src/flows/transito_flow.py

import logging

import pandas as pd
from bs4 import BeautifulSoup

from flows.base_flow import BaseFlow


class NoRowsException(Exception):
    """DUA válido pero sin filas en la tabla de líneas/tránsito."""


class XTransitoFlow(BaseFlow):
    _START_URL = 'https://ticaconsultas.hacienda.go.cr/Tica/hcimppon.aspx'

    @property
    def start_url(self) -> str:
        return self._START_URL

    def extract_data(self, page_source: str) -> pd.DataFrame:
        soup = BeautifulSoup(page_source, 'html.parser')

        cod_aduan_el = soup.find('span', id='span_CODI_ADUAN')
        ano_prese_el = soup.find('span', id='span_ANO_PRESE')
        nume_corre_el = soup.find('span', id='span_NUME_CORRE')

        if not all([cod_aduan_el, ano_prese_el, nume_corre_el]):
            raise ValueError("No se pudo extraer el número del DUA desde la página.")

        numero_del_dua = (
            f"{cod_aduan_el.get_text(strip=True)}-"
            f"{ano_prese_el.get_text(strip=True)}-"
            f"{nume_corre_el.get_text(strip=True)}"
        )

        table = soup.find('table', {'id': 'SeriesContainerTbl'})
        if table is None:
            raise ValueError(f"Tabla 'SeriesContainerTbl' no encontrada para DUA {numero_del_dua}.")

        rows = table.find_all('tr')
        if not rows:
            raise NoRowsException(numero_del_dua)

        extracted = self._parse_lineas_table(rows, numero_del_dua)

        if not extracted:
            raise NoRowsException(numero_del_dua)

        df = pd.DataFrame(extracted)
        df = df.astype(str).replace(r'[\n\r\t]+', ' ', regex=True)
        df = df.apply(lambda col: col.str.strip())
        return df

    @staticmethod
    def _clean(text: str) -> str:
        """Elimina caracteres que rompen el CSV: saltos de línea, tabulaciones, comas y punto y coma."""
        import re
        text = re.sub(r'[\n\r\t]+', ' ', text)   # saltos de línea → espacio
        text = text.replace(',', ' ')              # comas → espacio
        text = text.replace(';', ' ')              # punto y coma → espacio
        text = re.sub(r' {2,}', ' ', text)        # espacios múltiples → uno solo
        return text.strip()

    def _parse_lineas_table(self, rows, numero_del_dua: str) -> list[dict]:
        extracted = []

        for row in rows:
            if not row.get('id', '').startswith("SeriesContainerRow_"):
                continue

            cells = row.find_all('td')
            if len(cells) < 13:
                continue

            extracted.append({
                "Item":                          self._clean(cells[0].get_text(strip=True)),
                "Partida":                       self._clean(cells[1].get_text(strip=True)),
                "Descripción_Comercial":         self._clean(cells[3].get_text(strip=True)),
                "Bultos":                        self._clean(cells[4].get_text(strip=True)),
                "Tipo_de_Bulto":                 self._clean(cells[5].get_text(strip=True)),
                "Nombre_del_consignatario":      self._clean(cells[6].get_text(strip=True)),
                "Declaración_de_origen_de_China": self._clean(cells[12].get_text(strip=True)),
                "numero_del_dua":                numero_del_dua,
            })

        return extracted