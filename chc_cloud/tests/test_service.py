"""Publicación aislada: persistencia, cuenta, errores y protección de resultados."""
import json
from pathlib import Path
import tempfile
import unittest

from chc_cloud.service import CloudService,bot_folders
from chc_cloud.graph import GraphClient, GraphError, site_address, places_address
from chc_runtime import output_layout


class Account:
    info = {'username':'prueba@chc.example','home_account_id':'one'}
    def current(self): return self.info
    def connect(self): self.info={'username':'prueba@chc.example','home_account_id':'one'}
    def disconnect(self): self.info=None
    def token(self): return 'test-only-token'


class Graph:
    def __init__(self): self.sent=[];self.fail=False;self.created=[]
    def site(self,url): return {'site':{'id':'site'},'drives':[{'id':'drive','name':'Documentos'}]}
    def sites(self,host,query=''): return [{'id':'site','name':'Reportes','url':'https://'+host+'/sites/Reportes'}]
    def folders(self,drive,item): return {'folder':{'id':item,'name':item,'webUrl':'https://test.sharepoint.com/sites/reportes/'+item},'folders':[]}
    def ensure_folder(self,drive,parent,name):
        self.created.append((drive,parent,name))
        return parent+'/'+name
    def upload(self,drive,parent,path,previous):
        if self.fail:raise GraphError('Sin acceso; conserva el CSV.')
        self.sent.append((Path(path).name,Path(path).read_bytes(),previous))
        return {'id':'remote','eTag':f'tag{len(self.sent)}'}


class ServiceTests(unittest.TestCase):
    def monthly(self):
        return {'rows':[{'period':'2026-09','label':'Septiembre 2026',
                        'cells':[{'module':m,'status':'completed'} for m in output_layout.BOTS],
                        'procedures':[{'status':'completed'} for _ in output_layout.FLOWS]}]}
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'Talon_septiembre26.csv';self.source.write_bytes(b'Numero;Total\r\n001;123\r\n')
        self.account=Account();self.graph=Graph()
        self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)
        self.request={'target':'talon','path':str(self.source),'name':'septiembre26','owner':'table1'}
    def tearDown(self):self.service.db.close();self.temp.cleanup()
    def destination(self):
        self.service.execute({'command':'site','url':'https://test.sharepoint.com/sites/reportes'})
        self.service.save_destination('drive','folder')
    def test_without_account_or_destination_keeps_local_work(self):
        self.account.disconnect();self.service.enqueue(self.request);self.service.sync()
        self.assertEqual(self.service.snapshot()['pending'],0)
        self.assertEqual(self.source.read_bytes(),b'Numero;Total\r\n001;123\r\n')
        self.assertFalse(self.graph.sent)
    def test_exact_csv_and_original_name_deduplicated_and_updated_with_etag(self):
        self.destination();self.service.enqueue(self.request);self.service.sync()
        self.assertEqual(self.graph.sent[0],('TALON_SEPTIEMBRE_2026.CSV',self.source.read_bytes(),None))
        self.service.enqueue(self.request);self.service.sync();self.assertEqual(len(self.graph.sent),1)
        self.source.write_bytes(b'Numero;Total\r\n001;123\r\n002;456\r\n')
        self.service.enqueue(self.request);self.service.sync()
        self.assertEqual(self.graph.sent[1][2]['itemId'],'remote');self.assertEqual(self.graph.sent[1][2]['etag'],'tag1')
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'synced')
    def test_failed_publication_survives_restart_and_explicit_retry(self):
        self.destination();self.service.enqueue(self.request);self.graph.fail=True;self.service.sync()
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'error')
        self.service.db.close();self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)
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
        self.service.execute({'command':'remove'})
        self.service.save_destination('drive','different-folder')
        self.service.execute({'command':'retry'});self.assertFalse(self.graph.sent)
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'paused')
    def test_restart_recovers_uploading_without_losing_snapshot(self):
        self.destination();self.service.enqueue(self.request)
        with self.service.db:self.service.db.execute("UPDATE jobs SET state='uploading'")
        self.service.db.close();self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)
        self.assertEqual(self.service.snapshot()['tasks'][0]['state'],'pending')
        self.service.sync();self.assertEqual(len(self.graph.sent),1)
    def test_only_csv_and_valid_folder_names(self):
        self.destination()
        for name in ('../other','bad/name','.'):
            with self.assertRaises(ValueError):self.service.enqueue({**self.request,'name':name})
        source=self.root/'secret.txt';source.write_text('not a result')
        with self.assertRaises(ValueError):self.service.enqueue({**self.request,'path':str(source)})

    def test_old_automatic_outbox_is_not_uploaded(self):
        self.destination()
        outbox=self.service.folder/'outbox';outbox.mkdir()
        notice=outbox/'notice.json';notice.write_text(json.dumps(self.request),encoding='utf-8')
        self.service.db.close();self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)
        self.service.execute({'command':'status'});self.assertTrue(notice.exists())
        self.assertFalse(self.graph.sent);self.assertEqual(self.service.snapshot()['pending'],0)

    def test_places_opens_site_catalog_and_library_url_opens_real_site(self):
        portal='https://test.sharepoint.com/_layouts/15/sharepoint.aspx/onedrive/places'
        result=self.service.execute({'command':'site','url':portal})
        self.assertTrue(result['browse']['places']);self.assertEqual(result['browse']['sites'][0]['name'],'Reportes')
        self.assertIsNone(self.service.browse_site)
        result=self.service.execute({'command':'site','url':result['browse']['sites'][0]['url']})
        self.assertEqual(result['browse']['drives'][0]['name'],'Documentos')
        self.assertEqual(len(json.loads(self.service.sites_path.read_text(encoding='utf-8'))),1)

    def test_one_destination_creates_bot_and_month_folders_for_every_module(self):
        self.destination()
        targets=['detalles','duas_transito','talon','xmovimientos','bls']+['manifiestos:'+v for v in ('tabla','conocimientos','duas','movimientos','contenedores')]
        for target in targets:self.service.enqueue({**self.request,'target':target,'owner':target+':one'})
        self.service.sync()
        self.assertEqual(len(self.graph.sent),10)
        for target in targets:
            path='folder'
            for name in bot_folders(target)+['SEPTIEMBRE_2026']:
                self.assertIn(('drive',path,name),self.graph.created)
                path+='/'+name
        self.assertEqual(self.service.snapshot()['destination']['folderId'],'folder')

    def test_legacy_per_bot_configuration_is_preserved_and_requires_common_folder(self):
        self.service.db.close()
        config=self.root/'cloud/destinations.json'
        legacy={'talon':{'folderId':'old','driveId':'drive','accountId':'one'}}
        config.write_text(json.dumps(legacy),encoding='utf-8')
        self.service=CloudService(self.root/'cloud',{},self.account,self.graph,monthly=self.monthly)
        self.assertFalse(self.service.destination);self.assertTrue(self.service.snapshot()['needsFolderSelection'])
        self.destination()
        self.assertEqual(json.loads((self.root/'cloud/destinations_legacy.json').read_text(encoding='utf-8')),legacy)
        self.assertEqual(json.loads(config.read_text(encoding='utf-8'))['version'],2)

    def test_manual_month_action_is_required_and_incomplete_month_is_rejected(self):
        self.destination()
        self.service.execute({'command':'local_root','path':str(self.root/'RESULTADOS')})
        spec=output_layout.specification('talon','2026-09')
        output_layout.publish(self.source,self.root/'RESULTADOS',spec,'table1',self.service.exports_registry)
        self.service.execute({'command':'status'})
        self.assertFalse(self.graph.sent)
        self.assertEqual(self.service.snapshot()['months'][0]['period'],'2026-09')
        self.service.execute({'command':'upload_month','month':'2026-09'})
        self.assertEqual(len(self.graph.sent),1)
        self.service.monthly_reader=lambda:{'rows':[]}
        with self.assertRaises(ValueError):self.service.execute({'command':'upload_month','month':'2026-09'})
        with self.assertRaises(ValueError):self.service.execute({'command':'sync'})

    def test_current_month_up_to_date_is_eligible_and_other_pending_months_are_not_sent(self):
        self.destination()
        self.service.execute({'command':'local_root','path':str(self.root/'RESULTADOS')})
        data=self.monthly()
        data['rows'].append({'period':'2026-10','label':'Octubre 2026',
                            'cells':[{'module':'talon','status':'up_to_date'}],'procedures':[]})
        self.service.monthly_reader=lambda:data
        self.service.enqueue(self.request)
        spec=output_layout.specification('talon','2026-10')
        output_layout.publish(self.source,self.root/'RESULTADOS',spec,'octubre',self.service.exports_registry)
        self.service.execute({'command':'upload_month','month':'2026-10'})
        self.assertEqual([item[0] for item in self.graph.sent],['TALON_OCTUBRE_2026.CSV'])
        self.assertEqual(self.service.snapshot()['pending'],1)

    def test_cumulative_export_retires_partial_from_upload_without_removing_file(self):
        self.destination()
        base=self.root/'RESULTADOS'
        self.service.execute({'command':'local_root','path':str(base)})
        target='manifiestos:conocimientos'
        partial=output_layout.specification(target,'2026-09','maritimo','DEL_01_AL_15')
        old=output_layout.publish(self.source,base,partial,'month',self.service.exports_registry)
        self.service.enqueue({'target':target,'path':old['path'],'name':'2026-09','owner':'month','spec':partial})
        complete=output_layout.specification(target,'2026-09','maritimo')
        output_layout.publish(self.source,base,complete,'month',self.service.exports_registry,supersede=True)
        self.assertEqual(Path(old['path']).read_bytes(),self.source.read_bytes())
        self.service.upload_month('2026-09')
        self.assertEqual([item[0] for item in self.graph.sent],[complete['filename']])
        self.assertEqual(self.service.db.execute("SELECT state FROM jobs WHERE filename=?",(partial['filename'],)).fetchone()[0],'paused')


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
