"""Portal HTTP local para comprobar formulario, protocolos y SQLite sin TICA."""
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit


def inputs(state, rows):
    return ''.join('<input name="'+key+'" value="'+html.escape(json.dumps(value),quote=True)+'">'
                   for key,value in [('GXState',state),('Grid1ContainerDataV',rows)])


class FixturePortal:
    def __init__(self, mode, spec):
        self.mode, self.spec, self.requests = mode, spec, []
        portal = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self): self.reply(False)
            def do_POST(self): self.reply(True)
            def reply(self, post):
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                body = self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()
                portal.requests.append((parsed.path,post))
                data, content = portal.response(parsed.path,query,post,parse_qs(body))
                data = data.encode()
                self.send_response(200)
                self.send_header('Content-Type',content+'; charset=utf-8')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):
                    pass
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/hcicgmic.aspx'

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def main(self):
        from conocimientos import IDENTITY
        code = {'maritimo':'1','aereo':'4','terrestre':'7'}[self.mode]
        fields = IDENTITY+['vVCONS','vVDUAS','vVMOVSTK','vVCONTE']
        grid = {'GridName':'Grid1','Count':3}
        rows = []
        for n in range(1,4):
            parts = [code,'0',f"{self.spec['year']}000{n}",'P027',f"01/{self.spec['month']:02d}/{str(self.spec['year'])[-2:]}"]
            mid = '-'.join(parts)
            links = [endpoint+'?'+urlencode({'id':mid,'n':n}) for endpoint in
                     ['hcgcons.aspx','hcgduama.aspx','hcgmovi.aspx','hcgkonte.aspx']]
            row = parts+links
            rows.append(row)
            grid[str(n-1)] = {'Props':[[field+'_0001',value] for field,value in zip(fields,row)]}
        return grid, rows

    def response(self,path,query,post,form):
        from conocimientos import IDENTITY, FIELDS
        from tablas_manifiesto import HEADERS, FIELDS as TABLE_FIELDS
        if path=='/hcicgmic.aspx':
            grid,rows = self.main()
            if post:
                return json.dumps({'gxGrids':[grid],'gxHiddens':{'Grid1ContainerDataV':json.dumps(rows)}}),'application/json'
            headers = ['Trans.','Ing Sal','Manifiesto','Cod Ubicacion','Fecha']
            table = '<table id="Grid1ContainerTbl"><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'
            table += ''.join('<tr>'+''.join('<td>'+html.escape(value)+'</td>' for value in row[:5])+'</tr>' for row in rows)
            table += '</tbody></table>'
            return ('<select id="vVTRANS"><option value="1">Mar</option><option value="4">Aire</option><option value="7">Tierra</option></select>'
                    '<input id="vVCGNROMIC"><input id="vVFCH1"><input id="vVFCHF">'
                    '<button name="BTN_ENTER" onclick="fetch(location.href,{method:\'POST\',body:\'query\'})">Consultar</button>'+table),'text/html'
        mid = query['id'][0]
        n = int(query['n'][0])
        if n==3 and os.environ.get('CHC_MANIFEST_FIXTURE_SLOW'):
            time.sleep(float(os.environ['CHC_MANIFEST_FIXTURE_SLOW']))
        state = dict(zip(IDENTITY,mid.split('-')))
        if path=='/hcgcons.aspx':
            if n==3:
                return inputs(state,[]),'text/html'  # Esquema incompleto, nunca vacío válido.
            offset = 0
            if post:
                offset = int(json.loads(form['GXState'][0]).get('GRID1_nFirstRecordOnPage','0'))+2
            values = [] if n==2 else ([[str(offset+1),'00001234567890123456789' if offset==0 else '000000000000000000003','N','','HWB','00123','Empresa','188AJU','','','840MIA','','CER','']]
                + ([['2','000000000000000000002','S','','HWB','00123','Empresa','188AJU','','','840MIA','','CER','']] if offset==0 else []))
            grid = {'Count':len(values)}
            if values:
                grid['0'] = {'Props':[[f+'_0001'] for f in FIELDS]}
            state.update(Grid1ContainerData=json.dumps(grid), nRC_Grid1=str(len(values)),
                GRID1_nFirstRecordOnPage=str(offset),GRID1_nEOF='1' if n==2 or offset else '0')
            return inputs(state,values),'text/html'
        if path in ('/hcgduama.aspx','/hcgmovi.aspx'):
            flow = 'duas' if 'duama' in path else 'movimientos'
            if n==3 and flow=='duas':
                return '<form action="/frmAmbiente.aspx?aspxerrorpath=/Tica/hcgduama.aspx"></form>','text/html'
            values = [] if n==2 else [['0001','002']+['']*(len(HEADERS[flow])-2)]
            grid = {'Count':len(values),'Columns':[{} for _ in HEADERS[flow]]}
            if values:
                grid['0'] = {'Props':[[f+'_0001'] for f in TABLE_FIELDS[flow]]}
            if n==3:
                grid['Count'] = 99
            state.update(Grid1ContainerData=json.dumps(grid),nRC_Grid1=str(len(values)))
            return inputs(state,values),'text/html'
        if path=='/hcgkonte.aspx':
            spans = ''.join(f'<span id="span_{key}">{value}</span>' for key,value in state.items())
            count = 0 if n==2 else 1
            if post:
                return json.dumps({'gxGrids':[{'GridName':'Grid1','Count':count}]}),'application/json'
            cells = ['<a href="hcgkonli.aspx?'+html.escape(urlencode({'id':mid,'n':n}),quote=True)+'">Mercancías</a>']+['0001','LL','40','100','001','ACT','L','000001']+['']*13
            grid = '<table id="Grid1ContainerTbl"><tbody>'+(('<tr id="Grid1ContainerRow_0001">'+''.join('<td>'+v+'</td>' for v in cells)+'</tr>') if count else '')+'</tbody></table>'
            return spans+'<select id="vCGLLENVAC"><option value="1">Llenos</option></select><button name="BTN_ENTER1" onclick="fetch(location.href,{method:\'POST\'})">Filtrar</button><span id="span_vTOTALCONTENEDORES">'+str(count)+'</span>'+grid,'text/html'
        if path=='/hcgkonli.aspx':
            values = [['00001234567890123456789','001','001','0001','0002','CA','ACT']]
            if n==3:
                values = [['INCOMPLETA']]
            state.update(Grid1ContainerData=json.dumps({'Count':len(values)}),GRID1_nEOF='1')
            return inputs(state,values),'text/html'
        return '<html>Ruta de prueba desconocida</html>','text/html'


def configure_scraper(scraper, flow, mode, spec, portal=None):
    portal = portal or FixturePortal(mode,spec)
    scraper.URL = portal.url
    scraper.fixture_portal = portal
    return portal
