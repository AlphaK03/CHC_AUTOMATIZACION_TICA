"""Ampliación de colas del Workbench; los motores originales permanecen intactos."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from urllib.parse import urlsplit
from .manifest_coverage import selection_signature


def family(scope):
    value={k:v for k,v in scope.items() if k not in
            ('desde','hasta','start','end','modes','workbench_cumulative')}
    if urlsplit(value.get('url','')).hostname in ('127.0.0.1','localhost'):
        value['url']='fixture:'+urlsplit(value['url']).path
    return value


def query_range(scope, at=None):
    at=at or datetime.now(timezone(timedelta(hours=-6)))
    if at.tzinfo is None:at=at.replace(tzinfo=timezone.utc)
    local=at.astimezone(timezone(timedelta(hours=-6)))
    cutoff=local.date()-timedelta(days=2 if local.hour==0 and local.minute==0 else 1)
    start=scope.get('desde') or scope.get('start')
    end=scope.get('hasta') or scope.get('end')
    return start,min(end,cutoff.isoformat())


class IncrementalStore:
    enable_cumulative=False

    def __init__(self,csv_path,scope,*args,db_path=None,**kwargs):
        self.cumulative=bool((self.enable_cumulative or scope.get('workbench_cumulative'))
                             and not scope.get('ids') and not scope.get('limit'))
        self.query_id=None
        self.scope_ids=None
        requested={**scope,'workbench_cumulative':True} if self.cumulative else scope
        path=Path(db_path) if db_path else Path(csv_path).with_suffix('.sqlite3')
        stored=None
        if self.cumulative and path.exists():
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                row=db.execute('SELECT scope FROM metadata').fetchone()
                stored=json.loads(row[0]) if row else None
            if stored and family(stored)!=family(requested):
                raise ValueError('El acumulado pertenece a otro mes, modalidad o filtros.')
        super().__init__(csv_path,stored or requested,*args,db_path=db_path,**kwargs)
        if not self.cumulative:return
        try:
            existed=self.db.execute("SELECT 1 FROM sqlite_master WHERE name='workbench_queries'").fetchone()
            columns={row[1] for row in self.db.execute('PRAGMA table_info(workbench_queries)')}
            if stored and (not existed or 'expected' not in columns):
                backup_root=next((parent.parent for parent in self.db_path.parents
                                  if parent.name=='jobs' and parent.parent.name=='data'),self.db_path.parent)
                backup=backup_root/'backups'/('incremental-'+uuid.uuid4().hex+'.sqlite3')
                backup.parent.mkdir(parents=True,exist_ok=True)
                with closing(sqlite3.connect(backup)) as copy:self.db.backup(copy)
            self.db.executescript('''CREATE TABLE IF NOT EXISTS workbench_queries (
                id TEXT PRIMARY KEY,start TEXT NOT NULL,end TEXT NOT NULL,finished TEXT,
                expected INTEGER NOT NULL,signature TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workbench_query_jobs (
                query_id TEXT NOT NULL,manifest TEXT NOT NULL,PRIMARY KEY(query_id,manifest));''')
            if existed and 'expected' not in columns:
                with self.db:
                    self.db.execute('ALTER TABLE workbench_queries ADD COLUMN expected INTEGER NOT NULL DEFAULT 0')
                    self.db.execute("ALTER TABLE workbench_queries ADD COLUMN signature TEXT NOT NULL DEFAULT ''")
            # La selección anterior se congeló en su primera consulta, no en la
            # fecha de una reanudación posterior. Nunca acreditar fechas futuras.
            if stored and not existed:
                first=self.db.execute('SELECT started FROM runs ORDER BY rowid LIMIT 1').fetchone()
                last=self.db.execute('SELECT finished,state FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
                if first and last and last[0] and last[1].startswith('Finalizada'):
                    try:
                        start,end=query_range(stored,datetime.fromisoformat(first[0]))
                    except (ValueError,TypeError):start,end='1','0'
                    if start<=end:
                        with self.db:
                            ids=[row[0] for row in self.db.execute('SELECT id FROM jobs')]
                            self.db.execute('INSERT INTO workbench_queries VALUES (?,?,?,?,?,?)',('legacy',start,end,last[0],len(ids),selection_signature(ids)))
                            self.db.execute("INSERT INTO workbench_query_jobs SELECT 'legacy',id FROM jobs")
            with self.db:self.db.execute('UPDATE metadata SET scope=?',(json.dumps(requested,sort_keys=True),))
            self.requested_scope=requested
        except BaseException:
            self.close();raise

    def prepare_selection(self,jobs):
        if not self.cumulative:return super().prepare_selection(jobs)
        jobs=list(jobs)
        ids=[item[3] for item in jobs]
        if len(ids)!=len(set(ids)):raise ValueError('La consulta repitió una identidad de manifiesto.')
        self.scope_ids=set(ids)
        self.query_id=uuid.uuid4().hex
        start,end=query_range(self.requested_scope)
        with self.db:
            ordinal=self.db.execute('SELECT coalesce(max(ordinal),0) FROM jobs').fetchone()[0]
            for source_ordinal,href,info,mid in jobs:
                if self.db.execute('SELECT 1 FROM jobs WHERE id=?',(mid,)).fetchone():continue
                ordinal+=1
                completed=self.db.execute('SELECT stats FROM manifests WHERE id=?',(mid,)).fetchone()
                stats=json.loads(completed[0]) if completed else {}
                self.db.execute('''INSERT INTO jobs
                    (id,ordinal,source_ordinal,state,pages,read_count,kept_count,updated)
                    VALUES (?,?,?,?,?,?,?,?)''',(mid,ordinal,source_ordinal,'Guardado' if completed else 'Pendiente',
                    stats.get('pages',0),stats.get('read',0),stats.get('kept',0),datetime.now(timezone.utc).isoformat()))
            self.db.execute('INSERT OR IGNORE INTO selection VALUES (1)')
            self.db.execute('INSERT INTO workbench_queries VALUES (?,?,?,NULL,?,?)',
                            (self.query_id,start,end,len(ids),selection_signature(ids)))
            self.db.executemany('INSERT INTO workbench_query_jobs VALUES (?,?)',((self.query_id,mid) for mid in ids))

    def jobs(self):
        jobs=super().jobs()
        return jobs if self.scope_ids is None else [job for job in jobs if job['id'] in self.scope_ids]

    def finish_run(self,expected_attempts):
        result=super().finish_run(expected_attempts)
        if self.cumulative and self.query_id:
            with self.db:self.db.execute('UPDATE workbench_queries SET finished=? WHERE id=?',
                (datetime.now(timezone.utc).isoformat(),self.query_id))
        return result
