"""Contrato único para CSV públicos locales y rutas de SharePoint."""
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
MONTHS=('ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE')
BOTS={'detalles':'DETALLES','duas_transito':'DUAS_TRANSITO','talon':'TALON','xmovimientos':'XMOVIMIENTOS','bls':'BLS'}
FLOWS={'tabla':'LISTADO','conocimientos':'CONOCIMIENTOS','duas':'DUAS','movimientos':'MOVIMIENTOS','contenedores':'CONTENEDORES'}


def uppercase(value):
    plain=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().upper()
    return re.sub(r'[^A-Z0-9]+','_',plain).strip('_') or 'SIN_NOMBRE'


def period(*values):
    for value in values:
        value=str(value).upper()
        match=re.search(r'(20\d{2})[-_](0[1-9]|1[0-2])(?:\D|$)',value)
        if match:return match[1]+'-'+match[2]
        for month,name in enumerate(MONTHS,1):
            match=re.search(name+r'[ _-]*(20\d{2}|\d{2})(?!\d)',value)
            if match:return f'{int(match[1]) if len(match[1])==4 else 2000+int(match[1]):04d}-{month:02d}'
    return ''


def month_label(key):
    if not key:return 'SIN_PERIODO'
    year,month=map(int,key.split('-'))
    return MONTHS[month-1]+'_'+str(year)


def settings_path(storage=None):
    storage=Path(storage).resolve() if storage else None
    if storage and storage != ROOT/'bots'/storage.name:
        return storage/'data/public_outputs.json'
    return ROOT/'runtime/workbench/exports.json'


def local_root(storage=None,fallback='',settings=None):
    path=Path(settings) if settings else settings_path(storage)
    if path.exists():
        value=json.loads(path.read_text(encoding='utf-8')).get('localRoot')
        if value:return Path(value).resolve()
    if storage and settings_path(storage)!=settings_path():
        return Path(fallback or Path(storage)/'RESULTADOS').resolve()
    return ROOT/'RESULTADOS'


def set_local_root(value,storage=None,settings=None):
    path=Path(value).expanduser().resolve()
    path.mkdir(parents=True,exist_ok=True)
    config=Path(settings) if settings else settings_path(storage)
    config.parent.mkdir(parents=True,exist_ok=True)
    temp=config.with_suffix('.tmp')
    temp.write_text(json.dumps({'localRoot':str(path)},ensure_ascii=False),encoding='utf-8')
    os.replace(temp,config)
    return path


def specification(target,key='',mode='',qualifier=''):
    if target.startswith('manifiestos:'):
        flow=FLOWS[target.split(':',1)[1]]
        folders=['MANIFIESTOS',flow]
        prefix='MANIFIESTOS_'+flow
    else:
        prefix=BOTS[target];folders=[prefix]
    label=month_label(key)
    folders.append(label)
    parts=[prefix]
    if mode:parts.append(uppercase(mode))
    parts.append(label)
    if qualifier:parts.append(uppercase(qualifier))
    return {'target':target,'period':key,'mode':mode,'relativeFolders':folders,'filename':'_'.join(parts)+'.CSV'}


def dua_spec(target,record):
    key=period(record.get('source_path',''),record['name'])
    canonical=bool(key and re.fullmatch(r'(?:'+ '|'.join(MONTHS)+r')[ _-]*(?:20\d{2}|\d{2})',record['name'].upper()))
    return specification(target,key,qualifier='' if canonical or str(record.get('source_path','')).startswith('daily://') else 'LOTE_'+uppercase(record['name']))


def manifest_spec(flow,record,mode):
    scope=record['spec'];key=f"{scope['year']:04d}-{scope['month']:02d}"
    # El sufijo conserva selecciones parciales/courier/IDs sin mezclar sus datos.
    qualifier=''
    import calendar
    first=key+'-01';last=key+f"-{calendar.monthrange(scope['year'],scope['month'])[1]:02d}"
    if scope.get('start',first)!=first or scope.get('end',last)!=last:
        qualifier='DEL_'+scope.get('start',first)+'_AL_'+scope.get('end',last)
    if scope.get('courier') not in (None,'todos'):qualifier+='_COURIER_'+scope['courier']
    if scope.get('ids') or scope.get('limit'):
        qualifier+='_SELECCION_'+hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()[:8].upper()
    return specification('manifiestos:'+flow,key,mode,qualifier)


def bls_spec(record,key,mode):
    c=record.get('config',{})
    qualifier='' if c.get('inputMode')=='knowledge' and not re.search(r'\(\d+\)$',record.get('name','')) else 'LOTE_'+uppercase(record.get('name','BLS'))
    return specification('bls',key,mode,qualifier)


def registry_path(storage=None,settings=None):
    return (Path(settings) if settings else settings_path(storage)).with_name('publications.sqlite3')


def open_registry(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS exports(path TEXT PRIMARY KEY,owner TEXT NOT NULL,target TEXT NOT NULL,period TEXT NOT NULL,spec TEXT NOT NULL,final INTEGER NOT NULL)')
    return db


def publish(source,base,spec,owner,registry,final=True):
    source=Path(source)
    if not source.is_file():return None
    destination=Path(base).joinpath(*spec['relativeFolders'],spec['filename'])
    db=open_registry(registry)
    temp=None
    try:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT owner FROM exports WHERE path=?',(str(destination),)).fetchone()
        if (old and old['owner']!=owner) or (destination.exists() and not old):
            raise ValueError('Otro lote o archivo utiliza este nombre de resultados. Se conservó el archivo anterior.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(dir=destination.parent,suffix='.tmp');os.close(fd)
        shutil.copyfile(source,temp);os.replace(temp,destination)
        db.execute('INSERT OR REPLACE INTO exports VALUES(?,?,?,?,?,?)',(str(destination),owner,spec['target'],spec['period'],json.dumps(spec),int(final)))
        db.commit()
        return {'path':str(destination),'name':month_label(spec['period']),'owner':owner,**spec,'final':final}
    finally:
        db.close()
        if temp and os.path.exists(temp):os.unlink(temp)


def bls_exports(source,record):
    """Dividir por mes/modo real conservando columnas, filas y ceros originales."""
    source=Path(source)
    if not source.is_file():return []
    outputs={};streams=[]
    try:
        with source.open(encoding='utf-8-sig',newline='') as incoming:
            reader=csv.reader(incoming);headers=next(reader,[])
            try:index=headers.index('manifiesto')
            except ValueError:raise ValueError('El CSV de BLs no contiene la identidad del manifiesto.')
            for row in reader:
                parts=row[index].split('-')
                day=datetime.strptime(parts[-1],'%d/%m/%y')
                mode={'1':'MARITIMO','4':'AEREO','7':'TERRESTRE'}[parts[0]]
                key=f'{day.year:04d}-{day.month:02d}'
                group=(key,mode)
                if group not in outputs:
                    spec=bls_spec(record,key,mode)
                    fd,path=tempfile.mkstemp(dir=source.parent,suffix='.tmp')
                    stream=os.fdopen(fd,'w',encoding='utf-8-sig',newline='');streams.append(stream)
                    writer=csv.writer(stream);writer.writerow(headers)
                    outputs[group]=(Path(path),spec,writer)
                outputs[group][2].writerow(row)
        for stream in streams:stream.close()
        return [(path,spec) for path,spec,_ in outputs.values()]
    except Exception:
        for stream in streams:stream.close()
        for path,_,_ in outputs.values():path.unlink(missing_ok=True)
        raise
