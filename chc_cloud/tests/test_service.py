"""Publicación aislada: persistencia, cuenta, errores y protección de resultados."""
import json
from pathlib import Path
import tempfile
import unittest

from chc_cloud.service import CloudService
from chc_cloud.graph import GraphClient, GraphError, site_address, places_address


class Account:
    info = {'username':'prueba@chc.example','home_account_id':'one'}
    def current(self): return self.info
    def connect(self): self.info={'username':'prueba@chc.example','home_account_id':'one'}
    def disconnect(self): self.info=None
    def token(self): return 'test-only-token'


class Graph:
    def __init__(self): self.sent=[];self.fail=False
    def site(self,url): return {'site':{'id':'site'},'drives':[{'id':'drive','name':'Documentos'}]}
    def sites(self,host,query=''): return [{'id':'site','name':'Reportes','url':'https://'+host+'/sites/Reportes'}]
    def folders(self,drive,item): return {'folder':{'id':item,'name':item,'webUrl':'https://test.sharepoint.com/sites/reportes/'+item},'folders':[]}
    def ensure_folder(self,drive,parent,name): return 'monthly'
    def upload(self,drive,parent,path,previous):
        if self.fail:raise GraphError('Sin acceso; conserva el CSV.')
        self.sent.append((Path(path).name,Path(path).read_bytes(),previous))
        return {'id':'remote','eTag':f'tag{len(self.sent)}'}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'Talon_septiembre26.csv';self.source.write_bytes(b'Numero;Total\r\n001;123\r\n')
        self.account=Account();self.graph=Graph()
        self.service=CloudService(self.root/'cloud',{},self.account,self.graph)
        self.request={'target':'talon','path':str(self.source),'name':'septiembre26','owner':'table1'}
    def tearDown(self):self.service.db.close();self.temp.cleanup()
    def destination(self):
        self.service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
        self.service.save_destination('talon','drive','folder')
    def test_without_account_or_destination_keeps_local_work(self):
        self.account.disconnect();self.service.enqueue(self.request);self.service.sync()
        self.assertEqual(self.service.snapshot()['pending'],0)
        self.assertEqual(self.source.read_bytes(),b'Numero;Total\r\n001;123\r\n')
        self.assertFalse(self.graph.sent)
    def test_exact_csv_and_original_name_deduplicated_and_updated_with_etag(self):
        self.destination();self.service.enqueue(self.request);self.service.sync()
        self.assertEqual(self.graph.sent[0],(self.source.name,self.source.read_bytes(),None))
        self.service.enqueue(self.request);self.service.sync();self.assertEqual(len(self.graph.sent),1)
        self.source.write_bytes(b'Numero;Total\r\n001;123\r\n002;456\r\n')
        self.service.enqueue(self.request);self.service.sync()
        self.assertEqual(self.graph.sent[1][2]['itemId'],'remote');self.assertEqual(self.graph.sent[1][2]['etag'],'tag1')
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'synced')
    def test_failed_publication_survives_restart_and_explicit_retry(self):
        self.destination();self.service.enqueue(self.request);self.graph.fail=True;self.service.sync()
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'error')
        self.service.db.close();self.service=CloudService(self.root/'cloud',{},self.account,self.graph)
        self.graph.fail=False;self.service.execute({'command':'retry'})
        self.assertEqual(self.graph.sent[0][1],self.source.read_bytes());self.assertEqual(self.service.snapshot()['pending'],0)
    def test_disconnect_and_changed_account_cannot_upload_another_accounts_queue(self):
        self.destination();self.service.enqueue(self.request);self.account.disconnect();self.service.sync()
        self.account.info={'username':'otro@chc.example','home_account_id':'two'};self.service.sync()
        self.assertFalse(self.graph.sent)
        self.account.connect();self.service.sync();self.assertEqual(len(self.graph.sent),1)
    def test_other_lot_cannot_overwrite_same_cloud_name(self):
        self.destination();self.service.enqueue(self.request)
        with self.assertRaises(GraphError):self.service.enqueue({**self.request,'owner':'another-table'})
        self.service.sync();self.assertEqual(len(self.graph.sent),1)
    def test_removed_or_changed_destination_does_not_send_old_queue(self):
        self.destination();self.service.enqueue(self.request)
        self.service.execute({'command':'remove','key':'talon'})
        self.service.save_destination('talon','drive','different-folder')
        self.service.execute({'command':'retry'});self.assertFalse(self.graph.sent)
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'paused')
    def test_restart_recovers_uploading_without_losing_snapshot(self):
        self.destination();self.service.enqueue(self.request)
        with self.service.db:self.service.db.execute("UPDATE jobs SET state='uploading'")
        self.service.db.close();self.service=CloudService(self.root/'cloud',{},self.account,self.graph)
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'pending')
        self.service.sync();self.assertEqual(len(self.graph.sent),1)
    def test_only_csv_and_valid_folder_names(self):
        self.destination()
        for name in ('../other','bad/name','.'):
            with self.assertRaises(ValueError):self.service.enqueue({**self.request,'name':name})
        source=self.root/'secret.txt';source.write_text('not a result')
        with self.assertRaises(ValueError):self.service.enqueue({**self.request,'path':str(source)})

    def test_outbox_recovers_on_restart_and_failed_notice_remains_visible(self):
        self.destination()
        outbox=self.service.folder/'outbox';outbox.mkdir()
        notice=outbox/'notice.json';notice.write_text(json.dumps(self.request),encoding='utf-8')
        self.service.db.close();self.service=CloudService(self.root/'cloud',{},self.account,self.graph)
        self.service.execute({'command':'status'});self.assertFalse(notice.exists())
        self.service.sync();self.assertEqual(len(self.graph.sent),1)
        notice.write_text(json.dumps({**self.request,'owner':'another-lot'}),encoding='utf-8')
        state=self.service.execute({'command':'status'})['snapshot']
        self.assertTrue(notice.exists());self.assertTrue(state['queueError']);self.assertEqual(state['pending'],1)

    def test_places_opens_site_catalog_and_library_url_opens_real_site(self):
        portal='https://test.sharepoint.com/_layouts/15/sharepoint.aspx/onedrive/places'
        result=self.service.execute({'command':'site','url':portal})
        self.assertTrue(result['browse']['places']);self.assertEqual(result['browse']['sites'][0]['name'],'Reportes')
        self.assertIsNone(self.service.browse_site)
        result=self.service.execute({'command':'site','url':result['browse']['sites'][0]['url']})
        self.assertEqual(result['browse']['drives'][0]['name'],'Documentos')
        self.assertEqual(len(json.loads(self.service.sites_path.read_text(encoding='utf-8'))),1)


class Response:
    def __init__(self,code,data):self.status_code=code;self.data=data;self.content=b'x';self.headers={}
    def json(self):return self.data


class Transport:
    def __init__(self):self.calls=[];self.puts=[];self.response=Response(200,{'uploadUrl':'https://test.sharepoint.com/upload?secret=test'})
    def request(self,method,url,**kw):self.calls.append((method,url,kw));return self.response
    def put(self,url,**kw):self.puts.append((url,kw));return Response(201,{'id':'item','eTag':'etag'})


class GraphTests(unittest.TestCase):
    def test_upload_session_does_not_forward_oauth_token_and_refuses_first_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'datos.csv';path.write_bytes(b'abc')
            transport=Transport();graph=GraphClient(Account(),transport,sleep=lambda _:None)
            result=graph.upload('drive','folder',path)
            self.assertEqual(result['id'],'item')
            self.assertEqual(transport.calls[0][2]['json']['item']['@microsoft.graph.conflictBehavior'],'fail')
            self.assertNotIn('Authorization',transport.puts[0][1]['headers'])
            self.assertEqual(transport.puts[0][1]['headers']['Content-Range'],'bytes 0-2/3')
    def test_graph_next_link_and_site_url_validation(self):
        graph=GraphClient(Account(),Transport())
        with self.assertRaises(ValueError):graph.request('GET','https://evil.example/steal')
        for value in ('http://test.sharepoint.com/sites/a','https://test.sharepoint.com.evil.example/sites/a','https://user@test.sharepoint.com/sites/a'):
            with self.assertRaises(ValueError):site_address(value)
        self.assertEqual(site_address('https://test.sharepoint.com/sites/Reportes/Shared%20Documents/Forms/AllItems.aspx'),('test.sharepoint.com','/sites/Reportes'))
    def test_external_modification_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'datos.csv';path.write_bytes(b'abc')
            transport=Transport();transport.response=Response(200,{'eTag':'changed','name':'datos.csv','parentReference':{'id':'folder'}})
            with self.assertRaises(GraphError):GraphClient(Account(),transport).upload('drive','folder',path,{'itemId':'item','etag':'old'})
            self.assertFalse(transport.puts);self.assertEqual(len(transport.calls),1)

    def test_real_sharepoint_library_links_and_places_are_distinct(self):
        host='chcconsultorescr.sharepoint.com'
        value=f'https://{host}/_layouts/15/FileBrowser.aspx?view=0&id=%2Fsites%2FAutomatizacinTIC%2FDocumentos%20compartidos&listurl=%2Fsites%2FAutomatizacinTIC%2FDocumentos%20compartidos'
        self.assertEqual(site_address(value),(host,'/sites/AutomatizacinTIC'))
        self.assertEqual(places_address(f'https://{host}/_layouts/15/sharepoint.aspx/onedrive/places'),host)
        self.assertIsNone(places_address(value))
        with self.assertRaises(ValueError):site_address(f'https://{host}/_layouts/15/FileBrowser.aspx?id=https://evil.example/steal')

    def test_sites_search_uses_delegation_and_filters_tenant_hostname(self):
        transport=Transport()
        transport.response=Response(200,{'value':[
            {'id':'b','displayName':'TIC','webUrl':'https://test.sharepoint.com/sites/TIC'},
            {'id':'a','displayName':'Aduanas','webUrl':'https://test.sharepoint.com/sites/Aduanas'},
            {'id':'c','displayName':'Otro directorio','webUrl':'https://other.sharepoint.com/sites/Otro'}]})
        values=GraphClient(Account(),transport).sites('test.sharepoint.com','TIC documentos')
        self.assertEqual([v['name'] for v in values],['Aduanas','TIC'])
        self.assertTrue(transport.calls[0][1].endswith('/sites?search=TIC%20documentos'))


if __name__=='__main__':unittest.main()
