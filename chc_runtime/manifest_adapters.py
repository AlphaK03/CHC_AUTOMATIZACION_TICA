"""Adaptadores nuevos; los extractores copiados se conservan byte a byte."""
import asyncio
import calendar
import csv
from datetime import datetime
import json
from pathlib import Path

from conocimientos import KnowledgeStore, IncompleteTable, parse_main_rows
from manifest_scraper import ManifestScraper
from .manifest_incremental import IncrementalStore
from tablas_manifiesto import ManifestTableStore


class CumulativeKnowledgeStore(IncrementalStore,KnowledgeStore):
    enable_cumulative=True


class CumulativeTableStore(IncrementalStore,ManifestTableStore):
    enable_cumulative=True


def enable_incremental_stores():
    # Solo el proceso de este módulo; no altera los archivos fuente copiados.
    import conocimientos_flow, tablas_flow
    conocimientos_flow.KnowledgeStore=CumulativeKnowledgeStore
    tablas_flow.ManifestTableStore=CumulativeTableStore


class RowsStore(IncrementalStore,KnowledgeStore):
    """La unidad confirmada es el manifiesto, no el índice de la última fila CSV."""
    def __init__(self, csv_path, scope, columns, db_path):
        self.columns = columns
        self.flow = scope['flow']
        super().__init__(csv_path, scope, db_path=db_path)
        self.db.execute('CREATE TABLE IF NOT EXISTS workbench_columns (value TEXT NOT NULL)')
        previous = self.db.execute('SELECT value FROM workbench_columns').fetchone()
        if previous and json.loads(previous[0]) != columns:
            self.close()
            raise IncompleteTable('El esquema no coincide con las filas ya guardadas')
        if not previous:
            with self.db:
                self.db.execute('INSERT INTO workbench_columns VALUES (?)',(json.dumps(columns),))

    @classmethod
    def open_existing(cls, path):
        from contextlib import closing
        import sqlite3
        from resultados import csv_for_database
        path = Path(path).resolve()
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            scope = json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0])
            columns = json.loads(db.execute('SELECT value FROM workbench_columns').fetchone()[0])
        return cls(csv_for_database(path),scope,columns,path)

    def save(self, mid, ordinal, rows, stats):
        if any(len(row) != len(self.columns) for row in rows):
            raise IncompleteTable('Cambió el número de columnas; datos sin confirmar')
        with self.db:
            self.db.execute('DELETE FROM rows WHERE manifest=?', (mid,))
            self.db.executemany('INSERT INTO rows VALUES (?,?,?)',
                [(mid, n, json.dumps(row, ensure_ascii=False)) for n, row in enumerate(rows)])
            self.db.execute('INSERT OR REPLACE INTO manifests VALUES (?,?,?)',
                (mid, ordinal, json.dumps(stats)))
            self.db.execute('DELETE FROM failures WHERE id=?', (mid,))
            self.record_outcome(mid, 'Guardado', stats=stats)

    def export(self, failed_path=None):
        import os
        import tempfile
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=self.csv_path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow((['index_flujo_contenedores'] if self.flow == 'contenedores' else []) + self.columns)
                query = ("SELECT r.data FROM rows r JOIN jobs j ON j.id=r.manifest "
                         "WHERE j.state='Guardado' ORDER BY j.ordinal,r.sequence")
                for index, (data,) in enumerate(self.db.execute(query), 1):
                    writer.writerow(([index] if self.flow == 'contenedores' else []) + json.loads(data))
            os.replace(temporary, self.csv_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


class WorkbenchManifestScraper(ManifestScraper):
    async def process_conocimientos_links(self,link_field='vVCONS',fetch_result=None):
        if getattr(self.conoc_store,'cumulative',False):
            # Reconciliar los identificadores antiguos antes de añadir nuevos:
            # insertar primero el canónico impediría la reparación original.
            corrections=[];canonical=set()
            for ordinal,item in enumerate(parse_main_rows(self.conoc_main_grid,self.conoc_main_values,self.URL,link_field),1):
                if item is None:continue
                href,info,old=item
                actual='-'.join(info.get(k,'').strip() for k in ('Trans.','Ing Sal','Manifiesto','Cod Ubicacion','Fecha'))
                canonical.add(actual)
                if actual!=old:corrections.append((old,actual,ordinal))
            self.conoc_store.reconcile_identities(corrections,canonical)
        return await super().process_conocimientos_links(link_field,fetch_result)

    async def container_result(self, href, ordinal, info):
        """Mismos Llenos y 18 campos; un fallo de mercancía no puede perder filas."""
        mid = '-'.join(info[k] for k in ('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha'))
        page = await self._open_sub_page(href)
        try:
            actual = await self.obtener_identificador_manifiesto(page)
            if actual != mid:
                raise IncompleteTable(f'Manifiesto inesperado: {actual}; esperado {mid}')
            # Esperar la respuesta del filtro; un contador inicial de cero no es prueba.
            async with page.expect_response(lambda r: 'hcgkonte.aspx' in r.url and r.request.method == 'POST',
                                             timeout=self.timeout * 1000) as response:
                await self._apply_contenedores_filter_llenos(page)
            reply = await response.value
            if not reply.ok:
                raise IncompleteTable('Error HTTP al filtrar contenedores llenos')
            try:
                payload = await reply.json()
                grid = next(g for g in payload['gxGrids'] if g['GridName']=='Grid1')
                confirmed_count = int(grid['Count'])
            except (ValueError,KeyError,StopIteration,TypeError) as exc:
                raise IncompleteTable('El filtro no devolvió una tabla confirmada de contenedores') from exc
            await page.wait_for_function("document.querySelector('#vCGLLENVAC')?.value === '1'")
            await page.wait_for_function("n => document.querySelectorAll('#Grid1ContainerTbl tbody tr[id^=\"Grid1ContainerRow_\"]').length === n",
                                         arg=confirmed_count,timeout=self.timeout*1000)
            items = await self._read_contenedores_rows(page)
            raw_total = (await page.text_content('#span_vTOTALCONTENEDORES') or '').strip()
            total = int(raw_total)  # Desconocido no equivale a cero.
            if total != len(items) or total != confirmed_count:
                raise IncompleteTable('Cantidad de contenedores incompleta; se conservará pendiente')
            output = []
            for item in items:
                if not item['merc_href']:
                    raise IncompleteTable('Contenedor sin enlace de mercancías')
                detail = await self._open_sub_page(item['merc_href'])
                try:
                    await detail.wait_for_selector('[name="Grid1ContainerDataV"]', state='attached', timeout=self.timeout * 1000)
                    raw = await self._read_hidden_grid_stable(detail)
                    rows = json.loads(raw)
                    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != 7 for row in rows):
                        raise IncompleteTable('Respuesta de mercancías inválida')
                    # Mantener el contrato original: un contenedor sin mercancías queda pendiente.
                    if not rows:
                        raise IncompleteTable('Mercancía vacía; manifiesto sin confirmar')
                    from conocimientos import FormInputs
                    form = FormInputs(await detail.content()).values
                    state = json.loads(form.get('GXState','{}'))
                    if 'Grid1ContainerData' in state:
                        grid = json.loads(state['Grid1ContainerData'])
                        if int(grid['Count']) != len(rows):
                            raise IncompleteTable('Cantidad de mercancías inconsistente')
                    if str(state.get('GRID1_nEOF','1')) != '1':
                        raise IncompleteTable('Mercancías paginadas sin descargar completamente')
                    names = ['BLOriginal','SecuenciaTica','Linea','ContenedorMercancia','Bultos','Tipo','EstadoMercancia']
                    for row in rows:
                        merged = {**item['base'], **dict(zip(names, row)), 'IDManifiesto': mid}
                        output.append([str(merged.get(name, '')) for name in self.CONT_OUT_COLS])
                finally:
                    await detail.close()
            return mid, output, {'pages': 1, 'read': len(output), 'kept': len(output)}
        finally:
            await page.close()

    async def run_container_jobs(self, mode, month, year, csv_path, db_path):
        self._conoc_mode = mode
        self.conoc_dates = [datetime.strptime(self.config[key], '%Y-%m-%d')
                            for key in ('conocimientos_fecha_inicio','conocimientos_fecha_fin')]
        scope = self.config['workbench_scope']
        self.conoc_store = RowsStore(csv_path, scope, self.CONT_OUT_COLS, db_path)
        self.conoc_failed_rows, self.conoc_stats = [], []
        self._conoc_link_lock = asyncio.Lock()
        self._conoc_link_refreshed = 0
        try:
            await self.open_page()
            await self._query_conoc_main()
            # Reutiliza cola, validación de selección, cancelación y confirmación transaccional.
            await self.process_conocimientos_links(link_field='vVCONTE', fetch_result=self.container_result)
        finally:
            try:
                self.conoc_store.close()
            finally:
                if self.context:
                    await self.context.close()

    async def run_main_job(self, mode, month, year, csv_path, db_path):
        self._conoc_mode = mode
        self.conoc_dates = [datetime.strptime(self.config[key], '%Y-%m-%d')
                            for key in ('conocimientos_fecha_inicio','conocimientos_fecha_fin')]
        await self.open_page()
        try:
            await self._query_conoc_main()
            # Count/DataV de la respuesta confirmada acredita también períodos vacíos.
            snapshot = parse_main_rows(self.conoc_main_grid, self.conoc_main_values, self.URL)
            frame = await self.extract_table()
            if len(frame) != len(snapshot):
                raise IncompleteTable('El listado visible no coincide con la respuesta confirmada')
            keys=['Trans.','Ing Sal','Manifiesto','Cod Ubicacion','Fecha']
            indices=[list(frame.columns).index(key) for key in keys]
            values = [[str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
            identity=lambda row:tuple(row[index].strip() for index in indices)
            expected=[tuple(item[1].get(key,'').strip() for key in keys) for item in snapshot if item is not None]
            if [identity(row) for row in values]!=expected:
                raise IncompleteTable('Las identidades visibles no coinciden con el listado confirmado')
            store = RowsStore(csv_path, self.config['workbench_scope'], list(frame.columns), db_path)
            self.conoc_store = store
            try:
                store.prepare_selection([(1, '', {}, 'listado')])
                store.start_run()
                if store.cumulative and store.completed('listado'):
                    # El listado no tiene detalle por descargar: conservar las
                    # filas anteriores y añadir identidades nuevas de la consulta.
                    previous=[json.loads(row[0]) for row in store.db.execute(
                        "SELECT data FROM rows WHERE manifest='listado' ORDER BY sequence")]
                    seen={identity(row) for row in previous}
                    merged=previous+[row for row in values if identity(row) not in seen]
                    if len(merged)!=len(previous):
                        store.save('listado',1,merged,{'pages':1,'read':len(merged),'kept':len(merged)})
                elif not store.completed('listado'):
                    store.claim('listado')
                    store.save('listado', 1, values, {'pages':1, 'read':len(values), 'kept':len(values)})
                store.finish_run(0 if store.progress()['processed_run'] == 0 else 1)
                self._notify_conoc(snapshot=True)
            finally:
                store.close()
        finally:
            await self.context.close()
