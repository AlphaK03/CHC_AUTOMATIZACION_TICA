"""Muestra investigativa: SQLite de solo lectura, sin importar ni iniciar bots.

Los datos generados quedan en runtime/, fuera de Git. El HTML es autónomo.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DUA_COLUMNS = {
    'detalles': ['numero_del_dua','aduana','regimen','fecha_de_registro','tipo_semaforo','tipo_carga',
                 'pago_impuestos','modalidad','tipo_de_dua','estado','medio_de_transporte','aduana_de_ingreso',
                 'aduana_destino','total_bultos','total_peso_bruto','total_peso_neto','total_valor_aduanas','lineas_de_dua'],
    'talon': ['Codigo_Aduana','Año','Numero','Tributo','Descripcion_tributo','Valor_MN','numero_del_dua'],
    'xmovimientos': ['Deposito','Año','Movimiento','Tipo_de_Movimiento','numero_del_dua','Cantidad_de_Bultos_asociada'],
    'duas_transito': ['Item','Partida','Descripción_Comercial','Bultos','Tipo_de_Bulto','numero_del_dua'],
}
KNOWLEDGE_COLUMNS = ['IDManifiesto','Secuencia Tica','BL original','Courier','Categoria','Tipo',
    'RUC del garante','Razón social','Descarga','Desc Descarga','Master','Embarque','Desc Embarque','Estado','Nro de Conocimiento Master']
BL_COLUMNS = ['Contenedor Asociado','Pendientes','Afectaciones','Sob/ Falt','Retenciones','Nro','Peso',
    'Tipo de Bulto','Total de Bulto','Usado','Dep.Dest.','Ubicacion','Aduana','Marcas','Estado',
    'Tipo de operación','Categoria','Cod. Mercancia Peligrosa','manifiesto','bls']
MODULES = ('detalles','talon','xmovimientos','duas_transito')


def dua_key(value):
    match = re.fullmatch(r'(\d{1,3})-(\d{4})-(\d{1,6})', str(value).strip())
    if not match:
        raise ValueError('Identidad DUA inválida')
    aduana, year, number = match.groups()
    if int(aduana) < 1 or int(number) < 1:
        raise ValueError('Identidad DUA inválida')
    return f'{int(aduana):03d}-{year}-{int(number):06d}'


def money_cents(value):
    text = str(value).strip()
    if not re.fullmatch(r'[+-]?\d+(?:\.\d{1,2})?', text):
        return None
    try:
        result = Decimal(text) * 100
        return int(result) if result.is_finite() and abs(result) < 2**53 else None
    except InvalidOperation:
        return None


@contextmanager
def read_database(path):
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    try:
        yield db
    finally:
        db.close()


def relative(path):
    return str(path.resolve().relative_to(ROOT)).replace('\\','/')


def fetch_jobs(module, limit, keys=None):
    records, inventory = [], []
    for path in sorted((ROOT/'bots'/module/'data/queues').glob('daily-*.sqlite3')):
        try:
            with read_database(path) as db:
                available = db.execute("SELECT count(*) FROM jobs WHERE status='succeeded'").fetchone()[0]
                if keys is None:
                    rows = db.execute("SELECT dua,result FROM jobs WHERE status='succeeded' ORDER BY rowid LIMIT ?", (limit,)).fetchall()
                else:
                    rows = []
                    for offset in range(0,len(keys),300):
                        chunk = keys[offset:offset+300]
                        rows.extend(db.execute("SELECT dua,result FROM jobs WHERE status='succeeded' AND dua IN ("+
                            ','.join('?' for _ in chunk)+') ORDER BY rowid',chunk).fetchall())
                for row in rows:
                    dua = dua_key(row['dua'])
                    obj = json.loads(row['result'])
                    if dua_key(obj['numero_del_dua']) != dua:
                        raise ValueError('El resultado no coincide con su DUA')
                    originals = obj.get('rows', [obj])
                    selected = originals[:16]
                    for item in selected:
                        if dua_key(item['numero_del_dua']) != dua:
                            raise ValueError('Línea de otro DUA')
                        record = {key:str(item.get(key,'')) for key in DUA_COLUMNS[module]}
                        record['numero_del_dua'] = dua
                        record['_period'] = path.stem.removeprefix('daily-')
                        record['_source'] = relative(path)
                        record['_completeGroup'] = len(selected)==len(originals)
                        record['_groupRows'] = len(originals)
                        if module=='talon': record['_cents'] = money_cents(record['Valor_MN'])
                        records.append(record)
                inventory.append(dict(module=module,path=relative(path),period=path.stem.removeprefix('daily-'),
                    status='disponible',confirmedDuas=available,sampledDuas=len(rows),
                    columns=DUA_COLUMNS[module],filter="jobs.status = 'succeeded'"))
        except (sqlite3.Error,ValueError,KeyError) as exc:
            inventory.append(dict(module=module,path=relative(path),status='no disponible',reason=str(exc)))
    return records, inventory


def sample_empty(limit):
    observations = []
    for path in sorted((ROOT/'bots/xmovimientos/data/queues').glob('daily-*.sqlite3')):
        try:
            with read_database(path) as db:
                for row in db.execute('''SELECT j.dua,o.checked_at FROM jobs j JOIN empty_observations o ON o.job_id=j.id
                    WHERE j.status='empty' ORDER BY j.rowid LIMIT ?''',(limit,)):
                    observations.append(dict(dua=dua_key(row['dua']),checkedAt=row['checked_at'],period=path.stem.removeprefix('daily-')))
        except sqlite3.Error:
            continue
    return observations


def sample_bls(limit):
    records, jobs, inventory = [], [], []
    for path in sorted((ROOT/'bots/bls/data/jobs').rglob('bls.sqlite3')):
        if 'backups' in path.parts: continue
        try:
            with read_database(path) as db:
                selected = db.execute("SELECT id,payload,result_count FROM jobs WHERE state='Guardado' ORDER BY ordinal LIMIT ?",(limit,)).fetchall()
                for job in selected:
                    original = json.loads(job['payload'])
                    items = db.execute('SELECT position,data FROM results WHERE job=? ORDER BY position LIMIT 12',(job['id'],)).fetchall()
                    source = dict(manifest=original['IDManifiesto'],sequence=str(original['Secuencia Tica']),
                        bl=original['BL original'],period=original.get('Mes',''),source=relative(path),
                        confirmedRows=job['result_count'],sampledRows=len(items))
                    jobs.append(source)
                    for row in items:
                        values = json.loads(row['data'])
                        if len(values)!=len(BL_COLUMNS): raise ValueError('Esquema BL inesperado')
                        record = dict(zip(BL_COLUMNS,values))
                        if record['manifiesto']!=source['manifest'] or record['bls']!=source['bl']:
                            raise ValueError('Identidad de línea BL inconsistente')
                        record.update(_sequence=source['sequence'],_position=row['position'],_period=source['period'],
                                      _completeGroup=len(items)==job['result_count'])
                        records.append(record)
                states = dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state'))
                inventory.append(dict(module='bls',path=relative(path),status='disponible',states=states,
                    sampledJobs=len(selected),columns=BL_COLUMNS,filter="jobs.state='Guardado'; results por job confirmado"))
        except (sqlite3.Error,KeyError,ValueError) as exc:
            inventory.append(dict(module='bls',path=relative(path),status='no disponible',reason=str(exc)))
    return records,jobs,inventory


def sample_knowledge(limit, bl_jobs):
    records, inventory = {}, []
    for path in sorted((ROOT/'bots/manifiestos/data/jobs/conocimientos').rglob('*.sqlite3')):
        if 'backups' in path.parts: continue
        try:
            with read_database(path) as db:
                base = '''SELECT r.manifest,r.sequence,r.data FROM rows r JOIN jobs j ON j.id=r.manifest
                    WHERE j.state='Guardado' '''
                rows = list(db.execute(base+'ORDER BY j.ordinal,r.sequence LIMIT ?',(limit,)))
                for job in bl_jobs:
                    rows.extend(db.execute(base+'AND r.manifest=? AND r.sequence=?', (job['manifest'],job['sequence'])))
                for row in rows:
                    values = json.loads(row['data'])
                    if len(values)!=len(KNOWLEDGE_COLUMNS): raise ValueError('Esquema de Conocimientos inesperado')
                    record = dict(zip(KNOWLEDGE_COLUMNS,values))
                    if record['IDManifiesto']!=row['manifest']: raise ValueError('Identidad de manifiesto inconsistente')
                    # No se necesitan identificaciones ni nombres de personas/empresas en este ejemplo.
                    record.pop('RUC del garante',None);record.pop('Razón social',None)
                    date = datetime.strptime(record['IDManifiesto'].rsplit('-',1)[-1],'%d/%m/%y')
                    record.update(_source=relative(path),_period=date.strftime('%Y-%m'))
                    records[(record['IDManifiesto'],record['Secuencia Tica'])] = record
                states = dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state'))
                inventory.append(dict(module='manifiestos',procedure='conocimientos',path=relative(path),status='disponible',
                    states=states,sampledRows=sum(r['_source']==relative(path) for r in records.values()),columns=KNOWLEDGE_COLUMNS,
                    filter="rows de jobs.state='Guardado'; no partial_pages"))
        except (sqlite3.Error,ValueError) as exc:
            inventory.append(dict(module='manifiestos',path=relative(path),status='no disponible',reason=str(exc)))
    for procedure in ('tabla','duas','movimientos','contenedores'):
        inventory.append(dict(module='manifiestos',procedure=procedure,status='sin muestra local confirmada',
                              reason='Esquema disponible en el código; no se ejecutó el procedimiento para obtener datos.'))
    return list(records.values()), inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=32)
    parser.add_argument('--output',type=Path,default=ROOT/'runtime/investigacion_dashboard')
    args = parser.parse_args()
    if not 1<=args.limit<=100: parser.error('La muestra debe ser de 1 a 100 DUAs por fuente.')
    datasets,inventory = {},[]
    target = set()
    for module in ('talon','xmovimientos','duas_transito'):
        rows,sources=fetch_jobs(module,args.limit)
        datasets[module]=rows;inventory.extend(sources)
        target.update(row['numero_del_dua'] for row in rows)
    empty=sample_empty(args.limit);target.update(row['dua'] for row in empty)
    baseline,sources=fetch_jobs('detalles',args.limit)
    linked,_=fetch_jobs('detalles',args.limit,sorted(target))
    datasets['detalles']=list({r['numero_del_dua']:r for r in baseline+linked}.values())
    for source in sources: source['sampledDuas']=sum(r['_source']==source['path'] for r in datasets['detalles'])
    inventory.extend(sources)
    datasets['empty']=empty
    datasets['bls'],datasets['bl_jobs'],sources=sample_bls(min(args.limit,24));inventory.extend(sources)
    datasets['conocimientos'],sources=sample_knowledge(args.limit,datasets['bl_jobs']);inventory.extend(sources)
    keys={m:{r['numero_del_dua'] for r in datasets[m]} for m in MODULES}
    cargo={(r['IDManifiesto'],r['Secuencia Tica'],r['BL original']) for r in datasets['conocimientos']}
    joins=[dict(left='detalles',right=m,matched=len(keys['detalles']&keys[m]),sampled=len(keys[m]),
                key='aduana + año + número',direction='DUAs de '+m+' con Detalles') for m in MODULES if m!='detalles']
    joins.append(dict(left='conocimientos',right='bls',matched=sum((r['manifest'],r['sequence'],r['bl']) in cargo for r in datasets['bl_jobs']),
        sampled=len(datasets['bl_jobs']),key='manifiesto compuesto + secuencia TICA; BL comercial verificado',direction='BLs con conocimiento confirmado'))
    now=datetime.now().astimezone().isoformat(timespec='seconds')
    obj=dict(capturedAt=now,limitPerSource=args.limit,datasets=datasets,inventory=inventory,joins=joins,
        notes=['Muestreo intencional, no aleatorio ni representativo del total.',
               'No se extrapolan cifras ni se declara cobertura mensual.',
               'Cada fuente se leyó en un instante distinto; no es un corte transaccional conjunto.',
               'Los bultos de movimientos son eventos; no representan inventario actual.',
               'Valor_MN es importe tributario reportado, no pago bancario confirmado.',
               'No se ha demostrado un vínculo local DUA–BL: falta la tabla de asociaciones.',
               'Todas las identidades se conservan como texto. No se usaron coincidencias por nombre.'])
    encoded=json.dumps(obj,ensure_ascii=False,indent=2)
    obj['sampleHash']=hashlib.sha256(encoded.encode()).hexdigest()
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'muestra.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    embedded=json.dumps(obj,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(HERE/'dashboard.html').read_text(encoding='utf-8')
    (args.output/'index.html').write_text(template.replace('__SNAPSHOT_JSON__',embedded),encoding='utf-8')
    (args.output/'FUENTES.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(html=str((args.output/'index.html').resolve()),rows={k:len(v) for k,v in datasets.items()},joins=joins),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
