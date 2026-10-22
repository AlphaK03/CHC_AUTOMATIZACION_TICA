"""Perfil opcional y foto local, ligados a la cuenta y separados de las publicaciones."""
import hashlib
import json
import os
from pathlib import Path
import re

from .auth import AuthenticationRequired
from .graph import GraphError


class ProfileCache:
    def __init__(self, folder, graph):
        self.folder=Path(folder).resolve();self.graph=graph
        self.path=self.folder/'profile.json'
        self.data={};self.warning='';self.attempted=''
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(value,dict):self.data=value
        except (OSError,ValueError):pass

    @staticmethod
    def key(account):
        return hashlib.sha256(account['home_account_id'].encode()).hexdigest() if account else ''

    def photo_path(self, name):
        if not re.fullmatch(r'profile-[a-f0-9]{32}\.(jpg|png)',name or ''):return None
        path=self.folder/name
        return path if path.resolve().is_relative_to(self.folder) else None

    def get(self, account):
        if not account:return {}
        profile=dict(displayName=account.get('name') or account.get('username',''),email=account.get('username',''),photoUrl='')
        if self.data.get('accountKey')==self.key(account):
            profile.update({k:self.data.get(k,'') for k in ('displayName','email','jobTitle')})
            photo=self.photo_path(self.data.get('photo',''))
            if photo and photo.is_file():profile['photoUrl']=photo.as_uri()
        return profile

    def clear(self):
        photo=self.photo_path(self.data.get('photo',''))
        self.data={};self.warning='';self.attempted=''
        try:
            if photo:photo.unlink(missing_ok=True)
            self.path.unlink(missing_ok=True)
        except OSError:self.warning='No se pudo limpiar la caché de perfil; la cuenta está desconectada.'

    def refresh(self, account, force=False):
        if not account:
            self.clear();return
        key=self.key(account)
        if not force and (self.data.get('accountKey')==key or self.attempted==key):return
        if self.data and self.data.get('accountKey')!=key:self.clear()
        self.attempted=key;self.warning=''
        try:
            remote=self.graph.profile()
            data=dict(accountKey=key,displayName=remote.get('displayName') or account.get('username',''),
                      email=remote.get('mail') or remote.get('userPrincipalName') or account.get('username',''),
                      jobTitle=remote.get('jobTitle') or '',photo='')
            try:
                photo=self.graph.photo()
                if photo:
                    contents,mime=photo
                    name='profile-'+hashlib.sha256(contents).hexdigest()[:32]+('.png' if mime=='image/png' else '.jpg')
                    temporary=self.folder/'profile-photo.tmp'
                    temporary.write_bytes(contents);os.replace(temporary,self.folder/name)
                    data['photo']=name
            except Exception:
                self.warning='No se pudo actualizar la foto de perfil.'
                if self.data.get('accountKey')==key:data['photo']=self.data.get('photo','')
            previous=self.photo_path(self.data.get('photo',''))
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            os.replace(temporary,self.path);self.data=data
            if previous and previous.name!=data['photo']:previous.unlink(missing_ok=True)
        except (AuthenticationRequired,GraphError) as error:self.warning=str(error)
        except OSError:self.warning='No se pudo guardar el perfil; las publicaciones siguen disponibles.'
        except Exception:self.warning='El perfil no está disponible por ahora; las publicaciones siguen disponibles.'
