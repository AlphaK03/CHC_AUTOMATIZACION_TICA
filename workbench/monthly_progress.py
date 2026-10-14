"""Bitácora mensual de solo lectura, sin cargar motores ni iniciar consultas."""
import calendar
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3

MODULES = [('detalles','Detalles'),('duas_transito','Tránsito'),('talon','Talón'),
           ('xmovimientos','XMovimientos'),('bls','BLs'),('manifiestos','Manifiestos')]
FLOWS = [('tabla','Manifiestos'),('conocimientos','Conocimientos'),('duas','DUAs'),
         ('movimientos','Movimientos'),('contenedores','Contenedores')]
MONTHS = ('enero','febrero','marzo','abril','mayo','junio','julio','agosto',
          'septiembre','octubre','noviembre','diciembre')
LABELS = {'completed':'Completado','ready':'Lote listo','partial':'Parcial',
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


class MonthlyReader:
    def __init__(self,roots,today=None):
        self.roots={key:Path(value) for key,value in roots.items()}
        self.today=today or datetime.now(timezone(timedelta(hours=-6))).date()
        self.entries=[]
        self.errors=[]

    def add(self,key,module,flow,label,total,saved,running=0,days=(),scope='',status=None,group=''):
        if not period(key):return
        days=set(days)
        complete=month_days(key)<=days and max(days)<self.today.isoformat()
        self.entries.append(dict(period=key,module=module,flow=flow,name=label,total=total,
            saved=saved,running=running,days=days,scope=scope,group=group,
            status=status or state(total,saved,running,complete)))

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
                    empties=0
                    verified="j.status='succeeded' AND j.result IS NOT NULL"
                    if module=='xmovimientos' and db.execute("SELECT 1 FROM sqlite_master WHERE name='empty_observations'").fetchone():
                        empties=db.execute("SELECT count(*) FROM jobs j JOIN empty_observations o ON o.job_id=j.id WHERE j.status='empty'").fetchone()[0]
                        verified="("+verified+") OR (j.status='empty' AND EXISTS (SELECT 1 FROM empty_observations o WHERE o.job_id=j.id))"
                    days=set()
                    if ledger.exists():
                        db.execute('ATTACH DATABASE ? AS calendar',(ledger.resolve().as_uri()+'?mode=ro',))
                        details=db.execute(f'''SELECT c.day,c.state,c.base_ready,c.total,count(d.dua),
                            coalesce(sum(CASE WHEN {verified} THEN 1 ELSE 0 END),0)
                            FROM calendar.days c LEFT JOIN calendar.daily_duas d ON d.day=c.day
                            LEFT JOIN jobs j ON j.dua=d.dua
                            WHERE c.table_id=? AND c.day LIKE ? GROUP BY c.day''',(table_id,key+'-%')).fetchall()
                        days={day for day,status,base,expected,actual,confirmed in details
                              if status=='completed' and base and expected==actual==confirmed and day<self.today.isoformat()}
                full=month_days(key)<=days
                detail=f'{saved:,} guardados · {empties:,} vacíos / {total:,} DUAs consultados' if module=='xmovimientos' else f'{saved:,} / {total:,} DUAs confirmados'
                detail+=f' · {len(days)} / {len(month_days(key))} días verificados' if source.startswith('daily://') or days else ' · cobertura del archivo sin verificar'
                self.add(key,module,'',name,total,saved+empties,counts.get('running',0),days,detail,
                    status='partial' if saved+empties==total and source.startswith('daily://') and not full else None)
            except (OSError,sqlite3.Error,ValueError,TypeError):self.failed(path,key,module,'',name)

    def missing_bases(self,module,root):
        ledger=root/'data/daily/calendar.sqlite3'
        if not ledger.exists():return
        try:
            with readonly(ledger) as db:
                rows=db.execute("SELECT substr(day,1,7),count(*) FROM days WHERE base_ready=0 AND table_id='' AND day<? GROUP BY substr(day,1,7)",(self.today.isoformat(),)).fetchall()
            for key,count in rows:
                self.add(key,module,'','Días sin base',count,0,status='pending',scope=f'{count} días pendientes de obtener su base; se pueden reintentar manualmente.')
        except (OSError,sqlite3.Error,ValueError):self.failed(ledger)

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
                        saved=db.execute("SELECT count(*) FROM jobs j JOIN manifests m ON m.id=j.id WHERE j.state='Guardado'").fetchone()[0]
                        selected=db.execute('SELECT 1 FROM selection WHERE id=1').fetchone()
                        partial=db.execute('SELECT count(*) FROM partial_pages').fetchone()[0]
                        last=db.execute('SELECT state,finished FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
                        confirmed=bool(selected and not partial and last and last[0]=='Finalizada' and last[1] and saved==total)
                        if counts.get('Excluido',0):confirmed=False
                        days=covered(scope,key) if confirmed else set()
                    detail=f"{scope.get('mode','')} · {saved:,} / {total:,} confirmados"
                    detail+=f" · {scope.get('desde') or min(month_days(key))} a {scope.get('hasta') or max(month_days(key))}"
                    if scope.get('ids') or scope.get('limit') or scope.get('courier') not in (None,'todos'):detail+=' · selección filtrada'
                    status=state(total,saved,counts.get('Descargando',0),bool(days==month_days(key) and max(days)<self.today.isoformat()))
                    if status=='ready' and not confirmed:status='pending'
                    self.add(key,'manifiestos',flow,label,total,saved,counts.get('Descargando',0),days,detail,status,scope.get('mode',''))
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
                        rows=db.execute('''SELECT json_extract(payload,'$.Mes'),state,count(*),
                            sum(CASE WHEN state='Guardado' AND result_count=(SELECT count(*) FROM results r WHERE r.job=jobs.id)
                                     THEN 1 ELSE 0 END) FROM jobs GROUP BY json_extract(payload,'$.Mes'),state''').fetchall()
                    groups={}
                    for raw,status,count,saved in rows:
                        key=period(raw)
                        if not key:continue
                        item=groups.setdefault(key,dict(total=0,saved=0,running=0))
                        item['total']+=count;item['saved']+=saved
                        if status=='Descargando':item['running']+=count
                    for key,counts in groups.items():
                        coverage=[v for v in scope.get('coverage',[]) if v['key'].split('|')[0]==key]
                        full=bool(coverage and all(v.get('fullMonth') for v in coverage))
                        days=month_days(key) if full and counts['saved']==counts['total'] else set()
                        detail=f"{counts['saved']:,} / {counts['total']:,} BL confirmados"
                        detail+=' · base mensual de Conocimientos' if full else ' · cobertura de la base sin verificar'
                        self.add(key,'bls','',record['name'],**counts,days=days,scope=detail)
            except (OSError,sqlite3.Error,ValueError,TypeError,KeyError):
                self.failed(index)
                for key in record.get('config',{}).get('knowledgePeriods',[]):
                    self.add(key.split('|')[0],'bls','',record.get('name','BLs'),0,0,
                             status='unknown',scope='No se pudo leer el progreso; vuelve a actualizar.')

    def cell(self,key,module,flow=None):
        entries=[e for e in self.entries if e['period']==key and e['module']==module and (flow is None or e['flow']==flow)]
        groups={}
        for entry in entries:groups.setdefault(entry['group'],set()).update(entry['days'])
        coverage=[month_days(key)<=days and max(days)<self.today.isoformat() for days in groups.values()]
        full=(all(coverage) if module=='manifiestos' else any(coverage)) if coverage else False
        # Un lote anterior completo no oculta una ampliación pendiente del mes.
        full=full and all(e['saved']==e['total'] and not e['running'] and
                          e['status'] not in ('unknown','pending') for e in entries)
        status='missing'
        if entries:
            if full:status='completed'
            else:
                status=next((s for s in ('running','unknown','partial','pending','ready') if any(e['status']==s for e in entries)),'ready')
        detail='\n'.join(e['name']+': '+LABELS[e['status']]+' · '+e['scope'] for e in entries) or 'No hay una descarga guardada para este mes.'
        if status=='completed':detail='Mes completo verificado para las modalidades seleccionadas.\n'+detail
        return dict(module=module,status=status,label=LABELS[status],detail=detail)

    def read(self):
        for module,root in self.roots.items():
            if module=='manifiestos':self.manifests(root)
            elif module=='bls':self.bls(root)
            else:
                self.duas(module,root)
                self.missing_bases(module,root)
        keys=sorted({e['period'] for e in self.entries},reverse=True)
        rows=[]
        for key in keys:
            cells=[self.cell(key,module) for module,_ in MODULES[:-1]]
            flows=[self.cell(key,'manifiestos',flow) for flow,_ in FLOWS]
            completed=sum(c['status']=='completed' for c in flows)
            status='completed' if completed==5 else 'running' if any(c['status']=='running' for c in flows) else 'partial' if any(c['status']!='missing' for c in flows) else 'missing'
            cells.append(dict(module='manifiestos',status=status,label=f'{completed}/5 completos' if completed else LABELS[status],
                detail='\n\n'.join(label+': '+cell['label']+'\n'+cell['detail'] for (_,label),cell in zip(FLOWS,flows))))
            year,month=map(int,key.split('-'))
            rows.append(dict(period=key,label=MONTHS[month-1].capitalize()+' '+str(year),cells=cells,
                             completed=sum(c['status']=='completed' for c in cells),procedures=flows))
        return dict(rows=rows,errors=len(self.errors))
