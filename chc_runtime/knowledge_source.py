"""Conocimientos terminados → base BLs. Se ejecuta solo en su proceso proveedor."""
import calendar
from contextlib import closing
from datetime import date
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

MONTHS = ('Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto',
          'Septiembre','Octubre','Noviembre','Diciembre')
MODES = {'maritimo':'Marítimo','aereo':'Aéreo'}


class Unavailable(ValueError):
    pass


def readonly(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=3)
    connection.execute('PRAGMA query_only=ON')
    connection.execute('BEGIN')
    return connection


def completed_source(db):
    """El nombre del archivo ni la mera presencia de filas acreditan una descarga."""
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'metadata','selection','jobs','runs','manifests','rows','partial_pages'} <= tables:
        raise Unavailable('Sin control completo de Conocimientos')
    scope = json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0])
    if scope.get('flow','conocimientos') != 'conocimientos' or scope.get('mode') not in MODES:
        raise Unavailable('Otro procedimiento o modalidad')
    if scope.get('courier') not in (None,'N') or scope.get('ids') or scope.get('limit'):
        raise Unavailable('Selección limitada de conocimientos')
    if not db.execute('SELECT 1 FROM selection WHERE id=1').fetchone():
        raise Unavailable('Selección sin confirmar')
    if db.execute("SELECT 1 FROM jobs WHERE state!='Guardado' LIMIT 1").fetchone():
        raise Unavailable('Quedan trabajos pendientes o activos')
    if db.execute('SELECT 1 FROM partial_pages LIMIT 1').fetchone():
        raise Unavailable('Quedan páginas parciales')
    latest = db.execute('SELECT state,finished FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
    if not latest or not latest[1] or latest[0]!='Finalizada':
        raise Unavailable('La descarga no ha finalizado')
    if db.execute('SELECT 1 FROM jobs j LEFT JOIN manifests m ON m.id=j.id WHERE m.id IS NULL LIMIT 1').fetchone():
        raise Unavailable('Falta confirmación del resultado')
    year,month = int(scope['year']),int(scope['month'])
    first,last = date(year,month,1),date(year,month,calendar.monthrange(year,month)[1])
    start,end = date.fromisoformat(scope.get('desde') or first.isoformat()),date.fromisoformat(scope.get('hasta') or last.isoformat())
    if start>end or start<first or end>last or start>date.today():
        raise Unavailable('Intervalo inválido o futuro')
    return {'period':f'{year:04d}-{month:02d}','mode':scope['mode'], 'start':start.isoformat(),
            'end':min(end,date.today()).isoformat(), 'rows':db.execute('SELECT count(*) FROM rows').fetchone()[0],
            'manifests':db.execute('SELECT count(*) FROM jobs').fetchone()[0]}


def merge_ranges(ranges):
    result = []
    from datetime import timedelta
    for start,end in sorted(set((date.fromisoformat(a),date.fromisoformat(b)) for a,b in ranges)):
        if result and start<=result[-1][1]+timedelta(days=1):
            result[-1]=(result[-1][0],max(result[-1][1],end))
        else:
            result.append((start,end))
    return result


class KnowledgeSource:
    def __init__(self, root, stop, emit):
        self.root,self.stop,self.emit = Path(root).resolve(),stop,emit

    def check_stop(self):
        if self.stop.is_set():
            import asyncio
            raise asyncio.CancelledError()

    def catalog(self):
        groups, skipped = {},0
        roots = [self.root/'data/jobs/conocimientos',self.root/'datos_app/SQLite/conocimientos']
        paths = sorted({p.resolve() for root in roots if root.exists() for p in root.rglob('*.sqlite3')})
        for path in paths:
            self.check_stop()
            try:
                with closing(readonly(path)) as db:
                    info = completed_source(db)
            except Unavailable:
                skipped+=1
                continue
            except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,IndexError) as exc:
                logging.warning('No se ofrece %s como base BLs: %s',path,exc)
                skipped+=1
                continue
            key=info['period']+'|'+info['mode']
            entry=groups.setdefault(key,{'key':key,'period':info['period'],'mode':info['mode'],'sources':[],'ranges':[]})
            entry['sources'].append(str(path))
            entry['ranges'].append((info['start'],info['end']))
        result=[]
        for entry in groups.values():
            year,month=map(int,entry['period'].split('-'))
            ranges=merge_ranges(entry['ranges'])
            last=date(year,month,calendar.monthrange(year,month)[1])
            full = ranges==[(date(year,month,1),last)] and last<date.today()
            coverage='Mes completo' if full else 'Días '+', '.join(
                a.strftime('%d')+(('–'+b.strftime('%d')) if a!=b else '') for a,b in ranges)
            entry.update(label=MONTHS[month-1]+' '+str(year)+' · '+MODES[entry['mode']],
                         coverage=coverage,fullMonth=full,ranges=[(a.isoformat(),b.isoformat()) for a,b in ranges])
            result.append(entry)
        result.sort(key=lambda e:(e['period'],e['mode']),reverse=True)
        return {'periods':result,'skipped':skipped,'message':'Solo descargas terminadas, sin pendientes.' if result else
                'No hay descargas completas de Conocimientos disponibles para BLs.'}

    def build(self, keys):
        from bls_base import Source,build_base,OUTPUT_COLUMNS
        from chc_runtime.manifest_service import write_json
        keys=sorted(set(keys))
        if not keys:
            raise ValueError('Seleccione meses y modalidades de Conocimientos.')
        catalog={entry['key']:entry for entry in self.catalog()['periods']}
        if any(key not in catalog for key in keys):
            raise ValueError('La selección ya no está disponible como descarga completa. Actualice los meses.')
        folder=self.root/'data/bls_source'
        temporary_root=folder/'tmp'
        temporary_root.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(dir=temporary_root)).resolve()
        if not stage.is_relative_to(temporary_root.resolve()):
            raise ValueError('Carpeta de preparación fuera del almacenamiento propio')
        try:
            sources=[]
            signature=hashlib.sha256(json.dumps({'version':1,'keys':keys},sort_keys=True).encode())
            paths=sorted({path for key in keys for path in catalog[key]['sources']})
            for index,path in enumerate(paths):
                self.check_stop()
                destination=stage/str(index)/Path(path).name
                destination.parent.mkdir()
                with closing(readonly(path)) as incoming:
                    info=completed_source(incoming)
                    with closing(sqlite3.connect(destination)) as target:
                        incoming.backup(target,pages=256,progress=lambda *args:self.check_stop())
                with destination.open('rb') as stream:
                    while block:=stream.read(1024*1024):
                        self.check_stop()
                        signature.update(block)
                sources.append(Source(destination,'SQLite',period=info['period'],mode=info['mode'],rows=info['rows']))
            fingerprint=signature.hexdigest()
            output=folder/'bases'/(fingerprint+'.sqlite3')
            metadata=output.with_suffix('.json')
            if output.is_file() and metadata.is_file():
                record=json.loads(metadata.read_text(encoding='utf-8'))
                if hashlib.sha256(output.read_bytes()).hexdigest()==record['sha256']:
                    return {**record,'reused':True}
            try:
                stats=build_base(sources,output,periods=[tuple(k.split('|')) for k in keys],
                    audit_dir=folder/'auditoria',stop=self.stop,
                    progress=lambda event:self.emit('activity',message='Preparando base de BLs desde Conocimientos…'))
            except ValueError as exc:
                audit=getattr(exc,'audit',None)
                if not audit:
                    raise
                with closing(readonly(audit)) as db:
                    stats=json.loads(db.execute("SELECT value FROM metadata WHERE key='summary'").fetchone()[0])
                # Cero Courier N es legítimo; no confundirlo con inválidos o conflictos.
                if stats['invalid'] or stats['conflicts'] or stats['exported'] or stats['read']!=stats['courier_excluded']:
                    raise
                output.parent.mkdir(parents=True,exist_ok=True)
                staging=stage/'empty.sqlite3'
                with closing(sqlite3.connect(staging)) as db:
                    db.execute('CREATE TABLE BLS ('+','.join('"'+c+'" TEXT NOT NULL' for c in OUTPUT_COLUMNS)+')')
                    db.commit()
                self.check_stop()
                os.replace(staging,output)
                stats['output']=str(output)
                stats['tables']=1
            if stats['invalid'] or stats['conflicts']:
                raise ValueError('La base contiene conocimientos inválidos o BL contradictorios. No se iniciaron consultas. Auditoría: '+stats['audit'])
            record={'output':str(output),'periods':keys,'empty':stats['exported']==0,'stats':stats,
                    'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'fingerprint':fingerprint,'reused':False,
                    'sources':paths,'coverage':[{k:catalog[key][k] for k in ('key','ranges','fullMonth')} for key in keys]}
            with closing(sqlite3.connect(stats['audit'])) as audit:
                audit.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',
                              ('knowledge_sources',json.dumps(paths,ensure_ascii=False)))
                if record['empty']:
                    audit.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('status','completed_empty'))
                    audit.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('summary',json.dumps(stats,ensure_ascii=False)))
                    audit.execute("DELETE FROM metadata WHERE key='error'")
                audit.commit()
            write_json(metadata,record)
            return record
        finally:
            # El único borrado recursivo se restringe al temporal creado aquí.
            if stage.is_relative_to(temporary_root.resolve()):
                shutil.rmtree(stage)
