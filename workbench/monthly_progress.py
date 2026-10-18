"""Bitácora mensual de solo lectura, sin cargar motores ni iniciar consultas."""
import calendar
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from chc_runtime.manifest_coverage import cumulative_days, day_ranges

if __package__:
    from .daily_marks import DailyMarks
else:
    from daily_marks import DailyMarks

MODULES = [('detalles','Detalles'),('duas_transito','Tránsito'),('talon','Talón'),
           ('xmovimientos','XMovimientos'),('bls','BLs'),('manifiestos','Manifiestos')]
FLOWS = [('tabla','Manifiestos'),('conocimientos','Conocimientos'),('duas','DUAs'),
         ('movimientos','Movimientos'),('contenedores','Contenedores')]
MONTHS = ('enero','febrero','marzo','abril','mayo','junio','julio','agosto',
          'septiembre','octubre','noviembre','diciembre')
LABELS = {'completed':'Completado','up_to_date':'Al día','ready':'Lote listo','partial':'Parcial',
          'pending':'Pendiente','running':'En curso','missing':'Sin iniciar','unknown':'Sin verificar'}


@contextmanager
def readonly(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=0.5)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db
    finally:db.close()


def period(value):
    value=str(value).strip().lower()
    match=re.fullmatch(r'(20\d{2})-(0[1-9]|1[0-2])',value)
    if match:return value
    for index,name in enumerate(MONTHS,1):
        match=re.fullmatch(name+r'\s*(20\d{2}|\d{2})',value)
        if match:return f'{int(match[1]) if len(match[1])==4 else 2000+int(match[1]):04d}-{index:02d}'
    return ''


def month_days(key):
    year,month=map(int,key.split('-'))
    return {date(year,month,n).isoformat() for n in range(1,calendar.monthrange(year,month)[1]+1)}


def covered(scope,key):
    if scope.get('ids') or scope.get('limit') or scope.get('courier') not in (None,'todos'):
        return set()
    days=month_days(key)
    first,last=min(days),max(days)
    start,end=scope.get('desde') or scope.get('start') or first,scope.get('hasta') or scope.get('end') or last
    start,end=date.fromisoformat(start),date.fromisoformat(end)
    if start>end or start.isoformat()<first or end.isoformat()>last:raise ValueError('Rango fuera del mes')
    return {d for d in days if start.isoformat()<=d<=end.isoformat()}


def state(total,saved,running,complete=False):
    if running:return 'running'
    if saved==total:return 'completed' if complete else 'ready'
    return 'partial' if saved else 'pending'


def jobs_revision(db):
    columns={r[1] for r in db.execute('PRAGMA table_info(jobs)')}
    fields=["coalesce(sum(attempts),0)" if 'attempts' in columns else '0',
            "coalesce(max(updated),'')" if 'updated' in columns else "''"]
    return list(db.execute('SELECT '+','.join(fields)+' FROM jobs').fetchone())


class MonthlyReader:
    def __init__(self,roots,today=None,overrides_file=None):
        self.roots={key:Path(value) for key,value in roots.items()}
        now=datetime.now(timezone(timedelta(hours=-6)))
        self.today=today or now.date()
        self.cutoff=self.today-timedelta(days=2 if today is None and now.hour==0 and now.minute==0 else 1)
        self.entries=[]
        self.errors=[]
        self.calendar_marks={}
        self.used_manual_days={}
        for module,root in self.roots.items():
            if module not in ('detalles','duas_transito','talon','xmovimientos'):continue
            marks=DailyMarks(root)
            try:
                if marks.error:raise ValueError(marks.error)
                dates={date.fromisoformat(day).isoformat() for day in marks.values}
                self.calendar_marks[module]={day for day in dates if day<=self.cutoff.isoformat()}
            except (ValueError,TypeError):
                self.calendar_marks[module]=set()
                self.errors.append(str(marks.path))
            self.used_manual_days[module]=set()
        project=Path(__file__).resolve().parents[1]
        production=bool(self.roots) and all(root.resolve()==project/'bots'/module for module,root in self.roots.items())
        self.overrides_file=Path(overrides_file) if overrides_file else (project/'runtime/workbench/monthly_overrides.json' if production else next(iter(self.roots.values()),project/'runtime/workbench')/'data/monthly_overrides.json')
        try:self.overrides=json.loads(self.overrides_file.read_text(encoding='utf-8')) if self.overrides_file.exists() else {}
        except (OSError,ValueError):self.overrides={};self.errors.append(str(self.overrides_file))

    def required_days(self,key):
        return {d for d in month_days(key) if d<=self.cutoff.isoformat()}

    def coverage_status(self,key,days):
        required=self.required_days(key)
        if not required or not required<=set(days):return ''
        return 'completed' if max(month_days(key))<=self.cutoff.isoformat() else 'up_to_date'

    def add(self,key,module,flow,label,total,saved,running=0,days=(),scope='',status=None,group='',omitted=0,revision=None,manual_days=()):
        if not period(key):return
        days=set(days)
        complete=self.coverage_status(key,days)=='completed'
        self.entries.append(dict(period=key,module=module,flow=flow,name=label,total=total,
            saved=saved,omitted=omitted,revision=revision,running=running,days=days,scope=scope,group=group,
            status=status or state(total,saved+omitted,running,complete)))
        if manual_days:self.entries[-1]['manualDays']=sorted(manual_days)

    def failed(self,path,key='',module='',flow='',label=''):
        self.errors.append(str(path))
        if key:self.add(key,module,flow,label,0,0,status='unknown',scope='No se pudo leer el progreso; vuelve a actualizar.')

    def duas(self,module,root):
        catalog=root/'data/queues/catalog.sqlite3'
        if not catalog.exists():return
        try:
            with readonly(catalog) as db:
                records=db.execute('SELECT id,name,filename,source_path,source_sheet FROM saved_tables WHERE deleted=0').fetchall()
        except (OSError,sqlite3.Error,ValueError):self.failed(catalog);return
        ledger=root/'data/daily/calendar.sqlite3'
        for table_id,name,filename,source,sheet in records:
            key=period(source.removeprefix('daily://')) if source.startswith('daily://') else period(name) or period(sheet)
            if not key:continue
            path=(catalog.parent/filename).resolve()
            if path.parent!=catalog.parent.resolve():self.failed(path,key,module,'',name);continue
            try:
                with readonly(path) as db:
                    counts=dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
                    saved=db.execute("SELECT count(*) FROM jobs WHERE status='succeeded' AND result IS NOT NULL").fetchone()[0]
                    total=sum(counts.values())
                    revision=jobs_revision(db)
                    omitted=0
                    empties=0
                    verified="j.status='succeeded' AND j.result IS NOT NULL"
                    if module=='xmovimientos' and db.execute("SELECT 1 FROM sqlite_master WHERE name='empty_observations'").fetchone():
                        empties=db.execute("SELECT count(*) FROM jobs j JOIN empty_observations o ON o.job_id=j.id WHERE j.status='empty'").fetchone()[0]
                        verified="("+verified+") OR (j.status='empty' AND EXISTS (SELECT 1 FROM empty_observations o WHERE o.job_id=j.id))"
                    days=set()
                    manual_days=set()
                    running=counts.get('running',0)
                    if ledger.exists():
                        db.execute('ATTACH DATABASE ? AS calendar',(ledger.resolve().as_uri()+'?mode=ro',))
                        details=db.execute(f'''SELECT c.day,c.state,c.base_ready,c.total,count(d.dua),
                            coalesce(sum(CASE WHEN {verified} THEN 1 ELSE 0 END),0)
                            FROM calendar.days c LEFT JOIN calendar.daily_duas d ON d.day=c.day
                            LEFT JOIN jobs j ON j.dua=d.dua
                            WHERE c.table_id=? AND c.day LIKE ? GROUP BY c.day''',(table_id,key+'-%')).fetchall()
                        days={day for day,status,base,expected,actual,confirmed in details
                              if day<self.today.isoformat() and base and expected==actual and
                              ((status=='completed' and actual==confirmed) or (module!='detalles' and status=='omitted'))}
                        manual_days={row[0] for row in details}&self.calendar_marks.get(module,set())
                        self.used_manual_days[module].update(manual_days)
                        days.update(manual_days)
                        running=max(running,sum(row[1] in ('downloading','processing') for row in details))
                        if module!='detalles' or manual_days:
                            marks=','.join('?' for _ in manual_days) or 'NULL'
                            omitted=db.execute(f'''SELECT count(*) FROM jobs j WHERE j.status IN ('pending','retry','invalid')
                                AND EXISTS (SELECT 1 FROM calendar.daily_duas d JOIN calendar.days c ON c.day=d.day
                                WHERE d.dua=j.dua AND c.table_id=? AND c.day LIKE ? AND c.day<=?
                                AND ((? AND c.state='omitted') OR c.day IN ({marks})))''',
                                (table_id,key+'-%',self.cutoff.isoformat(),module!='detalles',*sorted(manual_days))).fetchone()[0]
                full=bool(self.coverage_status(key,days))
                detail=f'{saved:,} guardados · {empties:,} vacíos / {total:,} DUAs consultados' if module=='xmovimientos' else f'{saved:,} / {total:,} DUAs confirmados'
                if manual_days:
                    detail+=f' · {len(days)} / {len(month_days(key))} días completos ({len(days-manual_days)} verificados · {len(manual_days)} manuales)'
                else:
                    detail+=f' · {len(days)} / {len(month_days(key))} días verificados' if source.startswith('daily://') or days else ' · cobertura del archivo sin verificar'
                if omitted:detail+=f' · {omitted:,} omitidos fuera del resultado final, disponibles para reintento'
                self.add(key,module,'',name,total,saved+empties,running,days,detail,
                    status='running' if running else 'partial' if saved+empties+omitted==total and source.startswith('daily://') and not full else None,
                    omitted=omitted,revision=revision,manual_days=manual_days)
            except (OSError,sqlite3.Error,ValueError,TypeError):self.failed(path,key,module,'',name)

    def missing_bases(self,module,root):
        ledger=root/'data/daily/calendar.sqlite3'
        if not ledger.exists():return
        try:
            with readonly(ledger) as db:
                rows=db.execute("SELECT day,state FROM days WHERE base_ready=0 AND table_id='' AND day<?",(self.today.isoformat(),)).fetchall()
            groups={}
            for day,status in rows:groups.setdefault(day[:7],[]).append((day,status))
            for key,items in groups.items():
                omitted={day for day,status in items if status=='omitted' and module!='detalles'}
                manual_days={day for day,status in items}&self.calendar_marks.get(module,set())
                self.used_manual_days[module].update(manual_days)
                accepted=omitted|manual_days
                detail=f'{len(items)-len(accepted)} días pendientes de base · {len(omitted-manual_days)} días omitidos'
                if manual_days:detail+=f' · {len(manual_days)} días completados manualmente'
                self.add(key,module,'','Días sin base',len(items),0,days=accepted,omitted=len(accepted),
                         running=sum(status in ('downloading','processing') for day,status in items),
                         manual_days=manual_days,scope=detail+'; se pueden reintentar manualmente.')
        except (OSError,sqlite3.Error,ValueError):self.failed(ledger)

    def manual_only_days(self,module):
        # El usuario también puede aceptar días aún sin base/calendario persistido.
        remaining=self.calendar_marks.get(module,set())-self.used_manual_days.get(module,set())
        for key in sorted({day[:7] for day in remaining}):
            days={day for day in remaining if day.startswith(key+'-')}
            self.add(key,module,'','Días marcados manualmente',0,0,days=days,manual_days=days,
                     scope=f'{len(days)} días completados manualmente; base no verificada, disponibles para reintento.')

    def manifests(self,root):
        for flow,label in FLOWS:
            folder=root/'data/jobs'/flow
            if not folder.exists():continue
            for path in sorted(folder.rglob('*.sqlite3')):
                key=''
                try:
                    with readonly(path) as db:
                        scope=json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0])
                        key=f"{int(scope['year']):04d}-{int(scope['month']):02d}"
                        if not period(key):raise ValueError('Mes inválido')
                        counts=dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state'))
                        total=sum(counts.values())
                        revision=jobs_revision(db)
                        columns={r[1] for r in db.execute('PRAGMA table_info(jobs)')}
                        excluded="state IN ('Excluido','Omitido')"+(" OR (state='Pendiente' AND attempts>=3)" if 'attempts' in columns else '')
                        omitted=db.execute('SELECT count(*) FROM jobs WHERE '+excluded).fetchone()[0]
                        saved=db.execute("SELECT count(*) FROM jobs j JOIN manifests m ON m.id=j.id WHERE j.state='Guardado'").fetchone()[0]
                        selected=db.execute('SELECT 1 FROM selection WHERE id=1').fetchone()
                        partial=db.execute('SELECT count(*) FROM partial_pages WHERE manifest NOT IN (SELECT id FROM jobs WHERE '+excluded+')').fetchone()[0]
                        last=db.execute('SELECT state,finished FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
                        confirmed=bool(selected and not partial and last and last[0]=='Finalizada' and last[1] and saved+omitted==total)
                        accumulated=cumulative_days(db,allow_omitted=True)
                        unfiltered=not scope.get('ids') and not scope.get('limit') and scope.get('courier') in (None,'todos')
                        days=(accumulated if unfiltered else set()) if accumulated is not None else covered(scope,key) if confirmed else set()
                    detail=f"{scope.get('mode','')} · {saved:,} / {total:,} confirmados"
                    detail+=f" · {scope.get('desde') or min(month_days(key))} a {scope.get('hasta') or max(month_days(key))}"
                    if accumulated is not None:
                        detail+=' · cobertura acumulada: '+(', '.join(a+' a '+b for a,b in day_ranges(days)) or 'sin consultas completas')
                    if scope.get('ids') or scope.get('limit') or scope.get('courier') not in (None,'todos'):detail+=' · selección filtrada'
                    if omitted:detail+=f' · {omitted} omitidos, disponibles para reintento'
                    status=state(total,saved+omitted,counts.get('Descargando',0),self.coverage_status(key,days)=='completed')
                    if status=='ready' and not confirmed:status='pending'
                    self.add(key,'manifiestos',flow,label,total,saved,counts.get('Descargando',0),days,detail,status,scope.get('mode',''),omitted,revision)
                except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,IndexError):self.failed(path,key,'manifiestos',flow,label)

    def bls(self,root):
        index=root/'data/workbench/bls/session.json'
        if not index.exists():return
        try:history=json.loads(index.read_text(encoding='utf-8'))['history']
        except (OSError,ValueError,KeyError):self.failed(index);return
        for record in history:
            scope={}
            try:
                info=Path(record['spec']['input']).with_suffix('.json')
                if info.exists():scope=json.loads(info.read_text(encoding='utf-8'))
                paths=sorted(Path(record['work']).glob('**/SQLite/bls.sqlite3'))
                for path in paths:
                    with readonly(path) as db:
                        columns={r[1] for r in db.execute('PRAGMA table_info(jobs)')}
                        last=db.execute('SELECT state,finished FROM runs ORDER BY rowid DESC LIMIT 1').fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE name='runs'").fetchone() else None
                        finalized=bool(last and last[0] in ('Guardado','Pendiente') and last[1])
                        excluded="state IN ('Excluido','Omitido')"+(" OR (state='Pendiente' AND attempts>=3)" if 'attempts' in columns and finalized else '')
                        attempt_field='coalesce(sum(attempts),0)' if 'attempts' in columns else '0'
                        updated_field="coalesce(max(updated),'')" if 'updated' in columns else "''"
                        rows=db.execute('''SELECT json_extract(payload,'$.Mes'),state,count(*),
                            sum(CASE WHEN state='Guardado' AND result_count=(SELECT count(*) FROM results r WHERE r.job=jobs.id)
                                     THEN 1 ELSE 0 END),sum(CASE WHEN '''+excluded+''' THEN 1 ELSE 0 END),'''+attempt_field+','+updated_field+'''
                                     FROM jobs GROUP BY json_extract(payload,'$.Mes'),state''').fetchall()
                    groups={}
                    revisions={}
                    for raw,status,count,saved,omitted,attempts,updated in rows:
                        key=period(raw)
                        if not key:continue
                        item=groups.setdefault(key,dict(total=0,saved=0,running=0,omitted=0))
                        item['total']+=count;item['saved']+=saved
                        item['omitted']+=omitted
                        revisions.setdefault(key,[]).append([status,attempts,updated])
                        if status=='Descargando':item['running']+=count
                    for key,counts in groups.items():
                        coverage=[v for v in scope.get('coverage',[]) if v['key'].split('|')[0]==key]
                        ranges=[]
                        for item in coverage:
                            current=month_days(key) if item.get('fullMonth') else set()
                            for start,end in item.get('ranges',[]):current.update(covered({'start':start,'end':end},key))
                            ranges.append(current)
                        days=set.intersection(*ranges) if ranges else set()
                        full=bool(days and month_days(key)<=days)
                        if counts['saved']+counts['omitted']!=counts['total']:days=set()
                        detail=f"{counts['saved']:,} / {counts['total']:,} BL confirmados"
                        detail+=' · base mensual de Conocimientos' if full else ' · cobertura de la base sin verificar'
                        if counts['omitted']:detail+=f" · {counts['omitted']} omitidos, disponibles para reintento"
                        self.add(key,'bls','',record['name'],**counts,days=days,scope=detail,revision=revisions[key])
            except (OSError,sqlite3.Error,ValueError,TypeError,KeyError):
                self.failed(index)
                for key in record.get('config',{}).get('knowledgePeriods',[]):
                    self.add(key.split('|')[0],'bls','',record.get('name','BLs'),0,0,
                             status='unknown',scope='No se pudo leer el progreso; vuelve a actualizar.')

    def cell(self,key,module,flow=None):
        entries=[e for e in self.entries if e['period']==key and e['module']==module and (flow is None or e['flow']==flow)]
        groups={}
        for entry in entries:groups.setdefault(entry['group'],set()).update(entry['days'])
        coverage=[bool(self.coverage_status(key,days)) for days in groups.values()]
        full=(all(coverage) if module=='manifiestos' else any(coverage)) if coverage else False
        # Un lote anterior completo no oculta una ampliación pendiente del mes.
        full=full and all(e['saved']+e['omitted']==e['total'] and not e['running'] and
                          e['status'] not in ('unknown','pending') for e in entries)
        status='missing'
        if entries:
            if full:status=self.coverage_status(key,set().union(*groups.values()))
            else:
                status=next((s for s in ('running','unknown','partial','pending','ready') if any(e['status']==s for e in entries)),'ready')
        detail='\n'.join(e['name']+': '+LABELS[e['status']]+' · '+e['scope'] for e in entries) or 'No hay una descarga guardada para este mes.'
        manual_days=set().union(*(set(e.get('manualDays',[])) for e in entries))
        accepted_days=set().union(*(e['days'] for e in entries))
        if manual_days:
            detail=f'{len(accepted_days)} / {len(month_days(key))} días completos ({len(accepted_days-manual_days)} verificados · {len(manual_days)} manuales).\n'+detail
        target=module+(':'+flow if flow else '')
        marker=self.overrides.get(key+'|'+target,{})
        manual=bool(entries and marker.get('fingerprint')==self.fingerprint(key,target) and not any(e['running'] or e['status']=='unknown' for e in entries))
        if manual:
            status='completed'
            detail='Cierre manual: pendientes excluidos del resultado final; siguen disponibles para reintento.\n'+detail
        calendar_complete=bool(manual_days and status in ('completed','up_to_date'))
        if calendar_complete:
            detail=f'{len(manual_days)} días aceptados manualmente; pendientes conservados para reintento.\n'+detail
        if status=='completed' and not manual and not calendar_complete:detail='Mes completo verificado para las modalidades seleccionadas.\n'+detail
        if status=='up_to_date':detail='Descargas terminadas hasta '+self.cutoff.isoformat()+'. El mes sigue abierto.\n'+detail
        label='Completado manual' if manual or (calendar_complete and status=='completed') else 'Al día (manual)' if calendar_complete else LABELS[status]
        display_days=self.required_days(key) if manual else set.intersection(*groups.values()) if module=='manifiestos' and groups else accepted_days
        return dict(module=module,status=status,label=label,detail=detail,manual=manual,
                    manualDays=len(manual_days),verifiedDays=len(accepted_days-manual_days),coveredDays=len(accepted_days),
                    displayDays=len(display_days),displayDates=sorted(display_days))

    def fingerprint(self,key,target):
        module,_,flow=target.partition(':')
        entries=[e for e in self.entries if e['period']==key and e['module']==module and (not flow or e['flow']==flow)]
        value=[{**e,'days':sorted(e['days'])} for e in entries]
        return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def mark_complete(self,key,target,enabled):
        module,_,flow=target.partition(':')
        if module not in dict(MODULES) or (flow and flow not in dict(FLOWS)) or (flow and module!='manifiestos'):
            raise ValueError('Bot o procedimiento no válido.')
        entry_key=key+'|'+target
        if enabled:
            if not period(key) or key>self.today.strftime('%Y-%m'):raise ValueError('El mes todavía no está disponible.')
            entries=[e for e in self.entries if e['period']==key and e['module']==module and (not flow or e['flow']==flow)]
            if not entries or any(e['running'] or e['status']=='unknown' for e in entries):
                raise ValueError('Primero termina la descarga y verifica sus resultados guardados.')
            self.overrides[entry_key]={'fingerprint':self.fingerprint(key,target),'markedAt':datetime.now(timezone.utc).isoformat()}
        else:self.overrides.pop(entry_key,None)
        self.overrides_file.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.overrides_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.overrides,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temporary,self.overrides_file)

    def read(self):
        for module,root in self.roots.items():
            if module=='manifiestos':self.manifests(root)
            elif module=='bls':self.bls(root)
            else:
                self.duas(module,root)
                self.missing_bases(module,root)
                self.manual_only_days(module)
        keys=sorted({e['period'] for e in self.entries},reverse=True)
        rows=[]
        for key in keys:
            cells=[self.cell(key,module) for module,_ in MODULES[:-1]]
            flows=[self.cell(key,'manifiestos',flow) for flow,_ in FLOWS]
            completed=sum(c['status']=='completed' for c in flows)
            current=sum(c['status'] in ('completed','up_to_date') for c in flows)
            status='completed' if completed==5 else 'up_to_date' if current==5 else 'running' if any(c['status']=='running' for c in flows) else 'partial' if any(c['status']!='missing' for c in flows) else 'missing'
            cells.append(dict(module='manifiestos',status=status,label=f'{completed}/5 completos' if completed else LABELS[status],
                displayDays=len(set.intersection(*(set(c['displayDates']) for c in flows))),
                detail='\n\n'.join(label+': '+cell['label']+'\n'+cell['detail'] for (_,label),cell in zip(FLOWS,flows))))
            year,month=map(int,key.split('-'))
            rows.append(dict(period=key,label=MONTHS[month-1].capitalize()+' '+str(year),cells=cells,
                             daysInMonth=len(month_days(key)),
                             completed=sum(c['status']=='completed' for c in cells),upToDate=sum(c['status']=='up_to_date' for c in cells),procedures=flows))
        return dict(rows=rows,errors=len(self.errors))
