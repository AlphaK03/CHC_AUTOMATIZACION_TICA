"""
data_reader.py
Lectura textual de Excel, normalización de columnas y fechas de manifiesto.
"""

import re
import unicodedata
import pandas as pd

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def clean_col(s) -> str:
    """Normalize a column name: strip invisible chars, collapse spaces."""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\ufeff", "").replace("\xa0", " ")
    s = s.replace("\n", " ").replace("\t", " ")
    return " ".join(s.split()).strip()


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def parse_fecha_manifiesto(series: pd.Series) -> pd.Series:
    """
    Parse the 'Fecha Manifiesto' column.
    Accepts:
      - 'miércoles, 16 de abril de 2025'
      - '16 de abril de 2025'
      - '16/04/2025' or '2025-04-16'
    Returns datetime64[ns] (NaT where unparseable).
    """
    s = series.astype(str).fillna("").str.strip()

    # Try direct numeric formats first
    direct = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if direct.notna().all():
        return direct

    # Strip leading weekday "miércoles, "
    s2 = s.str.replace(r"^[^,]+,\s*", "", regex=True)
    s2 = s2.str.lower().map(_strip_accents)

    pat = re.compile(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})")
    out = []
    for position, val in enumerate(s2.tolist()):
        if pd.notna(direct.iloc[position]):
            out.append(direct.iloc[position])
            continue
        m = pat.search(val)
        if not m:
            out.append(pd.NaT)
            continue
        month = SPANISH_MONTHS.get(m.group(2))
        if not month:
            out.append(pd.NaT)
            continue
        out.append(pd.Timestamp(year=int(m.group(3)), month=month, day=int(m.group(1))))

    return pd.to_datetime(pd.Series(out, index=series.index), errors="coerce")


def leer_bls(file_path: str, sheet_name: str) -> pd.DataFrame:
    """
    Read an Excel sheet, normalize columns, parse dates, and split IDManifiesto.
    Returns a DataFrame ready for processing.
    Raises ValueError with a user-friendly message on any validation failure.
    """
    datos = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str, keep_default_na=False)
    return prepare_bls(datos)


def prepare_bls(datos: pd.DataFrame) -> pd.DataFrame:
    """Prepara las mismas columnas y fechas para Excel y la tabla BLS exportada."""
    datos = datos.copy()
    datos.columns = [clean_col(c) for c in datos.columns]
    if len(datos.columns) != len(set(datos.columns)):
        raise ValueError('La base tiene encabezados duplicados después de normalizarlos.')
    if datos.empty:
        raise ValueError('La hoja no contiene BL para procesar.')

    required = ["BL original", "IDManifiesto", "Fecha Manifiesto"]
    missing = [c for c in required if c not in datos.columns]
    if missing:
        raise ValueError(
            f"Faltan columnas requeridas: {missing}\n"
            f"Columnas encontradas: {list(datos.columns)}"
        )

    fecha_dt = parse_fecha_manifiesto(datos["Fecha Manifiesto"])
    if fecha_dt.isna().all():
        raise ValueError(
            "No se pudo interpretar ninguna fecha en la columna 'Fecha Manifiesto'.\n"
            "Formatos aceptados: '16/04/2025', '16 de abril de 2025', "
            "'miércoles, 16 de abril de 2025'."
        )
    datos["Fecha Manifiesto"] = fecha_dt.dt.strftime("%d/%m/%Y")

    ids = datos["IDManifiesto"].astype(str).str.split("-", expand=True)
    if ids.shape[1] < 5:
        raise ValueError(
            "La columna 'IDManifiesto' no tiene el formato esperado.\n"
            "Se requieren al menos 5 partes separadas por '-' "
            "(ejemplo: PART0-PART1-PART2-PART3-PART4)."
        )
    datos["ID2"] = ids[1]
    datos["ID3"] = ids[2]
    datos["ID4"] = ids[3]

    return datos
