"""Inicio mensual explícito desde Qt, reutilizando los workers y su recuperación."""
import calendar
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

SPECS=[('detalles','Detalles','',20,1),('duas_transito','DUAs Tránsito','',20,1),
       ('talon','Talón','',20,1),('xmovimientos','XMovimientos','',20,1),
       ('manifiestos','Manifiestos · Tabla','tabla',1,1),
       ('manifiestos','Manifiestos · Conocimientos','conocimientos',32,32),
       ('manifiestos','Manifiestos · DUAs','duas',32,4),
       ('manifiestos','Manifiestos · Movimientos','movimientos',32,4),
       ('manifiestos','Manifiestos · Contenedores','contenedores',32,5),
       ('bls','BLs','bls',20,2)]
ACTIVE={'configuring','starting','running','finishing','dependency','catalog'}


def month_range(year,month):
    year,month=int(year),int(month)
    if not 2000<=year<=2100 or not 1<=month<=12:raise ValueError('Elige un año y mes válidos.')
    now=datetime.now(timezone(timedelta(hours=-6))).date()
    start=now.replace(year=year,month=month,day=1)
    end=start.replace(day=calendar.monthrange(year,month)[1])
    if end>=now:raise ValueError('Elige un mes terminado para iniciar su descarga completa.')
    return start.isoformat(),end.isoformat()


class MonthLauncher(QObject):
    changed=Signal()
    choicesChanged=Signal()

    def __init__(self,bridges,parent=None):
        super().__init__(parent)
        self.bridges=bridges
        previous=datetime.now(timezone(timedelta(hours=-6))).date().replace(day=1)-timedelta(days=1)
        self._year,self._month=previous.year,previous.month
        self._modes=['maritimo']
        self._items=[dict(id=flow or module,module=module,label=label,flow=flow,maximum=maximum,
                          workers=workers,selected=False,edited=False,initialized=False)
                     for module,label,flow,maximum,workers in SPECS]
        self.tasks={}
        self.generation=0
        self._message='Elige un mes terminado y marca los procesos que quieres iniciar.'
        self.range=('', '')
        self._availability=None
        for module,bridge in bridges.items():
            if bridge:
                bridge.changed.connect(self.sync)
                bridge.eventReceived.connect(lambda event,m=module:self.receive_event(m,event))
        self.timer=QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.expire)
        self.sync()

    def bridge(self,item):return self.bridges.get(item['module'])
    def channel(self,item):
        bridge=self.bridge(item)
        return bridge.channels[item['flow']] if bridge and item['flow'] else bridge

    def occupied(self,item):
        bridge=self.bridge(item);channel=self.channel(item)
        return bool(channel and (channel.busy or getattr(bridge,'_closing',False) or
                    (item['module']=='bls' and getattr(bridge,'_knowledge_request',None) is not None)))

    @Property('QVariantList',notify=changed)
    def items(self):
        result=[]
        for item in self._items:
            bridge=self.bridge(item);task=self.tasks.get(item['id'],{})
            result.append({**item,'status':task.get('label') or ('Ocupado' if self.occupied(item) else
                          'Preparando módulo' if bridge and bridge.enabled and not item['flow'] and not bridge.ready else
                          'Listo' if bridge and bridge.enabled else 'No disponible'),
                          'available':bool(bridge and bridge.enabled),'state':task.get('stage','')})
        return result

    @Property(bool,notify=changed)
    def active(self):return any(t['stage'] in ACTIVE for t in self.tasks.values())
    @Property(str,notify=changed)
    def message(self):return self._message
    @Property(int,notify=changed)
    def year(self):return self._year
    @Property(int,notify=changed)
    def month(self):return self._month
    @Property('QVariantList',notify=changed)
    def modes(self):return self._modes
    @Property(str,notify=choicesChanged)
    def selectionSummary(self):
        chosen=[i for i in self._items if i['selected']]
        return f"{len(chosen)} procesos · {sum(i['workers'] for i in chosen)} trabajadores"

    @Property(bool,notify=choicesChanged)
    def canStart(self):
        chosen=[i for i in self._items if i['selected']]
        return bool(chosen) and all(self.bridge(i) and self.bridge(i).enabled and
            (bool(i['flow'] and i['module']!='bls') or self.channel(i).ready) for i in chosen)

    @Slot(int,int)
    def setPeriod(self,year,month):
        if not self.active:self._year,self._month=year,month;self.changed.emit()

    @Slot(str,bool)
    def setSelected(self,key,selected):
        if self.active:return
        item=next(i for i in self._items if i['id']==key);item['selected']=selected
        self.choicesChanged.emit()

    @Slot(bool)
    def selectAll(self,selected):
        if self.active:return
        for item in self._items:item['selected']=selected and bool(self.bridge(item) and self.bridge(item).enabled)
        self.changed.emit();self.choicesChanged.emit()

    @Slot(str,int)
    def setWorkers(self,key,workers):
        if self.active:return
        item=next(i for i in self._items if i['id']==key)
        item.update(workers=max(1,min(item['maximum'],workers)),edited=True)
        self.choicesChanged.emit()

    @Slot(str,bool)
    def setMode(self,mode,selected):
        if self.active or mode not in ('maritimo','aereo','terrestre'):return
        self._modes=[m for m in ('maritimo','aereo','terrestre') if m in
                     (set(self._modes)|{mode} if selected else set(self._modes)-{mode})]
        self.changed.emit()

    @Slot()
    def sync(self):
        modified=False
        for item in self._items:
            channel=self.channel(item)
            if not item['initialized'] and channel and channel.ready:
                config=channel.snapshot.get('config',{}) if item['flow'] else channel.config
                if not item['edited']:item['workers']=max(1,min(item['maximum'],int(config.get('workers' if item['flow'] else 'cant_hilos',item['workers']))))
                item['initialized']=True;modified=True
        available=tuple((bool(self.bridge(i) and self.bridge(i).enabled),bool(self.channel(i) and self.channel(i).ready),self.occupied(i)) for i in self._items)
        if available!=self._availability:self._availability=available;modified=True
        if modified:self.changed.emit();self.choicesChanged.emit()
        for task in list(self.tasks.values()):
            channel=self.channel(task)
            if (task['owned'] and task['stage'] in ACTIVE or task.get('watching')) and channel and not channel.ready and not channel.busy and getattr(channel,'error',''):
                task['watching']=False
                self.mark(task,'error' if task['owned'] else 'skipped','El proceso se desconectó; avance conservado')
                bls=self.tasks.get('bls')
                if task['id']=='conocimientos' and bls and bls['stage']=='dependency':self.mark(bls,'blocked','Conocimientos se desconectó; BLs no se inició')

    def mark(self,task,stage,label):
        task.update(stage=stage,label=label)
        self.changed.emit()
        if not self.active:self.timer.stop()

    def matching_knowledge(self,task):
        config=self.channel(task).snapshot.get('config',{})
        return (config.get('year')==self._year and config.get('month')==self._month and
                set(self._modes)-{'terrestre'}<=set(config.get('modes',[])) and
                (config.get('start') or self.range[0])==self.range[0] and
                (config.get('end') or self.range[1])==self.range[1] and
                not config.get('manifestIds') and not config.get('limit') and
                config.get('courier','todos')=='todos')

    @Slot()
    def start(self):
        if self.active:return
        try:
            self.range=month_range(self._year,self._month)
            chosen=[dict(i) for i in self._items if i['selected']]
            if not chosen:raise ValueError('Marca al menos un proceso.')
            if any(i['flow'] for i in chosen) and not self._modes:raise ValueError('Elige una modalidad para Manifiestos y BLs.')
        except ValueError as exc:self._message=str(exc);self.changed.emit();return
        self.generation+=1
        self.tasks={i['id']:{**i,'stage':'starting','label':'Preparando','generation':self.generation,'owned':False} for i in chosen}
        self._message=f'Inicio de {self._year}-{self._month:02d}. Los procesos ocupados conservan su ejecución.'
        self.timer.start();self.changed.emit()
        for task in list(self.tasks.values()):
            bridge=self.bridge(task)
            if not bridge or not bridge.enabled:self.mark(task,'error','Módulo no disponible');continue
            if self.occupied(task):self.mark(task,'skipped','Ocupado; se mantiene su ejecución');continue
            if task['module']=='bls':
                if not set(self._modes)&{'maritimo','aereo'}:self.mark(task,'blocked','BLs requiere Marítimo o Aéreo; Terrestre solo aplica a Manifiestos')
                continue
            if task['flow']:
                modes = [m for m in self._modes if task['flow'] != 'contenedores' or m == 'maritimo']
                if not modes:
                    self.mark(task,'blocked','Contenedores solo consulta Marítimo; marca esa modalidad.')
                    continue
                config={**self.channel(task).snapshot.get('config',{}),'year':self._year,'month':self._month,
                        'workers':task['workers'],'modes':modes,'start':self.range[0],'end':self.range[1],
                        'name':'','manifestIds':'','limit':0,'courier':'todos'}
                task['owned']=True
                if self.channel(task).send('run',{'config':config}):self.mark(task,'running','Consultando')
                else:self.mark(task,'error','No se pudo iniciar el procedimiento')
            else:
                if not bridge.ready:self.mark(task,'error','El módulo todavía no está listo');continue
                config={'cant_hilos':task['workers'],'daily_mode':True,
                        'daily_start_date':self.range[0],'daily_end_date':self.range[1]}
                if not bridge.config.get('output_base_path'):config['output_base_path']=str(Path(bridge.storageRoot)/'resultados')
                task.update(stage='configuring',label='Preparando el mes',configured=False,
                            deadline=time.monotonic()+60,owned=True,config=config)
                task['request']=bridge.request('configure',{'config':config})
                if not task['request']:self.mark(task,'error','No se pudo guardar la configuración')
        bls=self.tasks.get('bls')
        if bls and bls['stage']=='starting':
            dependency=self.tasks.get('conocimientos')
            if dependency and dependency['stage'] in ACTIVE:self.mark(bls,'dependency','Esperando Conocimientos de este mes')
            elif dependency and dependency['stage']=='skipped' and self.matching_knowledge(dependency):
                dependency['watching']=True
                self.mark(bls,'dependency','Esperando Conocimientos que ya está en curso')
            elif dependency and dependency['stage']=='error':self.mark(bls,'blocked','No se iniciaron Conocimientos')
            else:self.catalog(bls)
        self.changed.emit()

    def catalog(self,task):
        bridge=self.bridge(task)
        if getattr(bridge,'_closing',False):self.mark(task,'stopped','La app está cerrando; BLs no se inició');return
        if self.occupied(task):self.mark(task,'skipped','BLs está ocupado; no se cambió su base');return
        task.update(stage='catalog',label='Verificando Conocimientos',deadline=time.monotonic()+60,catalog=None)
        bridge.refreshKnowledge();self.changed.emit()

    def launch_bls(self,task,catalog):
        if getattr(self.bridge(task),'_closing',False):self.mark(task,'stopped','La app está cerrando; BLs no se inició');return
        modes=[m for m in self._modes if m!='terrestre']
        keys=[f'{self._year}-{self._month:02d}|{mode}' for mode in modes]
        available={p['key'] for p in catalog.get('periods',[]) if p.get('fullMonth')}
        if not keys or any(key not in available for key in keys):
            self.mark(task,'blocked','Falta Conocimientos completo para el mes/modalidad; selecciona Conocimientos y vuelve a iniciar.');return
        bridge=self.bridge(task)
        config={**bridge.config,'inputMode':'knowledge','knowledgePeriods':keys,'workers':task['workers'],'name':''}
        task.update(stage='running',label='Preparando base y consultando',owned=True)
        if not bridge.command('run',{'config':config}):self.mark(task,'error','BLs no aceptó el inicio; conserva su progreso')
        self.changed.emit()

    def finish(self,task):
        outcome=task.pop('terminal',('error','No se recibió una finalización verificable'))
        self.mark(task,*outcome)
        bls=self.tasks.get('bls')
        if task['id']=='conocimientos' and bls and bls['stage']=='dependency':
            if outcome[0]=='completed':self.catalog(bls)
            else:self.mark(bls,'blocked','Conocimientos quedó detenido o con pendientes; BLs no se inició')

    def receive_event(self,module,event):
        flow=event.get('flow','')
        task=self.tasks.get(flow or module)
        kind,command=event.get('event'),event.get('command')
        bls=self.tasks.get('bls')
        if kind=='stopping':
            if task:task['watching']=False
            if task and task['stage'] in ACTIVE:self.mark(task,'stopped','Detenido desde el panel; avance conservado')
            if module=='bls' and bls and bls['stage'] in ACTIVE:self.mark(bls,'stopped','BLs detenido; no se iniciarán consultas pendientes')
            if flow=='conocimientos' and bls and bls['stage']=='dependency':self.mark(bls,'blocked','Conocimientos detenido; BLs no se inició')
            return
        if task and task.get('watching') and bls and bls['stage']=='dependency' and command=='run':
            if kind=='result':
                summary=event.get('snapshot',{}).get('summary',{})
                task['watch_ok']=not any(summary.get(k) for k in ('pending','invalid','running','excluded'))
            elif kind=='error':
                task['watching']=False
                self.mark(bls,'blocked','Conocimientos falló; BLs no se inició')
            elif kind=='idle':
                task['watching']=False
                if task.get('watch_ok'):self.catalog(bls)
                else:self.mark(bls,'blocked','Conocimientos quedó con pendientes; BLs no se inició')
            return
        if module=='bls' and flow=='bls_source' and bls:
            if bls['stage']=='catalog':
                if kind=='result':bls['catalog']=event.get('snapshot',{}).get('knowledgeCatalog',{})
                elif kind=='error':self.mark(bls,'error',event.get('message','No se pudo verificar la base'))
                elif kind=='idle' and bls.get('catalog') is not None:
                    generation=self.generation
                    def dispatch():
                        if generation!=self.generation or bls['stage']!='catalog':return
                        # Dejar terminar el worker y cualquier refresco ya programado.
                        if self.bridge(bls).channels['bls_source'].busy:return
                        self.launch_bls(bls,bls['catalog'])
                    QTimer.singleShot(0,dispatch)
            elif bls['stage']=='running' and kind=='error':self.mark(bls,'error',event.get('message','No se pudo preparar BLs'))
            return
        if not task or task['stage'] not in ACTIVE:return
        if not task['flow']:
            if event.get('requestId')!=task.get('request'):return
            if task['stage']=='configuring':
                if kind=='error':self.mark(task,'error',event.get('message','No se pudo configurar'));return
                if kind=='result':task['configured']=True
                if kind=='idle' and task['configured']:
                    generation=self.generation
                    def run():
                        bridge=self.bridge(task)
                        if generation!=self.generation or task['stage']!='configuring':return
                        if bridge.busy or getattr(bridge,'_closing',False):self.mark(task,'error','El módulo está ocupado o cerrando');return
                        if any(bridge.config.get(key)!=task['config'][key] for key in ('daily_start_date','daily_end_date','daily_mode','cant_hilos')):
                            self.mark(task,'error','La configuración cambió; no se inició otro mes');return
                        task.update(stage='running',label='Descargando y procesando el mes')
                        task['request']=bridge.request('daily_run', {'bounded': True})
                        if not task['request']:self.mark(task,'error','No se pudo iniciar el mes')
                        self.changed.emit()
                    QTimer.singleShot(0,run)
                return
            if kind=='result':task['terminal']=('completed','Completado') if event.get('runStatus')=='completed' else ('stopped','Detenido; avance conservado')
        else:
            if command not in ('run','knowledge_empty'):return
            if kind=='result':
                summary=event.get('snapshot',{}).get('summary',{})
                task['terminal']=('pending','Terminó con pendientes o exclusiones') if any(summary.get(k) for k in ('pending','invalid','running','excluded')) else ('completed','Completado')
        if kind=='error':task['terminal']=('error',event.get('message','Error; avance conservado'))
        if kind in ('result','error'):self.mark(task,'finishing','Finalizando')
        if kind=='idle':self.finish(task)

    @Slot()
    def cancel(self):
        self.generation+=1
        for task in self.tasks.values():
            task['watching']=False
            if task['stage'] not in ACTIVE:continue
            task.update(stage='stopped',label='Detenido; avance conservado')
            if task['owned']:
                if task['module']=='bls':self.bridge(task).stop()
                elif task['flow']:self.channel(task).send('stop')
                else:self.bridge(task).stopQueries()
        self.timer.stop();self._message='Inicio conjunto detenido. Los avances se conservan.';self.changed.emit()

    @Slot()
    def expire(self):
        for task in self.tasks.values():
            if task['stage'] in ('configuring','catalog') and time.monotonic()>task['deadline']:
                self.mark(task,'error','No llegó la confirmación de preparación; no se inició la descarga')
