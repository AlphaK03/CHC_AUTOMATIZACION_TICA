"""Adaptador BLs con páginas persistentes; conserva el motor y su firma originales."""
import asyncio
from urllib.parse import urljoin, urlparse

from .bls_identifiers import install_input_support
install_input_support()

from core.engine import BLSProcessor
from core.inputs import input_job
from core.tables import InvalidResponse
from core.tica import TicaSession

from .bls_pages import PageStore, parse_page, next_form, validate_lines
from .bls_search import select_detail


class PagedTicaSession(TicaSession):
    def __init__(self, browser, config, stats, checkpoint, progress, active):
        # El formulario original selecciona la identidad; este hook lee sus líneas
        # por HTTP con las mismas cookies, incluida la ruta de una única página.
        super().__init__(browser,{**config,'detail_strategy':'workbench_pages'},stats)
        self.checkpoint, self.progress, self.active = checkpoint, progress, active

    async def query(self, record):
        try:
            selected, manifests = await select_detail(self, record)
            if selected is None:
                if await self.next_button() is not None:
                    raise InvalidResponse('La búsqueda tiene más páginas; no se confirma una ausencia parcial')
                return {'status':'no_match','error':'No se encontró la identidad exacta del BL. Encontrados: '+', '.join(manifests)}
            columns,rows = await self.browser_detail(selected,record)
            self.uses += 1
            return {'status':'success','columns':columns+['manifiesto','bls'],
                'rows':[[value.replace(',','').replace('"','') for value in row]+
                        [record['IDManifiesto'],record['BL original']] for row in rows]}
        except BaseException:
            await self.close()
            raise
        finally:
            if not self.config.get('reuse_context',True):await self.close()

    async def browser_detail(self, selected, record):
        job = input_job(record,0)['key']
        ordinal = self.active(job)
        href = urljoin(self.page.url,selected['href'])
        origin, target = urlparse(self.page.url), urlparse(href)
        if (target.scheme,target.netloc)!=(origin.scheme,origin.netloc) or not target.path.lower().endswith('/hcglineas.aspx'):
            raise InvalidResponse('Enlace de líneas ajeno al portal')

        async def fetch(form=None):
            self.active(job)
            self.stats['http_requests'] += 1
            response = await (self.context.request.post(href,form=form,timeout=float(self.config['timeout'])*1000)
                              if form is not None else self.context.request.get(href,timeout=float(self.config['timeout'])*1000))
            try:
                actual = urlparse(response.url)
                if response.status!=200 or (actual.scheme,actual.netloc,actual.path.lower())!=(target.scheme,target.netloc,target.path.lower()):
                    raise RuntimeError(f'HTTP {response.status} descargando página BLs')
                received = parse_page(await response.text(),record,selected['sequence'])
                self.active(job)
                return received
            finally:
                await response.dispose()

        saved = self.checkpoint.load(job)
        rows, seen = [], set()
        for previous in saved:
            validate_lines(previous.rows,seen)
            rows.extend(previous.rows)
        def notify(page_number, checkpoint_page):
            self.progress(record,page_number,checkpoint_page,len(rows))

        if saved:
            notify(len(saved),len(saved))
        notify(1 if not saved else len(saved),len(saved))
        fresh = await fetch()
        if fresh.offset!=0:
            raise InvalidResponse('El detalle no comenzó en la primera página')
        if saved:
            first, last = saved[0],saved[-1]
            same_first = (fresh.columns,fresh.rows)==(first.columns,first.rows)
            repeated_completion = len(saved)==1 and first.eof and not fresh.eof
            if not same_first or (fresh.eof!=first.eof and not repeated_completion):
                raise InvalidResponse('La primera página cambió; avance conservado para revisión')
            if last.offset:
                size = len(fresh.rows)
                if not size or last.offset % size:
                    raise InvalidResponse('Cambió el tamaño de página; no se puede retomar con seguridad')
                fresh = await fetch(next_form(fresh,last.offset-size))
            if (last.eof and not fresh.eof and
                    (fresh.offset,fresh.columns,fresh.rows)==(last.offset,last.columns,last.rows)):
                # Algunos grids repiten la última página llena al confirmar EOF.
                # Volver a comprobar ese EOF si hubo un cierre antes de Guardado.
                final = await fetch(next_form(fresh))
                if (final.eof and (final.offset,final.columns,final.rows)==
                        (last.offset,last.columns,last.rows)):
                    fresh = final
            if (fresh.offset,fresh.columns,fresh.rows,fresh.eof)!=(last.offset,last.columns,last.rows,last.eof):
                raise InvalidResponse('La página de reanudación cambió; avance conservado para revisión')
            page = fresh
        else:
            page = fresh
            validate_lines(page.rows,seen)
            self.active(job)
            self.checkpoint.save(job,ordinal,1,page)
            saved.append(page)
            rows.extend(page.rows)
            notify(1,1)
        while not page.eof:
            if len(saved)>=10000:
                raise InvalidResponse('Límite de paginación BLs excedido')
            notify(len(saved)+1,len(saved))
            received = await fetch(next_form(page))
            if (received.eof and received.offset==page.offset and received.columns==page.columns
                    and received.rows==page.rows):
                self.active(job)
                self.checkpoint.finish_repeated_page(job,len(saved))
                page.eof = True
                notify(len(saved),len(saved))
                break
            if received.offset!=len(rows) or received.columns!=page.columns:
                raise InvalidResponse('Página de líneas repetida, omitida o con otro esquema')
            validate_lines(received.rows,seen)
            self.active(job)
            self.checkpoint.save(job,ordinal,len(saved)+1,received)
            saved.append(received)
            rows.extend(received.rows)
            page = received
            notify(len(saved),len(saved))
        self.active(job)
        return page.columns, rows


class WorkbenchBLSProcessor(BLSProcessor):
    def __init__(self, config, stop_event):
        super().__init__(config,stop_event)
        self.page_store = None
        self._empty_retry_started = False

    def emit(self, kind='summary', **extra):
        request = self.config.get('workbench_empty_retry')
        if request and extra.get('phase') == 'prepare' and not self._empty_retry_started:
            from .bls_empty_retry import begin
            begin(self.store,request)
            self._empty_retry_started = True
        super().emit(kind,**extra)

    async def run_async(self, df, session_factory=None):
        try:
            return await super().run_async(df,session_factory=session_factory)
        finally:
            if self.page_store is not None:
                self.page_store.close()
                self.page_store = None

    async def worker(self, queue, factory, worker_id):
        def wrap(worker):
            original = factory(worker)
            if not isinstance(original,TicaSession):
                return original
            if self.page_store is None:
                signature = self.store.get_metadata('signature')
                from .bls_empty_retry import generations
                self.page_store = PageStore(self.store.path.with_name('bls_pages.sqlite3'),signature,
                                            generations(self.store.db))
            reservation = {}
            def active(key):
                if self.stop_event.is_set():
                    raise asyncio.CancelledError()
                row = self.store.db.execute('SELECT ordinal,token,state FROM jobs WHERE id=?',(key,)).fetchone()
                if not row or row[2]!='Descargando' or not row[1]:
                    raise asyncio.CancelledError()
                if key in reservation and reservation[key]!=row[1]:
                    raise asyncio.CancelledError()
                reservation[key] = row[1]
                return row[0]
            def progress(record,page,confirmed,collected):
                key = input_job(record,0)['key']
                ordinal = active(key)
                attempts = self.store.db.execute('SELECT attempts FROM jobs WHERE id=?',(key,)).fetchone()[0]
                job = self.job_event(ordinal,record,'Descargando',attempts,0,'')
                job.update(page=page,checkpointPage=confirmed,collectedRows=collected)
                self.emit('job',job=job)
            return PagedTicaSession(original.browser,original.config,original.stats,
                                    self.page_store,progress,active)
        await super().worker(queue,wrap,worker_id)
