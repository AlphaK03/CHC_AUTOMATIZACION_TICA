"""Cliente público OAuth2; MSAL administra PKCE y la renovación de tokens."""
from pathlib import Path
import sys


class AuthenticationRequired(RuntimeError):
    pass


class CloudAccount:
    def __init__(self, folder, settings):
        self.folder, self.settings = Path(folder), settings
        self.app = None

    def client(self):
        if self.app is None:
            if sys.platform != 'win32':
                raise RuntimeError('La conexión requiere la caché protegida de Windows.')
            import msal
            from msal_extensions import FilePersistenceWithDataProtection, PersistedTokenCache
            cache_path = self.folder / 'tokens.dpapi'
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache = PersistedTokenCache(FilePersistenceWithDataProtection(str(cache_path)))
            self.app = msal.PublicClientApplication(self.settings['clientId'],
                authority='https://login.microsoftonline.com/' + self.settings['tenantId'],
                token_cache=cache, timeout=20, app_name='CHC Workbench', enable_pii_log=False)
        return self.app

    def current(self):
        accounts = self.client().get_accounts()
        return accounts[0] if len(accounts) == 1 else None

    def token(self):
        account = self.current()
        result = self.client().acquire_token_silent(self.settings['scopes'], account=account) if account else None
        if not result or 'access_token' not in result:
            if account and 'Sites.Read.All' in self.settings['scopes']:
                raise AuthenticationRequired('Renueva la conexión con Cambiar cuenta para conceder la lectura de SharePoint. Si Microsoft solicita aprobación, debe concederla un administrador de CHC.')
            raise AuthenticationRequired('Conecta tu cuenta CHC para enviar los pendientes a SharePoint.')
        return result['access_token']

    def connect(self):
        result = self.client().acquire_token_interactive(self.settings['scopes'],
            prompt='select_account', timeout=180)
        if 'access_token' not in result:
            raise AuthenticationRequired('No se completó la conexión. Si Microsoft solicita aprobación administrativa, un administrador de CHC debe aprobar el permiso antes de volver a conectar.')
        claims = result.get('id_token_claims', {})
        if claims.get('tid', '').lower() != self.settings['tenantId'].lower():
            self.disconnect()
            raise AuthenticationRequired('La cuenta debe pertenecer al directorio de CHC.')
        selected = claims.get('preferred_username', '')
        for account in self.client().get_accounts():
            if account.get('username', '').lower() != selected.lower():
                self.client().remove_account(account)
        return self.current()

    def disconnect(self):
        for account in self.client().get_accounts():
            self.client().remove_account(account)
