"""Catálogo y adaptación de Manifiestos/BLs. Solo se importa dentro del worker."""
import asyncio
from contextlib import closing
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import time

from .manifest_names import manifest_scope, manifest_name, normalized_scope, cumulative_family
from . import output_layout

ROOT = Path(__file__).resolve().parents[1]
FLOWS = ('tabla', 'conocimientos', 'duas', 'movimientos', 'contenedores', 'bases', 'bls_source', 'bls')
LABELS = {'tabla':'Manifiestos', 'conocimientos':'Conocimientos', 'duas':'DUAs por manifiesto',
          'movimientos':'Movimientos de manifiesto', 'contenedores':'Contenedores', 'bls':'BLs'}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def name_checked(value):
    value = str(value).strip()
    if (not value or len(value) > 100 or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)
            or value.endswith(('.', ' ')) or value in ('.','..')
            or value.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}):
        raise ValueError('Escriba un nombre de tabla válido, sin caracteres de ruta.')
    return value


def bls_job(ordinal, payload, state, attempts, rows, error):
    original = json.loads(payload) if isinstance(payload, str) else payload
    manifest, bl = original.get('IDManifiesto', ''), original.get('BL original', '')
    return dict(id=manifest+' / '+bl, manifest=manifest, bl=bl, ordinal=ordinal,
                state=state, attempts=attempts, rows=rows, error=error,
                page=0,checkpointPage=0,collectedRows=rows)


class BatchService:
    def __init__(self, root, flow, emit, stop, fixture=False):
        if flow not in FLOWS:
            raise ValueError('Procedimiento desconocido')
        self.root, self.flow, self.emit, self.stop, self.fixture = Path(root).resolve(), flow, emit, stop, fixture
        self.index_path = self.root / 'data' / 'workbench' / flow / 'session.json'
        today = date.today()
        self.index = {'config': {'year':today.year, 'month':today.month, 'modes':['maritimo'],
            'workers':32 if flow == 'conocimientos' else 5 if flow == 'contenedores' else 2 if flow == 'bls' else 4,
            'headless':flow == 'bls', 'timeout':30 if flow == 'bls' else 120, 'name':'', 'outputRoot':str(self.root / 'resultados'),
            'courier':'todos', 'start':'', 'end':'', 'manifestIds':'', 'limit':0,
            'input':'', 'sheet':'BLS', 'max_retries':3, 'inputMode':'knowledge',
            'knowledgePeriods':[]}, 'history':[], 'active':'', 'lastBase':''}
        if self.index_path.exists():
            saved = json.loads(self.index_path.read_text(encoding='utf-8'))
            if 'inputMode' not in saved.get('config',{}) and saved.get('config',{}).get('input'):
                self.index['config']['inputMode']='file'
            self.index['config'].update(saved.get('config', {}))
            self.index.update({k:v for k,v in saved.items() if k != 'config'})
        self.sources = []
        self.base_scope = None
        self._last_event = 0
        self._last_save = 0
        self._jobs = {}
        self._result_counts = {}
        self.message = ''
        self.base_info = {}
        self._fixture_portals = {}
        self.processing = False
        self.knowledge_catalog = {'periods':[],'message':'Actualice las descargas disponibles.'}

    def close(self):
        for portal in self._fixture_portals.values():
            portal.close()

    def active(self):
        return next((item for item in self.index['history'] if item['id'] == self.index['active']), None)

    def public_root(self):
        return output_layout.local_root(self.root,self.index['config'].get('outputRoot',''))

    def save(self):
        write_json(self.index_path, self.index)

    def snapshot(self):
        active = self.active() or {}
        summary = active.get('summary', {})
        jobs = list(self._jobs.values())
        jobs.sort(key=lambda item:(0 if item['state']=='Descargando' else 1,item['ordinal']))
        return {'config':{**self.index['config'],'outputRoot':str(self.public_root())}, 'history':[
            {'id':item['id'], 'label':item['name'] + ' · ' + item.get('period',''), 'state':item.get('state','Pendiente')}
            for item in reversed(self.index['history'])], 'activeId':self.index['active'],
            'summary':{key:summary.get(key,0) for key in ('total','succeeded','pending','running','excluded','rows','invalid')},
            'jobs':jobs[:200], 'activeJobs':[j for j in jobs if j['state']=='Descargando'] if self.processing else [], 'outputFolder':str(self.public_root()/(Path('BLS') if self.flow=='bls' else Path('MANIFIESTOS')/output_layout.FLOWS.get(self.flow,'BASES'))) if active else '',
            'lastBase':self.index.get('lastBase',''), 'message':self.message, 'baseInfo':self.base_info,
            'knowledgeCatalog':self.knowledge_catalog}

    def progress(self, payload):
        record = self.active()
        if record is None:
            return
        p = payload.get('progress', payload)
        if 'selected' in p:
            summary = dict(total=p['selected'], succeeded=p.get('saved',0), pending=p.get('pending',0),
                           running=p.get('active',0), excluded=p.get('excluded',0), rows=record.get('summary',{}).get('rows',0))
        elif 'total' in p:
            summary = dict(total=p.get('total',0), succeeded=p.get('saved',0), pending=p.get('pending',0),
                           running=p.get('running',0), excluded=0, invalid=p.get('invalid',0), rows=p.get('result_rows',0))
        else:
            # Preparar el navegador/base no significa reiniciar el avance guardado.
            summary = dict(record.get('summary',{}))
        record['summary'] = summary
        if payload.get('message'):
            self.message = payload['message']
        jobs = payload.get('jobs', payload.get('rows', []))
        if payload.get('job'):
            jobs = [payload['job']]
        for item in jobs:
            if self.flow=='bls':
                ordinal = item['ordinal']
                previous = self._jobs.get(ordinal,{})
                row = bls_job(ordinal,
                    {'IDManifiesto':item.get('manifest',''), 'BL original':item.get('bl','')},
                    item.get('state',''),item.get('attempts',0),item.get('result_count',0),item.get('error',''))
                for field in ('page','checkpointPage','collectedRows'):
                    row[field] = item.get(field,previous.get(field,row[field]))
                if row['state']!='Descargando':
                    row['page'] = row['checkpointPage']
                if row['state']=='Guardado':
                    row['collectedRows'] = row['rows']
                self._jobs[ordinal] = row
                continue
            identifier = item.get('id') or (item.get('manifest','') + ' / ' + item.get('bl',''))
            self._jobs[identifier] = {'id':identifier, 'ordinal':item.get('ordinal',0),
                'state':item.get('state',''), 'attempts':item.get('attempts',0),
                'rows':item.get('kept', item.get('result_count',0)), 'error':item.get('error','')}
            if 'selected' in p:
                count = self._jobs[identifier]['rows'] if item.get('state')=='Guardado' else 0
                summary['rows'] += count-self._result_counts.get(identifier,0)
                self._result_counts[identifier] = count
        record['databases'] = list(dict.fromkeys(record.get('databases',[]) + ([payload['database']] if payload.get('database') else [])))
        terminal = bool(payload.get('job'))
        if time.monotonic() - self._last_event > .15 or payload.get('phase') == 'finished' or terminal:
            self.emit('progress', snapshot=self.snapshot())
            self._last_event = time.monotonic()
        if time.monotonic() - self._last_save > 2:
            self._last_save = time.monotonic()
            try:
                self.save()
            except OSError:
                # El historial auxiliar puede estar abierto por otro lector de
                # Windows. Nunca abortar un BL ya confirmado en SQLite por ello.
                import logging
                logging.exception('No se pudo actualizar el historial de %s; SQLite conserva el progreso.', self.flow)

    def execute(self, command, request):
        if command == 'configure':
            if request.get('config',{}).get('outputRoot'):
                output_layout.set_local_root(request['config']['outputRoot'],self.root)
            self.index['config'].update({k:v for k,v in request.get('config',{}).items() if k in self.index['config']})
            self.save()
        elif command == 'run':
            self.index['config'].update({k:v for k,v in request.get('config',{}).items() if k in self.index['config']})
            self.save()
            self.run()
        elif command == 'select':
            if not any(item['id'] == request['id'] for item in self.index['history']):
                raise ValueError('No se encontró la ejecución')
            self.index['active'] = request['id']
            selected=dict(self.active()['config'])
            if self.flow=='bls':
                selected.setdefault('inputMode','file')
                selected.setdefault('knowledgePeriods',[])
            self.index['config'].update(selected)
            self.inspect()
            self.save()
        elif command == 'view':
            self.inspect(request.get('search',''), int(request.get('offset',0)))
        elif command == 'export':
            self.export()
        elif command == 'review':
            return self.review(request.get('kind','pending'))
        elif command == 'import_progress':
            self.import_progress(request['source'])
        elif command == 'base_load':
            return self.load_base(request)
        elif command == 'base_build':
            return self.build_base(request)
        elif command in ('knowledge_catalog','knowledge_build'):
            if self.flow!='bls_source':
                raise ValueError('Esta operación requiere el proveedor de Conocimientos para BLs.')
            from chc_runtime.knowledge_source import KnowledgeSource
            provider=KnowledgeSource(self.root,self.stop,self.emit)
            if command=='knowledge_build':
                result=provider.build(request.get('periods',[]))
                return {'knowledgeBase':result,'snapshot':self.snapshot()}
            self.knowledge_catalog=provider.catalog()
        elif command=='knowledge_empty':
            if self.flow!='bls':
                raise ValueError('Operación exclusiva de BLs')
            config=request['config']
            from input_files import BLS_COLUMNS
            with closing(sqlite3.connect(Path(config['input']).resolve().as_uri()+'?mode=ro',uri=True)) as db:
                if [r[1] for r in db.execute('PRAGMA table_info(BLS)')]!=BLS_COLUMNS or db.execute('SELECT 1 FROM BLS LIMIT 1').fetchone():
                    raise ValueError('La base no acredita una selección sin BLs.')
            self.index['config'].update({k:v for k,v in config.items() if k in self.index['config']})
            self.index['active']=''
            self._jobs={}
            self.message='Conocimientos completos; no hay BLs Courier N para esta selección.'
            self.save()
        elif command == 'split':
            # Función original usa diálogos Tk: la adaptación conserva el streaming sin GUI.
            return self.split(request['source'], int(request.get('maxRows',1048576)))
        elif command != 'refresh':
            raise ValueError('Comando desconocido')
        if command == 'refresh':
            self.inspect()
        return {'snapshot':self.snapshot()}

    def import_progress(self, source):
        """Copiar una instantánea SQLite confirmada; nunca inferir éxito desde CSV."""
        if self.flow not in ('conocimientos','duas','movimientos'):
            raise ValueError('La importación de progreso aplica a Conocimientos, DUAs y Movimientos.')
        source = Path(source).resolve()
        if not source.is_file():
            raise ValueError('La base de progreso no existe.')
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as incoming:
            incoming.execute('BEGIN')
            tables = {r[0] for r in incoming.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'metadata','manifests','jobs','rows','partial_pages'} <= tables:
                raise ValueError('No es una base de progreso compatible de Manifiestos.')
            scope = json.loads(incoming.execute('SELECT scope FROM metadata').fetchone()[0])
            if scope.get('flow','conocimientos') != self.flow:
                raise ValueError('La base pertenece a otro procedimiento; selecciónelo primero.')
            year,month = int(scope['year']),int(scope['month'])
            self.index['config'].update({'year':year,'month':month,'modes':[scope['mode']],
                'start':scope.get('desde',''),'end':scope.get('hasta',''),
                'courier':scope.get('courier') or 'todos', 'manifestIds':' '.join(scope.get('ids',[])),
                'limit':scope.get('limit') or 0,'name':f"{LABELS[self.flow]} {year}-{month:02d} {scope['mode']}"})
            record = self.prepare()
            from resultados import output_paths
            workspace = Path(record['work'])
            paths = output_paths({'app_data_folder':str(workspace/'datos_app'),'resultados_folder':str(workspace/'resultados')},
                                 self.flow,scope['mode'],month,year)
            if paths.database.exists():
                raise ValueError('Este lote ya tiene progreso en el Workbench; no se sustituyó.')
            temporary = paths.database.with_suffix('.importando')
            try:
                with closing(sqlite3.connect(temporary)) as target:
                    def progress(status,remaining,total):
                        if self.stop.is_set():
                            raise asyncio.CancelledError()
                    incoming.backup(target,pages=256,progress=progress)
                    if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                        raise ValueError('La copia SQLite no superó la comprobación de integridad.')
                os.replace(temporary,paths.database)
            finally:
                if temporary.exists():
                    temporary.unlink()
            record['databases'] = [str(paths.database)]
            record['importedFrom'] = str(source)
            record['state'] = 'Importado'
            self.inspect()
            self.save()
            self.export()
            self.message = 'Progreso importado; el original permanece intacto.'

    def prepare(self):
        c = self.index['config']
        if self.flow == 'bls':
            if not Path(c['input']).is_file():
                raise ValueError('Seleccione una base de BLs Excel o SQLite.')
            from input_files import load_input_file
            from core.inputs import batch_scope
            from config_manager import DEFAULTS
            frame = load_input_file(c['input'], c['sheet'])
            settings = {**DEFAULTS, 'sheet_name':c['sheet'], 'dates_from_input':True}
            key, _ = batch_scope(frame, settings)
            spec = {'input':c['input'], 'sheet':c['sheet']}
        else:
            spec = manifest_scope(self.flow, c)
            key = hashlib.sha256(json.dumps(cumulative_family(spec) or normalized_scope(spec),sort_keys=True).encode()).hexdigest()
        maximum = 20 if self.flow == 'bls' else 32
        if not 1 <= int(c['workers']) <= maximum:
            raise ValueError(f'Use entre 1 y {maximum} descargas simultáneas')
        if not 5 <= float(c['timeout']) <= 3600 or not 1 <= int(c['max_retries']) <= 10:
            raise ValueError('Timeout o número de intentos inválido')
        default_name=manifest_name(spec) if self.flow!='bls' else LABELS[self.flow]
        output_root=Path(c['outputRoot']).resolve()
        identity_for=lambda name:hashlib.sha256((key+'|'+name+'|'+str(output_root)).encode()).hexdigest()[:24]
        if self.flow=='bls' and c.get('inputMode')=='knowledge' and c.get('knowledgePeriods') and not c['name']:
            periods=sorted(set(k.split('|')[0] for k in c['knowledgePeriods']))
            modes=sorted(set(k.split('|')[1] for k in c['knowledgePeriods']))
            mode_label='Marítimo y Aéreo' if len(modes)>1 else 'Marítimo' if modes[0]=='maritimo' else 'Aéreo'
            default_name='BLs '+(' y '.join(periods) if len(periods)<=3 else periods[0]+' a '+periods[-1])+' '+mode_label
            # Reutilizar incluso un lote manual previo de la misma entrada, conservando sus BLs.
            previous=next((r for r in self.index['history'] if r['id']==identity_for(r['name'])),None)
            if previous:
                default_name=previous['name']
            else:
                used={r['name'] for r in self.index['history'] if Path(r['output']).parent==output_root}
                base=default_name
                version=2
                while default_name in used:
                    default_name=base+f' ({version})'
                    version+=1
        name = name_checked(c['name'] or default_name) if self.flow=='bls' else name_checked(default_name)
        # El nombre y destino distinguen lotes publicados, sin duplicar reservas por cambiar hilos.
        identity = identity_for(name)
        record = next((item for item in self.index['history'] if item['id']==identity), None)
        if self.flow!='bls':
            # Recuperar también lotes anteriores con nombre manual, sin mover sus datos.
            candidates = [item for item in self.index['history']
                          if (cumulative_family(spec) and cumulative_family(item['spec'])==cumulative_family(spec))
                          or normalized_scope(item['spec']) == normalized_scope(spec)]
            populated=[item for item in candidates if item.get('databases')]
            pool=populated or candidates
            record = next((item for item in pool if item['id']==self.index['active']),
                          max(pool,key=lambda item:item.get('summary',{}).get('succeeded',0)) if pool else None)
            c['name'] = record['name'] if record else name
        elif record is None:
            # Cambiar la carpeta pública nunca reinicia un lote BL ya existente.
            record=next((item for item in reversed(self.index['history'])
                         if item['name']==name and item['id']==hashlib.sha256((key+'|'+item['name']+'|'+str(Path(item['output']).parent)).encode()).hexdigest()[:24]),None)
        if record is None:
            record = {'id':identity, 'name':name, 'period':f"{c['year']}-{int(c['month']):02d}" if self.flow!='bls' else 'Base BLs',
                'spec':spec, 'config':dict(c), 'work':str(self.root/'data/jobs'/self.flow/identity),
                'output':str(Path(c['outputRoot']).resolve()/name), 'databases':[], 'state':'Pendiente', 'summary':{}}
            self.index['history'].append(record)
        if self.flow!='bls' and cumulative_family(spec):
            record['cumulative']=True
            record['spec']=spec
        record['config'] = dict(c)
        if self.flow=='bls':
            public_specs={}
            from datetime import datetime
            for value in frame['IDManifiesto']:
                try:
                    parts=str(value).split('-');day=datetime.strptime(parts[-1],'%d/%m/%y')
                    mode={'1':'MARITIMO','4':'AEREO','7':'TERRESTRE'}[parts[0]]
                    value=output_layout.bls_spec(record,f'{day.year:04d}-{day.month:02d}',mode)
                    public_specs[value['filename']]=value
                except (KeyError,ValueError,IndexError):continue
            record['publicSpecs']=list(public_specs.values())
        self.index['active'] = record['id']
        self._jobs = {}
        self.inspect()
        self.save()
        return record

    def run(self):
        record = self.prepare()
        if self.flow=='bls':
            for spec in record.get('publicSpecs',[]):self.publication_target(record,spec=spec)
        else:
            from resultados import csv_name
            for mode in record['spec']['modes']:
                self.publication_target(record,csv_name(self.flow,mode,record['spec']['month'],record['spec']['year']))
        record['state'] = 'En curso'
        self.message = 'Consultando…'
        self.processing = True
        self.save()
        async def guarded():
            operation = asyncio.create_task(self.run_bls(record) if self.flow == 'bls' else self.run_manifests(record))
            async def watch():
                while not self.stop.is_set():
                    await asyncio.sleep(.1)
                operation.cancel()
            watcher = asyncio.create_task(watch())
            try:
                await operation
            finally:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
        try:
            asyncio.run(guarded())
            summary = record.get('summary',{})
            record['state'] = ('Con pendientes' if summary.get('pending') or summary.get('invalid') else
                               'Completado con exclusiones' if summary.get('excluded') else 'Completado')
            self.message = record['state']
        except BaseException as exc:
            if not self.stop.is_set():
                import logging
                logging.exception('El proceso %s se detuvo; el progreso está conservado.', self.flow)
                record['error'] = str(exc) or type(exc).__name__
            record['state'] = 'Detenido' if self.stop.is_set() else 'Error'
            self.message = record['state'] + '; progreso conservado'
            raise
        finally:
            self.processing = False
            self.inspect()
            try:
                self.export()
            finally:
                self.message = record['state'] + ('; progreso guardado' if record['state'] in ('Error','Detenido') else '')
                if record['state']=='Error' and record.get('error'):
                    self.message += ': ' + record['error']
                self.save()

    async def run_manifests(self, record):
        from playwright.async_api import async_playwright
        from resultados import output_paths
        from chc_runtime.manifest_adapters import WorkbenchManifestScraper
        c, spec = self.index['config'], record['spec']
        if record.get('cumulative'):
            from chc_runtime.manifest_adapters import enable_incremental_stores
            enable_incremental_stores()
        workspace = Path(record['work'])
        config = {'timeout_manifest':float(c['timeout']), 'headless':bool(c['headless']),
            'app_data_folder':str(workspace/'datos_app'), 'resultados_folder':str(workspace/'resultados'),
            'omitir_organizacion_legacy':True,
            'conocimientos_concurrencia':int(c['workers']), 'conocimientos_courier':None if spec['courier']=='todos' else spec['courier'],
            'conocimientos_fecha_inicio':spec['start'], 'conocimientos_fecha_fin':spec['end'],
            'conocimientos_manifest_ids':spec['ids'], 'conocimientos_limite_manifiestos':spec['limit'] or None,
            'conocimientos_progress_callback':self.progress}
        for option in ('concurrencia','fecha_inicio','fecha_fin','manifest_ids','limite_manifiestos','progress_callback'):
            config[self.flow+'_'+option] = config['conocimientos_'+option]
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=bool(c['headless']))
            try:
                for mode in spec['modes']:
                    paths = output_paths(config,self.flow,mode,spec['month'],spec['year'])
                    record['databases'] = list(dict.fromkeys(record['databases']+[str(paths.database)]))
                    scraper = WorkbenchManifestScraper(dict(config),browser,request_factory=pw.request)
                    if self.fixture:
                        from chc_runtime.manifest_fixture import configure_scraper
                        key = (mode,spec['year'],spec['month'])
                        self._fixture_portals[key] = configure_scraper(scraper,self.flow,mode,spec,self._fixture_portals.get(key))
                    if self.flow == 'conocimientos':
                        await scraper.run_conocimientos_for_mode(mode,spec['month'],spec['year'])
                    elif self.flow in ('duas','movimientos'):
                        await scraper.run_tracked_table(self.flow,mode,spec['month'],spec['year'])
                    elif self.flow == 'contenedores':
                        config['workbench_scope'] = {**spec,'mode':mode,'flow':self.flow,'workbench_cumulative':bool(record.get('cumulative'))}
                        scraper.config.update(config)
                        await scraper.run_container_jobs(mode,spec['month'],spec['year'],paths.csv,paths.database)
                    else:
                        scraper.config['workbench_scope'] = {**spec,'mode':mode,'flow':self.flow,'workbench_cumulative':bool(record.get('cumulative'))}
                        await scraper.run_main_job(mode,spec['month'],spec['year'],paths.csv,paths.database)
                    self.inspect()
                    self.emit('progress',snapshot=self.snapshot())
                    if self.stop.is_set():
                        raise asyncio.CancelledError()
            finally:
                await browser.close()

    async def run_bls(self, record):
        from config_manager import DEFAULTS
        from chc_runtime.bls_session import WorkbenchBLSProcessor
        from input_files import load_input_file
        c = self.index['config']
        config = {**DEFAULTS, 'sheet_name':c['sheet'], 'output_base_path':record['work'],
            'cant_hilos':int(c['workers']), 'max_retries':int(c['max_retries']),
            'timeout':float(c['timeout']), 'headless':bool(c['headless']), 'event_callback':self.progress}
        frame = load_input_file(c['input'],c['sheet'])
        factory = None
        if self.fixture:
            from chc_runtime.bls_fixture import Session
            factory = lambda worker: Session()
        processor = WorkbenchBLSProcessor(config,self.stop)
        result = await processor.run_async(frame,session_factory=factory)
        record['databases'] = [result['database']]
        record['csv'] = result['output_csv']
        if result.get('export_error'):
            raise OSError(result['export_error'])

    def inspect(self, search='', offset=0):
        record = self.active()
        if not record:
            return
        self._jobs = {}
        summary = dict(total=0,succeeded=0,pending=0,running=0,excluded=0,rows=0,invalid=0)
        self._result_counts = {}
        databases = record.get('databases',[])
        if self.flow == 'bls':
            databases = [str(p) for p in Path(record['work']).glob('**/SQLite/bls.sqlite3')]
            record['databases'] = databases
        for path in databases:
            path = Path(path)
            if not path.is_file():
                continue
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3)) as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'jobs' not in tables:
                    continue
                counts = dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state'))
                summary['total'] += sum(counts.values())
                for key, state in [('succeeded','Guardado'),('pending','Pendiente'),('running','Descargando'),('excluded','Excluido'),('invalid','Inválido')]:
                    summary[key] += counts.get(state,0)
                summary['rows'] += db.execute('SELECT count(*) FROM '+('results' if self.flow=='bls' else 'rows')).fetchone()[0]
                if self.flow!='bls':
                    self._result_counts.update(db.execute("SELECT id,kept_count FROM jobs WHERE state='Guardado'"))
                if self.flow=='bls':
                    progress = {}
                    checkpoint = path.with_name('bls_pages.sqlite3')
                    if checkpoint.is_file():
                        with closing(sqlite3.connect(checkpoint.resolve().as_uri()+'?mode=ro',uri=True,timeout=3)) as pages:
                            signature = db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0]
                            if pages.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0]!=signature:
                                raise ValueError('Las páginas guardadas pertenecen a otra selección BLs')
                            progress = {ordinal:(number,count) for ordinal,number,count in pages.execute(
                                'SELECT ordinal,MAX(page),SUM(count) FROM pages GROUP BY ordinal')}
                    records = db.execute('''SELECT ordinal,payload,state,attempts,result_count,error FROM jobs
                        WHERE json_extract(payload,'$."IDManifiesto"') LIKE ?
                           OR json_extract(payload,'$."BL original"') LIKE ?
                        ORDER BY CASE WHEN state='Descargando' THEN 0 ELSE 1 END, ordinal LIMIT 200 OFFSET ?''', ('%'+search+'%','%'+search+'%',max(0,offset)))
                    for ordinal,payload,state,attempts,rows,error in records:
                        row = bls_job(ordinal,payload,state,attempts,rows,error)
                        if ordinal in progress:
                            number,collected = progress[ordinal]
                            row.update(page=number,checkpointPage=number,
                                       collectedRows=rows if state=='Guardado' else collected)
                        self._jobs[ordinal] = row
                else:
                    records = db.execute('''SELECT id,ordinal,state,attempts,kept_count,error FROM jobs
                        WHERE id LIKE ? ORDER BY CASE WHEN state='Descargando' THEN 0 ELSE 1 END, ordinal LIMIT 200 OFFSET ?''', ('%'+search+'%',max(0,offset)))
                    for identifier,ordinal,state,attempts,rows,error in records:
                        self._jobs[identifier] = dict(id=identifier,ordinal=ordinal,state=state,attempts=attempts,rows=rows,error=error)
        record['summary'] = summary
        if not self.processing:
            # Una reserva huérfana se recupera bajo el bloqueo al reanudar; no simular actividad.
            summary['pending'] += summary['running']
            summary['running'] = 0
            for job in self._jobs.values():
                if job['state']=='Descargando':
                    job['state'] = 'Interrumpido'

    def publication_target(self, record, filename=None, spec=None):
        if spec is None:
            from resultados import parse_result_name
            parsed=parse_result_name(filename)
            if not parsed:raise ValueError('El archivo no es un CSV de resultados verificable.')
            spec=output_layout.manifest_spec(self.flow,record,parsed[1])
        destination=self.public_root().joinpath(*spec['relativeFolders'],spec['filename'])
        # Un destino compartido no puede sobrescribir otro lote con filtros diferentes.
        owner_path = self.root/'data/publications'/(hashlib.sha256(str(destination).casefold().encode()).hexdigest()+'.json')
        if owner_path.exists() and json.loads(owner_path.read_text(encoding='utf-8'))['owner'] != record['id']:
            if self.flow!='bls':
                raise ValueError('La carpeta de este período ya publica otra selección. Retome su ejecución guardada o elija otra carpeta de resultados.')
            raise ValueError('Este nombre de tabla ya publica otro lote. Use otro nombre o retome su ejecución guardada.')
        if destination.exists() and not owner_path.exists():
            if self.flow!='bls':
                raise ValueError('El CSV ya existe fuera de este lote. Elija otra carpeta de resultados; el archivo anterior se conservó.')
            raise ValueError('El CSV ya existe fuera de este lote. Use otro nombre de tabla; el archivo anterior se conservó.')
        return destination,owner_path

    def publish(self, source, record):
        source = Path(source)
        if not source.is_file():
            return
        if self.flow=='bls':
            files=output_layout.bls_exports(source,record)
        else:
            from resultados import parse_result_name
            parsed=parse_result_name(source)
            if not parsed or parsed[4]:raise ValueError('Solo se publican CSV de resultados, sin errores ni auditorías.')
            files=[(source,output_layout.manifest_spec(self.flow,record,parsed[1]))]
        try:
            for path,spec in files:
                destination,owner_path=self.publication_target(record,spec=spec)
                result=output_layout.publish(path,self.public_root(),spec,self.flow+':'+record['id'],output_layout.registry_path(self.root),
                                             supersede=bool(record.get('cumulative')))
                if result:
                    write_json(owner_path,{'owner':record['id'],'path':str(destination)})
                    self.emit('published',flow=self.flow,**result)
        finally:
            if self.flow=='bls':
                for path,_ in files:path.unlink(missing_ok=True)

    def export(self):
        record = self.active()
        if not record:
            raise ValueError('Seleccione una ejecución guardada.')
        if self.flow == 'bls':
            from core.store import export_saved
            # El motor ya exporta internamente; se publica exclusivamente el CSV de datos.
            files = list(Path(record['work']).glob('**/CSV/Duas_procesados_*.csv'))
            if not files:
                for database in record.get('databases',[]):
                    destination = Path(database).parent.parent/'CSV'/f"Duas_procesados_{record['config']['sheet']}.csv"
                    export_saved(database,destination)
                    files.append(destination)
            for path in files:
                self.publish(path,record)
        else:
            from conocimientos import KnowledgeStore
            from tablas_manifiesto import ManifestTableStore
            from resultados import csv_for_database
            for database in record.get('databases',[]):
                if not Path(database).is_file():
                    continue
                if self.flow in ('tabla','conocimientos','duas','movimientos','contenedores'):
                    from chc_runtime.manifest_adapters import RowsStore
                    cls = KnowledgeStore if self.flow=='conocimientos' else ManifestTableStore if self.flow in ('duas','movimientos') else RowsStore
                    store = cls.open_existing(database)
                    try:
                        store.export()
                    finally:
                        store.close()
                self.publish(csv_for_database(database),record)
        self.message = 'CSV actualizado'

    def review(self, kind):
        import csv
        record = self.active()
        if not record:
            raise ValueError('Seleccione una ejecución guardada.')
        root = Path(record['work'])/'revision'
        root.mkdir(parents=True,exist_ok=True)
        with (root/'pendientes_y_exclusiones.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Fila','Identificador','Estado','Intentos','Último error'])
            for database in record.get('databases',[]):
                with closing(sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True)) as db:
                    sql = "SELECT ordinal,id,state,attempts,error FROM jobs WHERE state!='Guardado' ORDER BY ordinal"
                    writer.writerows(db.execute(sql))
        return {'reviewFolder':str(root)}

    def load_base(self, request):
        from bls_base import catalog_sources, choose_candidates, inspect_sources, NotKnowledgeSource
        self.sources = []
        self.base_scope = None
        roots = [self.root/'data/jobs/conocimientos']
        roots = [path for path in roots if path.exists()] + [Path(p) for p in request.get('external',[]) if p]
        if not roots:
            self.base_info = {'sources':[], 'periods':[], 'message':'No hay descargas de Conocimientos. Puede añadir archivos externos.'}
            return {'snapshot':self.snapshot()}
        candidates, errors = catalog_sources(roots,self.stop,include_history=bool(request.get('includeHistory')))
        scope = {k:request.get(k) for k in ('year','month','mode','kind')}
        candidates = choose_candidates(candidates,year=scope['year'] or None,month=scope['month'] or None,
                                       mode=scope['mode'] or None,kind=scope['kind'] or 'preferred')
        for candidate in candidates:
            try:
                self.sources.extend(inspect_sources(candidate.path,self.stop,
                    progress=lambda n:self.emit('activity',message='Leyendo fuentes elegidas…')))
            except NotKnowledgeSource:
                continue
            except Exception as exc:
                errors.append((str(candidate.path),str(exc)))
        if errors:
            self.sources = []
            raise ValueError('No se pudieron leer todas las fuentes: '+'; '.join(f'{Path(p).name}: {error}' for p,error in errors[:5]))
        from bls_base import default_selection, available_periods
        selected = default_selection(self.sources)
        self.sources = [s for s in self.sources if selected.get(s.key,False) or (s.kind=='SQLite' and not s.rows)]
        groups = available_periods(self.sources)
        self.base_scope = scope
        periods = [{'key':period+'|'+mode,'period':period,'mode':mode,
                    'rows':sum(p.rows for s,p in entries),
                    'pending':sum(p.pending or 0 for s,p in entries)} for (period,mode),entries in groups.items()]
        self.base_info = {'sources':[{'path':str(s.path),'sheet':s.sheet,'rows':s.rows or 0,'kind':s.kind} for s in self.sources],
                          'periods':periods,'message':f'{len(self.sources)} fuentes disponibles. Seleccione los meses.'}
        return {'snapshot':self.snapshot()}

    def build_base(self, request):
        from bls_base import build_base
        if not self.sources or self.base_scope is None:
            raise ValueError('Cargue los datos elegidos antes de generar la base.')
        periods = [tuple(value.split('|')) for value in request.get('periods',[])]
        if not periods:
            raise ValueError('Seleccione al menos un mes con datos.')
        destination = Path(request.get('destination') or self.root/'bases_bls'/'Base_BLs.sqlite3').resolve()
        if destination.exists() and not request.get('replace',False):
            raise ValueError('El archivo ya existe. Confirme su sustitución o elija otro nombre.')
        keys = request.get('sources')
        sources = [s for s in self.sources if keys is None or str(s.path)+'|'+s.sheet in keys]
        stats = build_base(sources,destination,periods=periods,
            audit_dir=self.root/'data/bases_bls/auditoria',stop=self.stop,
            progress=lambda *args:self.emit('activity',message='Generando base de BLs…'))
        self.index['lastBase'] = str(destination)
        self.save()
        return {'baseResult':stats,'snapshot':self.snapshot()}

    def split(self, source, max_rows):
        import csv
        source = Path(source).resolve()
        if not source.is_file() or max_rows < 2:
            raise ValueError('Seleccione un CSV y un máximo de filas mayor que 1.')
        folder = self.root/'data/herramientas/divididos'/source.stem
        folder.mkdir(parents=True,exist_ok=True)
        stream = None
        parts = []
        try:
            with source.open(encoding='utf-8-sig',newline='') as incoming:
                reader = csv.reader(incoming)
                header = next(reader,None)
                for index,row in enumerate(reader):
                    if self.stop.is_set():
                        raise asyncio.CancelledError()
                    if index % (max_rows-1) == 0:
                        if stream:
                            stream.close()
                        path = folder/f'{source.stem}_parte{len(parts)+1}.csv'
                        stream = path.open('w',encoding='utf-8-sig',newline='')
                        parts.append(str(path))
                        writer = csv.writer(stream)
                        writer.writerow(header)
                    writer.writerow(row)
        finally:
            if stream:
                stream.close()
        return {'splitFolder':str(folder),'parts':parts}
