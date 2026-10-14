"""Microsoft Graph: sitios autorizados, carpetas y publicación condicionada."""
from pathlib import Path
import time
from urllib.parse import quote, unquote, urlsplit

from .auth import AuthenticationRequired

GRAPH = 'https://graph.microsoft.com/v1.0'


def segment(value):
    return quote(str(value), safe='')


def site_address(value):
    url = urlsplit(value.strip())
    if url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.sharepoint.com') or url.username or url.password or url.port:
        raise ValueError('Escribe una URL https del sitio de SharePoint de CHC.')
    path = unquote(url.path).rstrip('/')
    pieces = path.split('/')
    if len(pieces) >= 3 and pieces[1] in ('sites', 'teams'):
        path = '/'.join(pieces[:3])
    elif path:
        raise ValueError('Usa la URL del sitio, por ejemplo https://chc.sharepoint.com/sites/Reportes.')
    return url.hostname, path


class GraphError(RuntimeError):
    pass


class GraphClient:
    def __init__(self, account, session=None, sleep=time.sleep):
        if session is None:
            import requests
            session = requests.Session()
        self.account, self.session, self.sleep = account, session, sleep

    def request(self, method, path, **kwargs):
        url = GRAPH + path if path.startswith('/') else path
        if not url.startswith(GRAPH + '/'):
            raise ValueError('Destino Microsoft Graph inválido.')
        headers = {'Authorization': 'Bearer ' + self.account.token(), **kwargs.pop('headers', {})}
        for attempt in range(3):
            response = self.session.request(method, url, headers=headers, timeout=30, allow_redirects=False, **kwargs)
            if response.status_code == 401:
                raise AuthenticationRequired('La sesión necesita renovarse. Vuelve a conectar la cuenta CHC.')
            if response.status_code in (429, 503, 504) and attempt < 2:
                try:
                    delay = float(response.headers.get('Retry-After', 2))
                except ValueError:
                    delay = 2
                self.sleep(min(30, max(1, delay)))
                continue
            if response.status_code == 403:
                raise GraphError('Sin acceso a este sitio. Un administrador debe autorizarlo para CHC Workbench y tu cuenta debe poder escribir allí.')
            if response.status_code in (409, 412):
                raise GraphError('El archivo ya existe o cambió en SharePoint. Se conservó la copia online; revisa el destino antes de reintentar.')
            if response.status_code >= 300:
                raise GraphError(f'SharePoint no completó la operación (HTTP {response.status_code}). El archivo local se conserva.')
            return response.json() if response.content else {}
        raise GraphError('SharePoint sigue ocupado. La publicación queda pendiente.')

    def collection(self, path):
        values = []
        while path:
            data = self.request('GET', path)
            values.extend(data.get('value', []))
            path = data.get('@odata.nextLink')
        return values

    def site(self, url):
        host, path = site_address(url)
        site = self.request('GET', '/sites/' + host + (':' + quote(path, safe='/') if path else ''))
        drives = self.collection('/sites/' + segment(site['id']) + '/drives')
        return {'site': site, 'drives': drives}

    def folders(self, drive, item='root'):
        base = '/drives/' + segment(drive) + ('/root' if item == 'root' else '/items/' + segment(item))
        current = self.request('GET', base)
        if 'folder' not in current:
            raise ValueError('El destino debe ser una carpeta.')
        return {'folder': current, 'folders': [v for v in self.collection(base + '/children') if 'folder' in v]}

    def ensure_folder(self, drive, parent, name):
        base = '/drives/' + segment(drive) + '/items/' + segment(parent)
        for item in self.collection(base + '/children'):
            if item['name'].casefold() == name.casefold():
                if 'folder' not in item:
                    raise GraphError('El nombre del lote ya corresponde a un archivo online.')
                return item['id']
        data = self.request('POST', base + '/children', json={'name': name, 'folder': {}, '@microsoft.graph.conflictBehavior': 'fail'})
        return data['id']

    def upload(self, drive, parent, path, previous=None):
        path = Path(path)
        base = '/drives/' + segment(drive)
        headers = {}
        if previous:
            current = self.request('GET',base + '/items/' + segment(previous['itemId']))
            if current.get('eTag') != previous['etag'] or current.get('parentReference',{}).get('id') != parent or current.get('name') != path.name:
                raise GraphError('El archivo online fue modificado o movido fuera de la app. Se conservó; revisa su destino.')
            endpoint = base + '/items/' + segment(previous['itemId']) + '/createUploadSession'
            headers['If-Match'] = previous['etag']
        else:
            endpoint = base + '/items/' + segment(parent) + ':/' + segment(path.name) + ':/createUploadSession'
        data = self.request('POST', endpoint, headers=headers,
            json={'item': {'@microsoft.graph.conflictBehavior': 'replace' if previous else 'fail', 'name': path.name}})
        upload_url = data['uploadUrl']
        address = urlsplit(upload_url)
        if address.scheme != 'https' or address.username or address.password or not address.hostname or not (
                address.hostname.endswith('.sharepoint.com') or address.hostname.endswith('.up.1drv.com')):
            raise GraphError('SharePoint devolvió un destino de carga inesperado.')
        total, offset = path.stat().st_size, 0
        if not total:
            raise GraphError('El CSV local está vacío; se conservó el resultado online.')
        with path.open('rb') as stream:
            while offset < total:
                stream.seek(offset)
                chunk = stream.read(10 * 320 * 1024)
                # uploadUrl ya contiene autorización; nunca adjuntar el token OAuth.
                response = self.session.put(upload_url, data=chunk, timeout=60, allow_redirects=False,
                    headers={'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {offset}-{offset+len(chunk)-1}/{total}'})
                if response.status_code in (200, 201):
                    return response.json()
                if response.status_code != 202:
                    raise GraphError(f'La subida quedó pendiente (HTTP {response.status_code}). Reintenta la publicación.')
                ranges = response.json().get('nextExpectedRanges', [])
                next_offset = int(ranges[0].split('-')[0]) if ranges else offset + len(chunk)
                if next_offset <= offset or next_offset > total:
                    raise GraphError('SharePoint no confirmó el avance de la carga.')
                offset = next_offset
        raise GraphError('SharePoint no confirmó el archivo completo; queda pendiente.')
