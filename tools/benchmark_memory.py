"""Compara workers reales con datos temporales; red local por defecto.

Ejecutar este mismo archivo con --code-root apuntando a cada revisión. No abre
la GUI del usuario ni sus bases. Solo --live permite consultar TICA; exige una
muestra explícita, un trabajador, una ronda y salida privada independiente.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

from process_memory import Sampler, sample_tree

DUA = ('detalles', 'duas_transito', 'talon', 'xmovimientos')
BATCH = ('tabla', 'conocimientos', 'duas', 'movimientos', 'contenedores', 'bls', 'bases', 'bls_source')


class Worker:
    def __init__(self, repo, profile, storage, fixture=True):
        self.repo, self.profile, self.storage = repo, profile, storage
        module = profile if profile in DUA or profile == 'bls' else 'manifiestos'
        python = repo / 'bots' / module / '.venv/Scripts/python.exe'
        args = [str(python), '-u', str(repo/'bots'/module/'workbench_worker.py'), '--storage-root', str(storage)]
        if profile not in DUA: args += ['--flow', profile]
        if fixture: args += ['--offline-fixture']
        self.process = subprocess.Popen(args, cwd=repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
        # Cerrar la familia solo de este worker si falla una prueba.
        sys.path.insert(0, str(repo/'workbench'))
        from process_guard import ProcessTreeGuard
        self.guard = ProcessTreeGuard()
        try:
            self.guard.attach(self.process.pid)
        except BaseException:
            self.process.terminate(); self.process.wait(10)
            for stream in (self.process.stdin,self.process.stdout,self.process.stderr): stream.close()
            raise
        self.events, self.stderr = queue.Queue(), []
        self.sequence = 0
        def read():
            for line in self.process.stdout:
                try: self.events.put(json.loads(line))
                except ValueError: self.stderr.append(line[-2000:])
            self.events.put({'event':'eof'})
        def errors():
            for line in self.process.stderr:
                self.stderr.append(line[-2000:]); self.stderr[:] = self.stderr[-25:]
        self.readers = [threading.Thread(target=read, daemon=True), threading.Thread(target=errors, daemon=True)]
        for reader in self.readers: reader.start()
        self.sampler = Sampler(self.process.pid); self.sampler.__enter__()

    def wait(self, predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('El worker no completó la respuesta dentro del plazo de la prueba.')
            event = self.events.get(timeout=max(.01, deadline-time.monotonic()))
            if event.get('event')=='log' and '| Descargando |' in event.get('message',''):
                self.sampler.phase = 'extracting'
            if event.get('event') in ('error','fatal','eof'):
                raise RuntimeError(str(event)+'\n'+''.join(self.stderr)[-2500:])
            if predicate(event): return event

    def call(self, command, data=None, timeout=120):
        self.sequence += 1
        request = {'command':command, 'requestId':self.sequence, **(data or {})}
        self.process.stdin.write(json.dumps(request)+'\n'); self.process.stdin.flush()
        reply = self.wait(lambda e:e.get('event')=='result' and e.get('requestId')==self.sequence, timeout)
        self.wait(lambda e:e.get('event')=='idle' and (self.profile not in DUA or e.get('requestId')==self.sequence), timeout)
        self.sampler.phase = 'idle'
        return reply

    def ready(self):
        if self.profile not in DUA: self.wait(lambda e:e.get('event')=='ready')
        reply = self.call('initialize' if self.profile in DUA else 'refresh')
        if self.profile=='bls_source': self.call('knowledge_catalog')
        return reply

    def close(self):
        try:
            if self.process.poll() is None:
                self.process.stdin.write('{"command":"shutdown"}\n'); self.process.stdin.flush()
                self.process.wait(timeout=35)
        finally:
            self.guard.close()
            if self.process.poll() is None: self.process.wait(timeout=10)
            self.sampler.__exit__()
            for reader in self.readers: reader.join(5)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr): stream.close()


def source_xlsx(repo, profile, path, values):
    code = ('import sys,json; from openpyxl import Workbook; b=Workbook(); b.active.title="base"; '
            'b.active.append(["NroDUA"]); [b.active.append([s]) for s in json.loads(sys.argv[2])]; '
            'b.save(sys.argv[1]); b.close()')
    subprocess.run([str(repo/'bots'/profile/'.venv/Scripts/python.exe'), '-c', code, str(path), json.dumps(values)], check=True, timeout=30)


def bls_source(path, values=None):
    columns = ['IDManifiesto','Secuencia Tica','BL original','Fecha Manifiesto','Mes']
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE BLS ('+','.join('"'+c+'" TEXT' for c in columns)+')')
        db.executemany('INSERT INTO BLS VALUES (?,?,?,?,?)', values or [
            ('1-0-20260001-P027-01/10/26','001','00001234567890123456789','01/10/26','Octubre'),
            ('1-0-20260001-P027-01/10/26','003','000000000000000000003','01/10/26','Octubre')])


def fingerprint(storage):
    # CSV explícitamente exportados desde SQLite: igualdad de columnas, filas,
    # texto, ceros, orden y multiplicidad. No comparar timestamps ni UUID de lotes.
    files = sorted(storage.rglob('*.CSV'))
    digests = []
    for path in files:
        with path.open(encoding='utf-8-sig', newline='') as stream: rows = list(csv.reader(stream))
        digests.append(dict(columns=len(rows[0]) if rows else 0, rows=max(0,len(rows)-1),
            sha256=hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()))
    return sorted(digests, key=lambda x:x['sha256'])


def run_profile(repo, profile, storage, mode, sample=None):
    source = storage/'input.xlsx'
    if profile in DUA and mode != 'idle':
        values = sample['duas'][profile] if sample else ['001-2026-000001','001-2026-000050']
        if mode == 'live' and not 1 <= len(values) <= 2: raise ValueError('Máximo dos DUAs por bot.')
        source_xlsx(repo, profile, source, values)
    elif profile == 'bls' and mode != 'idle':
        source = storage/'input.sqlite3'; bls_source(source, sample.get('bls') if sample else None)
    worker = Worker(repo, profile, storage, fixture=mode!='live')
    started = time.perf_counter()
    try:
        worker.ready()
        load_seconds = time.perf_counter()-started
        idle = sample_tree(worker.process.pid)
        summary = {}
        run_seconds = 0
        if mode != 'idle' and profile not in ('bases','bls_source'):
            if profile in DUA:
                worker.call('configure', {'config':{'output_base_path':str(storage/'public'),
                    'cant_hilos':1 if mode=='live' else 6,'max_retries':1,'timeout':60 if mode=='live' else 5}})
                plan = worker.call('prepare_import',{'source':str(source),'sheet':'base','name':'Memoria'})['importPlan']
                worker.call('import',plan)
                started_run = time.perf_counter(); reply=worker.call('run',timeout=240)
            else:
                config = {'year':2026,'month':10,'modes':['maritimo'],'workers':6,'headless':True,
                          'timeout':8,'name':'Memoria','max_retries':1,'outputRoot':str(storage/'public')}
                if profile=='bls': config.update(input=str(source),sheet='BLS',inputMode='file',workers=1)
                if mode=='live':
                    config.update(sample['manifests']); config['workers']=1; config['timeout']=60
                    config.update(sample.get('manifests_by_profile',{}).get(profile,{}))
                    if not config.get('manifestIds') and not config.get('limit'):
                        raise ValueError('Las pruebas reales requieren IDs o límite explícito.')
                    if profile=='bls': config.update(input=str(source),sheet='BLS',inputMode='file',workers=1)
                started_run=time.perf_counter(); reply=worker.call('run',{'config':config},timeout=300)
            run_seconds=time.perf_counter()-started_run
            summary=reply.get('snapshot',{}).get('summary',{})
            if list(storage.rglob('*.CSV')): raise AssertionError('Hubo CSV antes de exportar manualmente.')
            worker.call('export')
        result=dict(profile=profile, load_seconds=round(load_seconds,3),run_seconds=round(run_seconds,3),
            idle_resident_mib=round(sum(x['resident_mib'] for x in idle),2),
            idle_committed_mib=round(sum(x['committed_mib'] for x in idle),2),
            summary=summary, output=fingerprint(storage), **worker.sampler.summary())
        result['peak_resident_mib']=max(result['peak_resident_mib'],result['idle_resident_mib'])
        result['peak_committed_mib']=max(result['peak_committed_mib'],result['idle_committed_mib'])
        return result
    finally:
        worker.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--output',type=Path, required=True)
    parser.add_argument('--mode',choices=('idle','fixture','live'),default='fixture')
    parser.add_argument('--profiles',nargs='+',choices=(*DUA,*BATCH),default=list(DUA)+list(BATCH))
    parser.add_argument('--iterations',type=int,default=1)
    parser.add_argument('--live-sample',type=Path)
    args=parser.parse_args()
    if not 1 <= args.iterations <= 5: parser.error('Use entre una y cinco repeticiones.')
    if args.mode=='live' and (not args.live_sample or args.iterations!=1):
        parser.error('Una prueba real exige muestra explícita y una sola ronda.')
    report=dict(code_root=str(args.code_root.resolve()), mode=args.mode,
        utc=datetime.now(timezone.utc).isoformat(), metrics='MiB; resident includes shared pages; committed is not physical RAM', results=[])
    sample=json.loads(args.live_sample.read_text(encoding='utf-8')) if args.live_sample else None
    if args.mode=='live' and 'bls' in args.profiles and not sample.get('bls') and 'conocimientos' not in args.profiles:
        parser.error('BLs real requiere una muestra explícita o Conocimientos previos en esta misma prueba.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # Todos los datos se limpian tras cerrar las familias propias, incluso si falla.
    with tempfile.TemporaryDirectory(prefix='CHC-memory-') as folder:
        try:
            for iteration in range(args.iterations):
                for profile in args.profiles:
                    storage=Path(folder)/str(iteration)/profile; storage.mkdir(parents=True)
                    result=run_profile(args.code_root.resolve(),profile,storage,args.mode,sample)
                    if args.mode=='live' and profile=='conocimientos' and 'bls' in args.profiles and not sample.get('bls'):
                        for path in (storage/'public').rglob('*.CSV'):
                            with path.open(encoding='utf-8-sig',newline='') as stream:
                                for row in csv.DictReader(stream):
                                    if row.get('Courier')=='N':
                                        mid=row['IDManifiesto']
                                        sample['bls']=[[mid,row['Secuencia Tica'],row['BL original'],mid.split('-')[-1],'Septiembre']]
                                        break
                            if sample.get('bls'): break
                        if not sample.get('bls'): raise RuntimeError('La muestra no obtuvo un BL Courier N verificable.')
                    result['iteration']=iteration+1; report['results'].append(result)
                    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    print(json.dumps(result,ensure_ascii=False),flush=True)
        finally:
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
