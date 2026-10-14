"""Cola durable de copias CSV: un fallo online nunca cambia progreso TICA."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid

from .auth import CloudAccount
from .graph import GraphClient, GraphError

TARGETS = [('detalles','Detalles'), ('duas_transito','DUAs Tránsito'), ('talon','Talón'),
           ('xmovimientos','XMovimientos'), ('bls','BLs'), ('manifiestos:tabla','Manifiestos'),
           ('manifiestos:conocimientos','Conocimientos'), ('manifiestos:duas','DUAs por manifiesto'),
           ('manifiestos:movimientos','Movimientos de manifiesto'), ('manifiestos:contenedores','Contenedores')]


def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def safe_name(value):
    value = str(value).strip()
    if not value or value in ('.','..') or any(c in value for c in '/\\<>:"|?*') or any(ord(c)<32 for c in value):
        raise ValueError('El nombre del lote no es válido para exportar.')
    return value.rstrip('. ')


class CloudService:
    def __init__(self, folder, app_settings, account=None, graph=None):
        self.folder = Path(folder)
        (self.folder/'spool').mkdir(parents=True, exist_ok=True)
        self.settings_path = self.folder/'destinations.json'
        self.destinations = json.loads(self.settings_path.read_text(encoding='utf-8')) if self.settings_path.exists() else {}
        self.account = account or CloudAccount(self.folder, app_settings)
        self.graph = graph or GraphClient(self.account)
        self.db = sqlite3.connect(self.folder/'publications.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, target TEXT NOT NULL, owner TEXT NOT NULL, name TEXT NOT NULL,
            filename TEXT NOT NULL, destination TEXT NOT NULL, digest TEXT NOT NULL,
            spool TEXT NOT NULL, state TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS bindings (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, itemId TEXT NOT NULL, etag TEXT NOT NULL);
          UPDATE jobs SET state='pending' WHERE state='uploading';
        ''')
        self.browse_site = None
        self.collection_error = ''

    def account_info(self):
        # Una instalación sin cuenta no necesita descubrir autoridades por red.
        if isinstance(self.account, CloudAccount) and self.account.app is None and not (self.folder/'tokens.dpapi').exists():
            return None
        return self.account.current()

    def snapshot(self):
        account = self.account_info()
        tasks = [dict(r) for r in self.db.execute('SELECT target,name,filename,state,error,updated FROM jobs ORDER BY updated DESC LIMIT 50')]
        return {'account': account.get('username','') if account else '',
                'connected': bool(account), 'destinations': [{'key':key,'label':label,**self.destinations.get(key,{})} for key,label in TARGETS],
                'tasks': tasks, 'queueError':self.collection_error,
                'pending': self.db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('pending','uploading','error')").fetchone()[0] + len(list((self.folder/'outbox').glob('*.json')))}

    def connect(self):
        self.account.connect()

    def save_destination(self, key, drive, item):
        if key not in dict(TARGETS) or not self.browse_site or drive not in [d['id'] for d in self.browse_site['drives']]:
            raise ValueError('Selecciona primero el sitio y la biblioteca.')
        account = self.account_info()
        if not account:
            raise ValueError('Conecta una cuenta CHC antes de elegir una carpeta.')
        current = self.graph.folders(drive, item)['folder']
        old = self.destinations.get(key, {})
        if old and (old.get('driveId'),old.get('folderId'),old.get('accountId')) != (drive,current['id'],account['home_account_id']):
            with self.db:
                self.db.execute("UPDATE jobs SET state='paused',error='Destino cambiado; se conserva la copia local.' WHERE target=? AND state!='synced'",(key,))
        self.destinations[key] = {'driveId': drive, 'folderId': current['id'], 'folderName': current['name'],
            'webUrl': current.get('webUrl',''), 'siteId': self.browse_site['site']['id'],
            'accountId': account['home_account_id'], 'enabled': True}
        atomic_json(self.settings_path, self.destinations)

    def enqueue(self, request):
        destination = self.destinations.get(request['target'])
        if not destination or not destination.get('enabled'):
            return
        source = Path(request['path']).resolve()
        if source.suffix.lower() != '.csv' or not source.is_file():
            raise ValueError('Solo se publican CSV de resultados existentes.')
        name, filename = safe_name(request['name']), safe_name(source.name)
        identity = json.dumps([destination['accountId'],destination['driveId'],destination['folderId'],name.casefold(),filename.casefold()])
        key = hashlib.sha256(identity.encode()).hexdigest()
        old = self.db.execute('SELECT * FROM jobs WHERE id=?', (key,)).fetchone()
        if old and old['owner'] != request['owner']:
            raise GraphError('Otro lote utiliza este destino online. Cambia su carpeta para conservar ambos.')
        temporary = self.folder/'spool'/f'{uuid.uuid4().hex}.csv'
        try:
            before = source.stat()
            shutil.copyfile(source, temporary)
            after = source.stat()
            if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):
                raise GraphError('El CSV se está actualizando. Se enviará en la próxima exportación.')
            digest_hash = hashlib.sha256()
            with temporary.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    digest_hash.update(chunk)
            digest = digest_hash.hexdigest()
            if old and old['digest']==digest:
                return
            spool = self.folder/'spool'/(key+'.csv')
            os.replace(temporary, spool)
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (key,request['target'],request['owner'],name,filename,json.dumps(destination),digest,str(spool),'pending','',datetime.now(timezone.utc).isoformat()))
        finally:
            temporary.unlink(missing_ok=True)

    def sync(self):
        self.collect()
        account = self.account_info()
        if not account:
            return
        for row in list(self.db.execute("SELECT * FROM jobs WHERE state='pending' ORDER BY updated")):
            row = dict(row)
            destination = json.loads(row['destination'])
            current = self.destinations.get(row['target'],{})
            if destination['accountId'] != account['home_account_id'] or not current.get('enabled') or any(destination.get(k)!=current.get(k) for k in ('accountId','driveId','folderId')):
                continue
            with self.db:
                self.db.execute("UPDATE jobs SET state='uploading',error='' WHERE id=?",(row['id'],))
            try:
                parent = self.graph.ensure_folder(destination['driveId'],destination['folderId'],row['name'])
                previous = self.db.execute('SELECT * FROM bindings WHERE id=?',(row['id'],)).fetchone()
                if previous and previous['owner'] != row['owner']:
                    raise GraphError('El archivo online pertenece a otro lote.')
                # El spool tiene nombre interno; publicar con el nombre CSV original.
                staging = self.folder/'spool'/row['id']
                staging.mkdir(exist_ok=True)
                path = staging/row['filename']
                shutil.copyfile(row['spool'],path)
                try:
                    result = self.graph.upload(destination['driveId'],parent,path,dict(previous) if previous else None)
                finally:
                    path.unlink(missing_ok=True)
                if not result.get('id') or not result.get('eTag'):
                    raise GraphError('SharePoint no confirmó el archivo; queda pendiente.')
                with self.db:
                    self.db.execute('INSERT OR REPLACE INTO bindings VALUES(?,?,?,?)',(row['id'],row['owner'],result['id'],result['eTag']))
                    self.db.execute("UPDATE jobs SET state='synced',error='' WHERE id=?",(row['id'],))
                Path(row['spool']).unlink(missing_ok=True)
            except Exception as error:
                from .auth import AuthenticationRequired
                message = str(error) if isinstance(error,(GraphError,AuthenticationRequired,ValueError)) else 'No se pudo publicar. El CSV local se conserva; puedes reintentar.'
                with self.db:
                    self.db.execute("UPDATE jobs SET state='error',error=? WHERE id=?",(message,row['id']))

    def collect(self):
        self.collection_error = ''
        for path in sorted((self.folder/'outbox').glob('*.json')):
            try:
                request=json.loads(path.read_text(encoding='utf-8'))
                self.enqueue(request)
                path.unlink()
            except Exception as error:
                # Conservar el aviso; una próxima exportación puede resolverlo.
                self.collection_error=str(error) if isinstance(error,(ValueError,GraphError)) else 'Una copia online sigue pendiente de preparar. Conserva el CSV local y vuelve a exportar.'
                continue

    def execute(self, request):
        command = request['command']
        result = {}
        if command == 'connect':
            self.connect()
        elif command == 'disconnect':
            self.account.disconnect()
        elif command == 'site':
            self.browse_site = self.graph.site(request['url'])
            result['browse'] = self.browse_site
        elif command == 'folders':
            if not self.browse_site or request['drive'] not in [d['id'] for d in self.browse_site['drives']]:
                raise ValueError('Selecciona una biblioteca del sitio autorizado.')
            result['browse'] = {**self.browse_site, **self.graph.folders(request['drive'],request.get('item','root')), 'driveId':request['drive']}
        elif command == 'save':
            self.save_destination(request['key'],request['drive'],request['item'])
        elif command == 'remove':
            self.destinations.pop(request['key'],None)
            atomic_json(self.settings_path,self.destinations)
            with self.db:
                self.db.execute("UPDATE jobs SET state='paused',error='Destino retirado; se conserva la copia local.' WHERE target=? AND state!='synced'",(request['key'],))
        elif command == 'enqueue':
            self.enqueue(request)
        elif command == 'collect':
            self.collect()
        elif command == 'retry':
            with self.db:
                self.db.execute("UPDATE jobs SET state='pending',error='' WHERE state='error'")
            self.sync()
        elif command == 'sync':
            self.sync()
        elif command != 'status':
            raise ValueError('Acción SharePoint desconocida.')
        if command == 'status':self.collect()
        return {**result, 'snapshot':self.snapshot()}
