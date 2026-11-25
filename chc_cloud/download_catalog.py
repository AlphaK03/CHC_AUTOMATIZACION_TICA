"""Catálogo de descargas guardadas: solo metadatos, sin motores ni exportaciones."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from chc_runtime import output_layout
from chc_runtime.sqlite_read import prepare_reader


def identifier(owner, spec):
    return hashlib.sha256(json.dumps([owner,spec['target'],spec['filename']],ensure_ascii=False).encode()).hexdigest()


def read_catalog(roots, registry, base):
    rows={};exports={};errors=[]
    registries=dict.fromkeys([Path(registry),*(output_layout.registry_path(root) for root in roots.values())])
    for path in registries:
        if not path.is_file():continue
        try:
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
                prepare_reader(db,2);db.row_factory=sqlite3.Row
                for item in db.execute('SELECT * FROM exports WHERE final=1'):
                    record=dict(item);spec=json.loads(record['spec'])
                    if spec['target']=='manifiestos:contenedores' and spec.get('mode')!='maritimo':continue
                    if spec['target']!=record['target'] or spec['period']!=record['period']:continue
                    exports.setdefault(identifier(record['owner'],spec),{**record,'registry':str(path),'spec':spec})
        except (OSError,ValueError,sqlite3.Error):errors.append('No se pudo leer un registro de CSV.')

    def add(owner,spec,name='',module='',flow='',record_id='',state=''):
        key=identifier(owner,spec);export=exports.get(key)
        path=Path(export['path']) if export else Path(base).joinpath(*spec['relativeFolders'],spec['filename'])
        rows[key]=dict(id=key,owner=owner,target=spec['target'],period=spec['period'],
            procedure=output_layout.FLOWS.get(spec['target'].split(':')[-1],output_layout.BOTS.get(spec['target'],spec['target'])),
            periodLabel=output_layout.month_label(spec['period']),mode=spec.get('mode',''),
            name=name or path.stem,module=module,flow=flow,recordId=record_id,state=state,
            filename=spec['filename'],relativePath='/'.join([*spec['relativeFolders'],spec['filename']]),
            path=str(path),registry=export['registry'] if export else str(registry),
            csvReady=bool(export and path.is_file()),canGenerate=bool(record_id),spec=spec)

    for key,export in exports.items():add(export['owner'],export['spec'])
    for module,root in roots.items():
        root=Path(root)
        if module in ('detalles','duas_transito','talon','xmovimientos'):
            path=root/'data/queues/catalog.sqlite3'
            if not path.is_file():continue
            try:
                with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
                    prepare_reader(db,2);db.row_factory=sqlite3.Row
                    for raw in db.execute('SELECT * FROM saved_tables WHERE deleted=0'):
                        record=dict(raw)
                        if not (path.parent/record['filename']).is_file():continue
                        add(module+':'+record['id'],output_layout.dua_spec(module,record),record['name'],module,'',record['id'])
            except (OSError,ValueError,sqlite3.Error):errors.append(module+': catálogo sin verificar.')
            continue
        for flow in (('bls',) if module=='bls' else output_layout.FLOWS if module=='manifiestos' else ()):
            path=root/'data/workbench'/flow/'session.json'
            if not path.is_file():continue
            try:
                history=json.loads(path.read_text(encoding='utf-8'))['history']
                for record in history:
                    owner=flow+':'+record['id']
                    if flow=='bls':
                        specs=record.get('publicSpecs',[]) or [e['spec'] for e in exports.values() if e['owner']==owner and e['target']=='bls']
                        if not specs:
                            # Los meses reales se obtienen del payload al exportar,
                            # nunca del nombre de un lote BLs antiguo o multimes.
                            spec=output_layout.specification('bls',qualifier='LOTE_'+record['id'])
                            specs=[spec]
                    else:
                        specs=[output_layout.manifest_spec(flow,record,mode) for mode in record['spec']['modes']
                               if flow!='contenedores' or mode=='maritimo']
                    for spec in specs:add(owner,spec,record['name'],module,flow,record['id'],record.get('state',''))
            except (OSError,KeyError,TypeError,ValueError):errors.append(flow+': historial sin verificar.')
    return {'rows':sorted(rows.values(),key=lambda row:(row['period'],row['target'],row['name'],row['mode']),reverse=True),'errors':errors}
