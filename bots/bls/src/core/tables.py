"""Lectura textual de tablas TICA y rechazo de respuestas incompletas."""
import json
import re

from bs4 import BeautifulSoup


class InvalidResponse(ValueError):
    pass


DETAIL_COLUMNS = ['Contenedor Asociado', 'Pendientes', 'Afectaciones', 'Sob/ Falt', 'Retenciones',
                  'Nro', 'Peso', 'Tipo de Bulto', 'Total de Bulto', 'Usado', 'Dep.Dest.',
                  'Ubicacion', 'Aduana', 'Marcas', 'Estado', 'Tipo de operación', 'Categoria',
                  'Cod. Mercancia Peligrosa']
DETAIL_FIELDS = ['vVLINKON', 'vVPEND', 'vVAFEC', 'vSOBFAL', 'vRET', 'CGNROLIN', 'vCGDESC',
                 'CGLINPESBRU', 'CGLINTIPBUL', 'CGLINTOTBUL', 'CGLINBULUSA', 'CGLINDEP',
                 'vVUBICACION', 'vCOD_ADUANA', 'CGMARCLIN', 'CGLINEST', 'vTPOOPERACION',
                 'CGLITPOOPER', 'CGTPOENV', 'CGCODSUSPEL']


def table_data(html, table_id=None, include_hidden=False):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id=table_id) if table_id else soup.find('table')
    if table is None:
        raise InvalidResponse(f'La respuesta no contiene la tabla {table_id or "esperada"}')
    rows = table.find_all('tr', recursive=False)
    if not rows:
        # HTML serializado por el navegador introduce tbody; no tomar tablas anidadas.
        rows = [row for row in table.find_all('tr') if row.find_parent('table') is table]
    columns, data, links = None, [], []
    for row in rows:
        cells = row.find_all(['th', 'td'], recursive=False)
        if not include_hidden:
            cells = [cell for cell in cells if not re.search(r'display\s*:\s*none', cell.get('style', ''), re.I)]
        if not cells:
            continue
        if any(int(cell.get('rowspan', 1)) != 1 or int(cell.get('colspan', 1)) != 1 for cell in cells):
            raise InvalidResponse('La tabla cambió su estructura de columnas')
        values = [cell.get_text(' ', strip=True) for cell in cells]
        if columns is None:
            columns = values
            if not any(columns):
                raise InvalidResponse('Encabezados vacíos')
            if len(set(columns)) != len(columns):
                raise InvalidResponse('Encabezados duplicados')
            continue
        if all(cell.name == 'th' for cell in cells) and values == columns:
            continue
        if len(values) != len(columns):
            raise InvalidResponse('Fila con cantidad de columnas incompatible')
        data.append(values)
        link = row.find(id=lambda value: bool(value and value.startswith('vVLIN_')))
        anchor = link if link and link.name == 'a' else link.find_parent('a') if link else None
        links.append({'id': link.get('id'), 'href': anchor.get('href') if anchor else None} if link else None)
    if columns is None:
        raise InvalidResponse('La tabla no contiene encabezados')
    return columns, data, links


def parse_search(data, record, dates):
    try:
        hidden = data['gxHiddens']
        if (hidden['GXH_vCGNROCON'] != record['BL original'] or
            (hidden['GXH_vVFCH1'], hidden['GXH_vVFCHF']) != dates):
            raise InvalidResponse('La respuesta AJAX corresponde a otros filtros o BL')
        rows = json.loads(hidden['Grid2ContainerDataV'])
        grid = next(grid for grid in data['gxGrids'] if grid['GridName'] == 'Grid2')
        count = int(hidden['nRC_Grid2'])
        if count != len(rows) or int(grid['Count']) != count:
            raise InvalidResponse('Cantidad de filas de búsqueda incompatible')
        target = record['IDManifiesto'].split('-')
        selected, manifests = [], []
        for index, row in enumerate(rows):
            if len(row) != 24:
                raise InvalidResponse('Cambió el esquema de la búsqueda BL')
            manifests.append('-'.join(row[:5]))
            if row[:5] != target or row[8] != record['BL original']:
                continue
            if record.get('Secuencia Tica') and int(row[7]) != int(record['Secuencia Tica']):
                continue
            props = grid[str(index)]['Props']
            candidates = [prop for prop in props if isinstance(prop, list) and prop and
                          isinstance(prop[0], str) and prop[0].startswith('vVLIN_')]
            if len(candidates) != 1 or len(candidates[0]) < 2 or not candidates[0][1]:
                raise InvalidResponse('Falta el enlace confirmado de líneas del BL')
            selected.append({'id': candidates[0][0], 'href': candidates[0][1], 'sequence': row[7]})
        if len(selected) > 1:
            raise InvalidResponse('Más de una coincidencia exacta; falta una secuencia inequívoca')
        return selected[0] if selected else None, manifests
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        if isinstance(exc, InvalidResponse):
            raise
        raise InvalidResponse(f'Respuesta AJAX incompleta: {exc}') from exc


def parse_detail(html, record, sequence=None):
    try:
        soup = BeautifulSoup(html, 'html.parser')
        field = soup.find('input', attrs={'name': 'GXState'})
        if field is None:
            raise InvalidResponse('El detalle no contiene estado TICA')
        state = json.loads(field['value'])
        fields = ['CGTPOTRANS', 'CGTPOMIC', 'CGNROMIC', 'RGDEPID', 'CGFCHARR']
        identity = '-'.join(str(state[name]) for name in fields)
        if identity != record['IDManifiesto'] or state['CGNROCON'] != record['BL original']:
            raise InvalidResponse('El detalle pertenece a otro manifiesto o BL')
        wanted = sequence or record.get('Secuencia Tica')
        if wanted and int(state['CGNROCONDNA']) != int(wanted):
            raise InvalidResponse('La secuencia del detalle no coincide')
        count = int(state['nRC_Grid1'])
        grid = state['Grid1ContainerData']
        grid = json.loads(grid) if isinstance(grid, str) else grid
        raw_values = soup.find('input', attrs={'name': 'Grid1ContainerDataV'})
        if raw_values is None:
            raise InvalidResponse('Faltan los datos confirmados del detalle')
        raw = json.loads(raw_values['value'])
        if len(raw) != count or int(grid['Count']) != count or len(grid['Columns']) != 20:
            raise InvalidResponse('El detalle contiene filas incompletas o columnas inesperadas')
        if any(len(row) != 20 or any(not isinstance(value, str) for value in row) for row in raw):
            raise InvalidResponse('Cambió el esquema de los datos de líneas')
        if count:
            props = grid['0']['Props']
            if len(props) != 20 or [prop[0].rsplit('_', 1)[0] for prop in props] != DETAIL_FIELDS:
                raise InvalidResponse('Cambió la identidad de las columnas del detalle')
        visible = [index for index in range(20) if index not in (6, 17)]
        rows = [['' if index < 5 else row[index].strip() for index in visible] for row in raw]
        columns = DETAIL_COLUMNS
        if soup.find('table', id='Grid1ContainerTbl') is not None:
            dom_columns, dom_rows, _ = table_data(html, 'Grid1ContainerTbl')
            if dom_columns != columns or dom_rows != rows:
                raise InvalidResponse('El detalle dibujado difiere de sus datos confirmados')
        if len(columns) != 18:
            raise InvalidResponse('Cambió el esquema de las líneas del BL')
        return columns, rows
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, InvalidResponse):
            raise
        raise InvalidResponse(f'Detalle incompleto: {exc}') from exc
