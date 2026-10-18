"""Acumular una selección de Conocimientos sin cambiar firmas ni trabajos confirmados."""
from contextlib import closing
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid


def family(config, scope):
    if config.get('inputMode') != 'knowledge' or not config.get('knowledgePeriods'):
        return None
    periods = sorted(set(config['knowledgePeriods']))
    if any(not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])\|(maritimo|aereo)', p) for p in periods):
        raise ValueError('Mes o modalidad de Conocimientos inválidos.')
    return {'version':1,'periods':periods,'scope':query_scope(scope)}


def query_scope(scope):
    return {k:v for k,v in scope.items() if k != 'revision'}


def find_record(history, selected_family, active=''):
    if selected_family is None:
        return None
    candidates=[]
    for record in history:
        previous=record.get('knowledgeFamily')
        if previous is None:
            previous=family(record.get('config',{}),selected_family['scope'])
        if previous==selected_family:
            candidates.append(record)
    return next((r for r in candidates if r['id']==active),
                max(candidates,key=lambda r:(r.get('summary',{}).get('succeeded',0),
                    r.get('summary',{}).get('rows',0),r.get('summary',{}).get('total',0))) if candidates else None)


def anchor(root, record, signature, scope):
    from .batch_deletion import checked_work
    work=checked_work(Path(root).resolve(),'bls',record)
    paths=list(work.glob('**/SQLite/bls.sqlite3'))
    if len(paths)>1:
        raise ValueError('El lote contiene varias bases; se conserva para revisión.')
    if paths:
        path=paths[0].resolve()
        if not path.is_relative_to(work):raise ValueError('Base BLs fuera del lote seleccionado.')
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            metadata=dict(db.execute('SELECT key,value FROM metadata'))
        signature=metadata['signature'];stored_scope=json.loads(metadata['scope'])
        if query_scope(stored_scope)!=query_scope(scope):
            raise ValueError('El lote utiliza otra configuración de búsqueda.')
        if record.get('knowledgeAnchor',signature)!=signature:
            raise ValueError('La firma del lote cambió; progreso conservado.')
        scope=stored_scope
    return record.get('knowledgeAnchor',signature),record.get('knowledgeScope',scope)


def rows_digest(records, scope):
    from core.inputs import input_job
    digest=hashlib.sha256(json.dumps(query_scope(scope),sort_keys=True).encode())
    for record in records:
        digest.update(json.dumps(input_job(record,0)['record'],sort_keys=True,ensure_ascii=False).encode())
        digest.update(b'\n')
    return digest.hexdigest()


def verify_input(db, records, scope):
    metadata=dict(db.execute('SELECT key,value FROM metadata'))
    digest=rows_digest(records,scope)
    expected=metadata.get('workbench_bls_input_signature')
    if expected is None:
        expected=metadata['signature']
        if scope.get('revision'):
            digest=hashlib.sha256((digest+scope['revision']).encode()).hexdigest()
    if digest!=expected:
        raise ValueError('La entrada persistida no coincide con la firma del lote; progreso conservado.')


def install_engine_scope():
    from core import engine
    if getattr(engine.batch_scope,'_workbench_accumulation',False):return
    original=engine.batch_scope
    @wraps(original)
    def batch_scope(df, config):
        signature,scope=original(df,config)
        request=config.get('workbench_bls_accumulation')
        if request:
            if query_scope(scope)!=query_scope(request['scope']):
                raise ValueError('La configuración no coincide con el lote acumulado.')
            if request.get('input_signature') and signature!=request['input_signature']:
                raise ValueError('La base de Conocimientos cambió durante la preparación.')
            return request['signature'],scope
        return signature,scope
    batch_scope._workbench_accumulation=True
    engine.batch_scope=batch_scope


def append(store, df, request):
    from core.inputs import input_job
    from .bls_empty_retry import scope_pending_queue
    db=store.db
    selected_family=request['family']
    metadata=dict(db.execute('SELECT key,value FROM metadata'))
    if metadata.get('workbench_bls_family') and json.loads(metadata['workbench_bls_family'])!=selected_family:
        raise ValueError('La base pertenece a otro mes o modalidad de Conocimientos.')
    old=[json.loads(r[0]) for r in db.execute('SELECT payload FROM inputs ORDER BY ordinal')]
    if metadata.get('selection_ready'):verify_input(db,old,request['scope'])
    existing={key:json.loads(payload) for key,payload in db.execute('SELECT id,payload FROM jobs')}
    identities={}
    def identity(record):
        sequence=record.get('Secuencia Tica','')
        return record['IDManifiesto'],str(int(sequence)) if sequence.isdigit() else sequence
    def check_member(record):
        parts=record['IDManifiesto'].split('-')
        period=datetime.strptime(parts[-1],'%d/%m/%y').strftime('%Y-%m')
        mode={'1':'maritimo','4':'aereo'}.get(parts[0],'')
        if period+'|'+mode not in selected_family['periods'] or record.get('Mes')!=period:
            raise ValueError('Un BL pertenece a otro mes o modalidad; no se amplió el lote.')
    for record in existing.values():
        check_member(record)
        key=identity(record);bl=record['BL original']
        if key in identities and identities[key]!=bl:
            raise ValueError('El lote existente contiene BLs contradictorios; se conserva para revisión.')
        identities[key]=bl
    incoming={}
    for row in df.to_dict('records'):
        job=input_job(row,0)
        if job['error']:raise ValueError('Conocimiento inválido: '+job['error'])
        record=job['record'];check_member(record)
        key=identity(record);bl=record['BL original']
        if key in identities and identities[key]!=bl:
            raise ValueError('Conocimientos cambió el BL de un manifiesto/secuencia existente; requiere revisión.')
        identities[key]=bl;incoming[job['key']]=record
    additions={key:record for key,record in incoming.items() if key not in existing}
    if old and 'workbench_bls_family' not in metadata:
        backup=Path(request['backups'])/(uuid.uuid4().hex+'.sqlite3')
        if backup.resolve().is_relative_to(store.path.parents[3]):
            raise ValueError('El respaldo debe quedar fuera del progreso del lote.')
        backup.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(backup)) as target:db.backup(target)
    ordinal=max(db.execute('SELECT coalesce(max(ordinal),0) FROM inputs').fetchone()[0],
                db.execute('SELECT coalesce(max(ordinal),0) FROM jobs').fetchone()[0])
    operation=uuid.uuid4().hex;timestamp=datetime.now(timezone.utc).isoformat()
    with db:
        db.execute('''CREATE TABLE IF NOT EXISTS workbench_bls_queries(
            id TEXT PRIMARY KEY,requested TEXT NOT NULL,finished TEXT,input_signature TEXT NOT NULL,
            expected INTEGER NOT NULL,added INTEGER NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS workbench_bls_query_jobs(
            request TEXT NOT NULL,job TEXT NOT NULL,PRIMARY KEY(request,job))''')
        for key,record in additions.items():
            ordinal+=1;payload=json.dumps(record,ensure_ascii=False)
            db.execute("INSERT INTO jobs(id,ordinal,payload,state,updated) VALUES (?,?,?,'Pendiente',?)",(key,ordinal,payload,timestamp))
            db.execute('INSERT INTO inputs VALUES (?,?,?)',(ordinal,key,payload))
        db.execute('INSERT INTO workbench_bls_queries VALUES (?,?,NULL,?,?,?)',
                   (operation,timestamp,request['input_signature'],len(incoming),len(additions)))
        db.executemany('INSERT INTO workbench_bls_query_jobs VALUES (?,?)',[(operation,key) for key in incoming])
        for key,value in {'selection_ready':'1','workbench_bls_family':json.dumps(selected_family,sort_keys=True),
                          'workbench_bls_input_signature':rows_digest(old+list(additions.values()),request['scope'])}.items():
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(key,value))
    scope_pending_queue(store,'workbench_bls_query_jobs',operation)
    return operation
