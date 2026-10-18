"""Cola durable de copias CSV: un fallo online nunca cambia progreso TICA."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid

from .auth import CloudAccount
from .graph import GraphClient, GraphError, places_address, site_address
from chc_runtime import output_layout

TARGETS = [('detalles','Detalles'), ('duas_transito','DUAs Tránsito'), ('talon','Talón'),
           ('xmovimientos','XMovimientos'), ('bls','BLs'), ('manifiestos:tabla','Manifiestos'),
           ('manifiestos:conocimientos','Conocimientos'), ('manifiestos:duas','DUAs por manifiesto'),
           ('manifiestos:movimientos','Movimientos de manifiesto'), ('manifiestos:contenedores','Contenedores')]
PROCEDURES = {'tabla':'Listado','conocimientos':'Conocimientos','duas':'DUAs',
              'movimientos':'Movimientos','contenedores':'Contenedores'}


def bot_folders(target):
    if target.startswith('manifiestos:') and target.split(':',1)[1] in PROCEDURES:
        return ['MANIFIESTOS',output_layout.FLOWS[target.split(':',1)[1]]]
    if target in dict(TARGETS):
        return [output_layout.BOTS[target]]
    raise ValueError('Bot de exportación desconocido.')


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
    def __init__(self, folder, app_settings, account=None, graph=None, monthly=None):
        self.folder = Path(folder)
        (self.folder/'spool').mkdir(parents=True, exist_ok=True)
        self.settings_path = self.folder/'destinations.json'
        saved = json.loads(self.settings_path.read_text(encoding='utf-8')) if self.settings_path.exists() else {}
        self.destination = saved.get('root',{}) if saved.get('version')==2 else {}
        self.legacy_destinations = saved if saved and saved.get('version')!=2 else {}
        self.account = account or CloudAccount(self.folder, app_settings)
        self.graph = graph or GraphClient(self.account)
        self.exports_settings=self.folder.parent/'exports.json'
        self.exports_registry=output_layout.registry_path(settings=self.exports_settings)
        self.monthly_reader=monthly
        self.monthly_cache=None
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
        with self.db:
            for row in self.db.execute("SELECT id,destination FROM jobs WHERE state IN ('pending','error')").fetchall():
                if json.loads(row['destination']).get('layoutVersion')!=2:
                    self.db.execute("UPDATE jobs SET state='paused',error='Elige la carpeta común; los avisos anteriores se conservan.' WHERE id=?",(row['id'],))
        self.browse_site = None
        self.collection_error = ''
        self.sites_path = self.folder/'known_sites.json'
        self.known_sites = json.loads(self.sites_path.read_text(encoding='utf-8')) if self.sites_path.exists() else []

    def account_info(self):
        # Una instalación sin cuenta no necesita descubrir autoridades por red.
        if isinstance(self.account, CloudAccount) and self.account.app is None and not (self.folder/'tokens.dpapi').exists():
            return None
        return self.account.current()

    def snapshot(self):
        account = self.account_info()
        tasks = [dict(r) for r in self.db.execute('SELECT target,name,filename,state,error,updated FROM jobs ORDER BY updated DESC LIMIT 50')]
        return {'account': account.get('username','') if account else '',
                'connected': bool(account), 'destination': self.destination,
                'needsFolderSelection': bool(self.legacy_destinations),
                'localRoot':str(output_layout.local_root(settings=self.exports_settings)),
                'months':self.months(),
                'tasks': tasks, 'queueError':self.collection_error,
                'pending': self.db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('pending','uploading','error')").fetchone()[0]}

    def completed_targets(self,refresh=False):
        if refresh or self.monthly_cache is None:
            if self.monthly_reader:
                data=self.monthly_reader()
            else:
                from workbench.monthly_progress import MonthlyReader
                roots={m:output_layout.ROOT/'bots'/m for m in (*output_layout.BOTS,'manifiestos')}
                data=MonthlyReader(roots).read()
            self.monthly_cache={}
            for row in data['rows']:
                targets={c['module'] for c in row['cells'] if c['status'] in ('completed','up_to_date') and c['module']!='manifiestos'}
                for flow,cell in zip(output_layout.FLOWS,row['procedures']):
                    if cell['status'] in ('completed','up_to_date'):targets.add('manifiestos:'+flow)
                self.monthly_cache[row['period']]={'targets':targets,'label':row['label']}
        return self.monthly_cache

    def inventory(self):
        if not self.exports_registry.exists():return []
        with closing(sqlite3.connect(self.exports_registry.as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row
            base=output_layout.local_root(settings=self.exports_settings)
            return [dict(r) for r in db.execute('SELECT * FROM exports WHERE final=1') if Path(r['path']).is_file() and Path(r['path']).resolve().is_relative_to(base)]

    def months(self):
        completed=self.completed_targets()
        groups={}
        for row in self.inventory():
            if row['target'] not in completed.get(row['period'],{}).get('targets',set()):continue
            groups.setdefault(row['period'],[]).append(row)
        return [{'period':key,'label':completed[key]['label'],'files':len(files),
                 'bots':len({r['target'] for r in files})} for key,files in sorted(groups.items(),reverse=True)]

    def upload_month(self,key):
        if not self.account_info() or not self.destination.get('enabled'):
            raise ValueError('Conecta tu cuenta y elige la carpeta común de SharePoint.')
        completed=self.completed_targets(refresh=True)
        eligible=[r for r in self.inventory() if r['period']==key and r['target'] in completed.get(key,{}).get('targets',set())]
        if not eligible:raise ValueError('El mes no tiene CSV de bots completos, al día o cerrados manualmente. Exporta sus resultados y vuelve a actualizar.')
        for row in eligible:
            self.enqueue({'target':row['target'],'path':row['path'],'name':key,'owner':row['owner'],'spec':json.loads(row['spec'])})
        self.sync(key)

    def connect(self):
        self.account.connect()

    def save_destination(self, drive, item):
        if not self.browse_site or drive not in [d['id'] for d in self.browse_site['drives']]:
            raise ValueError('Selecciona primero el sitio y la biblioteca.')
        account = self.account_info()
        if not account:
            raise ValueError('Conecta una cuenta CHC antes de elegir una carpeta.')
        current = self.graph.folders(drive, item)['folder']
        old = self.destination
        if self.legacy_destinations:
            backup=self.folder/'destinations_legacy.json'
            if not backup.exists():atomic_json(backup,self.legacy_destinations)
        if self.legacy_destinations or (old and (old.get('driveId'),old.get('folderId'),old.get('accountId')) != (drive,current['id'],account['home_account_id'])):
            with self.db:
                self.db.execute("UPDATE jobs SET state='paused',error='Destino cambiado; se conserva la copia local.' WHERE state!='synced'")
        self.destination = {'driveId': drive, 'folderId': current['id'], 'folderName': current['name'],
            'webUrl': current.get('webUrl',''), 'siteId': self.browse_site['site']['id'],
            'accountId': account['home_account_id'], 'enabled': True}
        atomic_json(self.settings_path, {'version':2,'root':self.destination})
        self.legacy_destinations={}

    def enqueue(self, request):
        destination = self.destination
        if not destination or not destination.get('enabled'):
            return
        source = Path(request['path']).resolve()
        safe_name(request['name'])
        if source.suffix.lower() != '.csv' or not source.is_file():
            raise ValueError('Solo se publican CSV de resultados existentes.')
        spec=request.get('spec') or output_layout.specification(request['target'],output_layout.period(request['name']))
        if spec['target']!=request['target']:raise ValueError('El CSV no pertenece al bot seleccionado.')
        name, filename = safe_name(output_layout.month_label(spec['period'])),safe_name(spec['filename'])
        destination={**destination,'layoutVersion':2,'relativeFolders':[safe_name(v) for v in spec['relativeFolders']],
                     'period':spec['period']}
        identity = json.dumps([destination['accountId'],destination['driveId'],destination['folderId'],
                               [v.casefold() for v in destination['relativeFolders']],filename.casefold()])
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
            if old and old['digest']==digest and old['state']!='paused':
                return
            spool = self.folder/'spool'/(key+'.csv')
            os.replace(temporary, spool)
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (key,request['target'],request['owner'],name,filename,json.dumps(destination),digest,str(spool),'pending','',datetime.now(timezone.utc).isoformat()))
        finally:
            temporary.unlink(missing_ok=True)

    def sync(self,month=None):
        completed=self.completed_targets(refresh=True)
        account = self.account_info()
        if not account:
            return
        for row in list(self.db.execute("SELECT * FROM jobs WHERE state='pending' ORDER BY updated")):
            row = dict(row)
            destination = json.loads(row['destination'])
            if month and destination.get('period')!=month:continue
            current = self.destination
            if destination.get('layoutVersion')!=2 or destination['accountId'] != account['home_account_id'] or not current.get('enabled') or any(destination.get(k)!=current.get(k) for k in ('accountId','driveId','folderId')):
                continue
            if row['target'] not in completed.get(destination.get('period',''),{}).get('targets',set()):
                with self.db:self.db.execute("UPDATE jobs SET state='error',error='El mes ya no está completo, al día ni cerrado manualmente; se conservó la copia local.' WHERE id=?",(row['id'],))
                continue
            if self.exports_registry.exists():
                with closing(sqlite3.connect(self.exports_registry.as_uri()+'?mode=ro',uri=True)) as exports:
                    registered=exports.execute("SELECT final FROM exports WHERE owner=? AND target=? AND json_extract(spec,'$.filename')=?",
                        (row['owner'],row['target'],row['filename'])).fetchall()
                if registered and not any(value[0] for value in registered):
                    with self.db:self.db.execute("UPDATE jobs SET state='paused',error='CSV anterior sustituido por el acumulado mensual; copia local conservada.' WHERE id=?",(row['id'],))
                    continue
            with self.db:
                self.db.execute("UPDATE jobs SET state='uploading',error='' WHERE id=?",(row['id'],))
            try:
                parent=destination['folderId']
                for folder in destination['relativeFolders']:
                    parent=self.graph.ensure_folder(destination['driveId'],parent,safe_name(folder))
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
        # Los avisos de la versión automática se conservan y no se envían.
        return

    def execute(self, request):
        command = request['command']
        result = {}
        if command == 'connect':
            self.connect()
        elif command == 'disconnect':
            self.account.disconnect()
        elif command == 'site':
            host = places_address(request['url'])
            if host:
                self.browse_site = None
                sites = self.graph.sites(host,request.get('search',''))
                self.known_sites = sites
                atomic_json(self.sites_path,sites)
                result['browse'] = {'places':True,'host':host,'sites':sites, 'drives':[]}
            else:
                self.browse_site = self.graph.site(request['url'])
                result['browse'] = self.browse_site
        elif command == 'sites':
            host,_=site_address(request['url'])
            sites=self.graph.sites(host,request.get('search',''))
            self.known_sites=sites
            atomic_json(self.sites_path,sites)
            result['browse']={'places':True,'host':host,'sites':sites,'drives':[]}
            self.browse_site=None
        elif command == 'folders':
            if not self.browse_site or request['drive'] not in [d['id'] for d in self.browse_site['drives']]:
                raise ValueError('Selecciona una biblioteca del sitio autorizado.')
            result['browse'] = {**self.browse_site, **self.graph.folders(request['drive'],request.get('item','root')), 'driveId':request['drive']}
        elif command == 'save':
            self.save_destination(request['drive'],request['item'])
        elif command == 'remove':
            if self.legacy_destinations and not (self.folder/'destinations_legacy.json').exists():
                atomic_json(self.folder/'destinations_legacy.json',self.legacy_destinations)
            self.legacy_destinations={}
            self.destination={}
            atomic_json(self.settings_path,{'version':2,'root':{}})
            with self.db:
                self.db.execute("UPDATE jobs SET state='paused',error='Destino retirado; se conserva la copia local.' WHERE state!='synced'")
        elif command == 'enqueue':
            raise ValueError('Usa Subir a SharePoint para enviar un mes completo de forma explícita.')
        elif command == 'collect':
            self.collect()
        elif command == 'retry':
            with self.db:
                self.db.execute("UPDATE jobs SET state='pending',error='' WHERE state='error'")
            self.sync()
        elif command == 'sync':
            raise ValueError('La subida solo se inicia mediante una acción del usuario.')
        elif command == 'upload_month':
            self.upload_month(request['month'])
        elif command == 'local_root':
            output_layout.set_local_root(request['path'],settings=self.exports_settings)
        elif command != 'status':
            raise ValueError('Acción SharePoint desconocida.')
        if command == 'status':self.completed_targets(refresh=True)
        return {**result, 'snapshot':self.snapshot()}
