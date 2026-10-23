"""Observación de etapas y señales de proceso; no decide plazos ni guarda resultados."""
import asyncio
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
import inspect
import logging
import threading
import time

CURRENT = ContextVar('workbench_activity',default=None)
SUBJECT = ContextVar('workbench_activity_subject',default='')
PATH = ContextVar('workbench_activity_path',default=())


class EventLog(logging.Handler):
    def __init__(self, emit):
        super().__init__();self.send=emit

    def emit(self, record):
        if getattr(record,'technical_only',False):return
        try:
            self.send('log',message=record.getMessage(),level=getattr(record,'tag',record.levelname),
                      time=time.strftime('%H:%M:%S',time.localtime(record.created)))
        except (OSError,ValueError):pass


class ActivityReporter:
    def __init__(self, emit, interval=1, repeat=15):
        self.emit=emit;self.interval=interval;self.repeat=repeat
        self.lock=threading.RLock();self.stacks={};self.generation=0;self.running=False

    def send(self, event, **data):
        try:self.emit(event,**data)
        except Exception:pass  # La observación nunca cambia el resultado del motor.

    def log(self,message,level='INFO'):
        self.send('log',message=message,level=level,time=time.strftime('%H:%M:%S'))

    @contextmanager
    def session(self, label):
        if CURRENT.get() is self:
            with self.stage(label):yield self
            return
        with self.lock:
            self.generation+=1;generation=self.generation;self.running=True;self.stacks.clear()
        stop=threading.Event();context=CURRENT.set(self)
        def pulse():
            while not stop.wait(self.interval):self.publish(generation)
        thread=threading.Thread(target=pulse,name='workbench-activity',daemon=True);thread.start()
        try:
            with self.stage(label):
                self.publish(generation)
                yield self
        finally:
            stop.set();thread.join(timeout=1)
            with self.lock:self.running=False;self.stacks.clear()
            self.send('activity_state',running=False,operations=[])
            CURRENT.reset(context)

    @contextmanager
    def stage(self, label, subject=''):
        parents=PATH.get()
        if not self.running or any(not parent['active'] for parent in parents):
            yield lambda message:None
            return
        try:task=asyncio.current_task()
        except RuntimeError:task=None
        key=str(threading.get_ident())+':'+str(id(task) if task else 0)
        now=time.monotonic();subject=subject or SUBJECT.get()
        marker={'active':True};lineage=parents+(marker,)
        row=dict(key=key,label=label,subject=subject,started=now,announced=now,generation=self.generation,path=lineage)
        context=SUBJECT.set(subject)
        path_context=PATH.set(lineage)
        with self.lock:self.stacks.setdefault(key,[]).append(row)
        self.log(label+(' · '+subject if subject else ''))
        def update(message):
            with self.lock:
                if not self.running or row['generation']!=self.generation or any(not p['active'] for p in lineage):return
                changed=message!=row['label'];row['label']=message;row['announced']=time.monotonic()
            if changed:self.log(message+(' · '+subject if subject else ''))
        try:
            yield update
        except BaseException as error:
            if self.running and row['generation']==self.generation and all(p['active'] for p in lineage):
                self.log(label+' · '+(subject+' · ' if subject else '')+
                         ('Interrumpido' if isinstance(error,asyncio.CancelledError) else str(error) or type(error).__name__),'WARNING')
            raise
        finally:
            elapsed=time.monotonic()-now
            with self.lock:
                was_active=all(p['active'] for p in lineage)
                marker['active']=False
                for stack_key,stack in list(self.stacks.items()):
                    stack[:]=[item for item in stack if all(p['active'] for p in item['path'])]
                    if not stack:self.stacks.pop(stack_key,None)
            if was_active and self.running and row['generation']==self.generation and elapsed>=1:
                self.log('Fin de etapa: '+label+(' · '+subject if subject else '')+f' · {elapsed:.1f} s')
            SUBJECT.reset(context)
            PATH.reset(path_context)

    def publish(self,generation):
        now=time.monotonic();waiting=[]
        with self.lock:
            if not self.running or generation!=self.generation:return
            rows=[]
            for stack in self.stacks.values():
                if not stack:continue
                row=stack[-1];elapsed=max(0,now-row['started'])
                rows.append(dict(key=row['key'],label=row['label'],subject=row['subject'],elapsed=round(elapsed,1)))
                if now-row['announced']>=self.repeat:
                    row['announced']=now
                    waiting.append(row['label']+(' · '+row['subject'] if row['subject'] else '')+f' · {int(elapsed)} s transcurridos')
        self.send('activity_state',running=True,operations=rows)
        for message in waiting:self.log('Sigue en: '+message)


def stage(label, subject=''):
    reporter=CURRENT.get()
    return reporter.stage(label,subject) if reporter else nullcontext(lambda message:None)


def observed(label, subject=None):
    def decorate(function):
        if getattr(function,'_workbench_observed',False):return function
        def scope(args,kwargs):
            value=subject(*args,**kwargs) if subject else ''
            return stage(label,str(value or ''))
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def wrapped(*args,**kwargs):
                if CURRENT.get() is None:return await function(*args,**kwargs)
                with scope(args,kwargs):return await function(*args,**kwargs)
        else:
            @wraps(function)
            def wrapped(*args,**kwargs):
                if CURRENT.get() is None:return function(*args,**kwargs)
                with scope(args,kwargs):return function(*args,**kwargs)
        wrapped._workbench_observed=True
        return wrapped
    return decorate


COMMANDS={'run':'Ejecutando consultas','retry_empty':'Reconsultando vacíos','daily_run':'Diario automático',
          'retry_month':'Reintentando pendientes del mes','retry_day':'Reintentando pendientes del día',
          'export':'Generando CSV','export_all':'Generando todos los CSV guardados','refresh':'Leyendo bases y progreso','initialize':'Cargando bases de datos',
          'knowledge_build':'Preparando base BLs desde Conocimientos','knowledge_catalog':'Buscando Conocimientos terminados',
          'base_build':'Generando base BLs','base_load':'Leyendo fuentes de Conocimientos','import':'Importando base',
          'view':'Leyendo lista de consultas','detail':'Leyendo detalle guardado','daily_calendar':'Leyendo calendario',
          'configure':'Guardando configuración','select':'Abriendo tabla seleccionada',
          'review':'Preparando pendientes y exclusiones','knowledge_empty':'Preparando lote BLs sin registros'}
