"""Perfil opcional, aislamiento de cuenta y navegación; sin servicios reales."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from chc_cloud.auth import AuthenticationRequired,CloudAccount
from chc_cloud.graph import GraphClient,GraphError
from chc_cloud.profile import ProfileCache
from chc_cloud.service import CloudService
from chc_cloud.tests.test_service import Account,Graph

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH3sAAAAASUVORK5CYII=')


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.account={'home_account_id':'one','username':'one@chc.example'}
        self.graph=Mock()
        self.graph.profile.return_value=dict(displayName='Persona Uno',mail='one@chc.example')
        self.graph.photo.return_value=(PNG,'image/png')

    def test_photo_cache_survives_restart_without_query_and_is_cleared_on_disconnect(self):
        cache=ProfileCache(self.root,self.graph);cache.refresh(self.account)
        self.assertEqual(cache.get(self.account)['displayName'],'Persona Uno')
        photo=next(self.root.glob('profile-*.png'));self.assertEqual(photo.read_bytes(),PNG)
        restarted=ProfileCache(self.root,self.graph);restarted.refresh(self.account)
        self.assertEqual(self.graph.profile.call_count,1)
        self.assertEqual(restarted.get(self.account)['photoUrl'],photo.as_uri())
        restarted.clear()
        self.assertFalse(photo.exists());self.assertFalse((self.root/'profile.json').exists())
        self.assertEqual(restarted.get(None),{})

    def test_switch_account_and_missing_permission_never_show_other_person_photo(self):
        cache=ProfileCache(self.root,self.graph);cache.refresh(self.account)
        other={'home_account_id':'two','username':'two@chc.example'}
        self.assertEqual(cache.get(other)['photoUrl'],'')
        self.graph.profile.side_effect=AuthenticationRequired('Renueva el permiso de perfil.')
        cache.refresh(other)
        self.assertEqual(cache.get(other)['displayName'],'two@chc.example')
        self.assertEqual(cache.get(other)['photoUrl'],'')
        self.assertIn('Renueva',cache.warning)
        self.assertFalse(list(self.root.glob('profile-*.png')))
        cache.refresh(other);self.assertEqual(self.graph.profile.call_count,2)

    def test_missing_photo_uses_profile_and_transient_failure_preserves_cached_photo(self):
        cache=ProfileCache(self.root,self.graph);cache.refresh(self.account)
        url=cache.get(self.account)['photoUrl']
        self.graph.photo.side_effect=TimeoutError('Prueba sin red')
        cache.refresh(self.account,force=True)
        self.assertEqual(cache.get(self.account)['photoUrl'],url)
        self.graph.photo.side_effect=None;self.graph.photo.return_value=None
        cache.refresh(self.account,force=True)
        self.assertEqual(cache.get(self.account)['photoUrl'],'')
        self.assertEqual(cache.get(self.account)['displayName'],'Persona Uno')

    def test_legacy_file_token_does_not_require_profile_consent(self):
        account=CloudAccount(self.root,dict(scopes=['Sites.Read.All','Files.ReadWrite.All','User.Read']))
        client=Mock();client.get_accounts.return_value=[self.account]
        client.acquire_token_silent.return_value={'access_token':'test-only'}
        account.app=client
        account.token();self.assertEqual(client.acquire_token_silent.call_args.args[0],['Sites.Read.All','Files.ReadWrite.All'])
        account.token(['User.Read']);self.assertEqual(client.acquire_token_silent.call_args.args[0],['User.Read'])
        client.acquire_token_silent.return_value={}
        with self.assertRaises(AuthenticationRequired):account.token(['User.Read'])

    def test_graph_photo_handles_absence_permissions_mime_and_redirects(self):
        response=Mock(status_code=200,content=PNG,headers={'Content-Type':'image/png'})
        transport=Mock();transport.request.return_value=response
        account=Mock();account.token.return_value='test-only'
        graph=GraphClient(account,transport)
        self.assertEqual(graph.photo(),(PNG,'image/png'))
        account.token.assert_called_with(['User.Read'])
        self.assertFalse(transport.request.call_args.kwargs['allow_redirects'])
        response.status_code=404;self.assertIsNone(graph.photo())
        response.status_code=403
        with self.assertRaises(GraphError):graph.photo()
        response.status_code=200;response.headers={'Content-Type':'text/html'}
        with self.assertRaises(GraphError):graph.photo()

    def test_profile_network_error_does_not_block_status_or_modify_queue(self):
        account=Account();account.info=dict(self.account)
        graph=Graph();graph.profile=Mock(side_effect=TimeoutError())
        service=CloudService(self.root/'cloud',dict(scopes=['User.Read']),account,graph,monthly=lambda:{'rows':[]})
        self.addCleanup(service.db.close)
        snapshot=service.execute({'command':'status'})['snapshot']
        self.assertTrue(snapshot['connected']);self.assertEqual(snapshot['pending'],0)
        self.assertIn('perfil',snapshot['profileWarning'])
        self.assertEqual(graph.sent,[])

    def test_folder_listing_keeps_files_metadata_and_follows_graph_pagination(self):
        account=Mock();account.token.return_value='test-only'
        responses=[]
        for data in ({'id':'folder','folder':{},'name':'Resultados'},
                     {'value':[{'id':'csv','name':'BLS.CSV','file':{},'size':2048,'lastModifiedDateTime':'2026-10-18T15:30:00Z'}],
                      '@odata.nextLink':'https://graph.microsoft.com/v1.0/next'},
                     {'value':[{'id':'nested','name':'BLS','folder':{}}]}):
            response=Mock(status_code=200,content=b'json');response.json.return_value=data;responses.append(response)
        transport=Mock();transport.request.side_effect=responses
        result=GraphClient(account,transport).folders('drive','folder')
        self.assertEqual([item['name'] for item in result['folders']],['BLS'])
        self.assertEqual(result['files'][0]['size'],2048)
        self.assertEqual(len(transport.request.call_args_list),3)

    def test_destination_browsing_and_explicit_creation_are_scoped_and_do_not_upload(self):
        account=Account();account.info=dict(self.account)
        graph=Graph();graph.create_folder=Mock(return_value={'id':'created'})
        service=CloudService(self.root/'cloud',{},account,graph,monthly=lambda:{'rows':[]})
        self.addCleanup(service.db.close)
        service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
        service.execute({'command':'save','drive':'drive','item':'folder'})
        result=service.execute({'command':'destination_contents'})
        self.assertEqual(result['browse']['folder']['id'],'folder')
        for name in ('../fuera','carpeta.',''):
            with self.assertRaises(ValueError):service.execute(dict(command='create_folder',drive='drive',item='folder',name=name))
        with self.assertRaises(ValueError):service.execute(dict(command='create_folder',drive='other',item='folder',name='Nueva'))
        graph.create_folder.assert_not_called()
        service.execute(dict(command='create_folder',drive='drive',item='folder',name='Nueva'))
        graph.create_folder.assert_called_once_with('drive','folder','Nueva')
        self.assertFalse(graph.sent)
        account.info={'home_account_id':'two','username':'two@chc.example'}
        with self.assertRaises(ValueError):service.execute({'command':'destination_contents'})


if __name__=='__main__':unittest.main()
