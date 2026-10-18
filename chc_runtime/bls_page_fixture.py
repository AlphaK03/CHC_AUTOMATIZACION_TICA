"""Portal local de BLs con siete líneas, cuatro páginas y fallos controlados."""
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlencode, urlsplit


class BLSPagePortal:
    def __init__(self, fail_offset=None, changed_offset=None, repeated_last=False, empty=False, search_get=False,
                 manifest='1-0-00001-A01-01/09/26', sequences=None):
        self.fail_offset, self.changed_offset = fail_offset, changed_offset
        self.repeated_last, self.empty = repeated_last, empty
        self.search_get = search_get
        self.manifest = manifest
        self.sequences = sequences or {}
        self.offsets, self.searches = [], []
        portal = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self): self.reply(False)
            def do_POST(self): self.reply(True)
            def reply(self,post):
                path = urlsplit(self.path)
                form = parse_qs(self.rfile.read(int(self.headers.get('Content-Length',0))).decode()) if post else {}
                status,kind,body = portal.response(path.path,parse_qs(path.query),form,post)
                data = body.encode()
                self.send_response(status)
                self.send_header('Content-Type',kind+'; charset=utf-8')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/Tica/hcgconocimientos.aspx'

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def response(self,path,query,form,post):
        if path.lower().endswith('/hcgconocimientos.aspx'):
            if not post and 'lookup' not in query:
                body = '''<script>window.gx={evt:{execEvt:()=>{}},O:{},ajax:{iscallactive:()=>false}};</script>
                    <input id="vVFCH1"><input id="vVFCHF"><input id="vCGNROCON">
                    <button name="BTN_ENTER1" onclick="fetch(location.href,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({vVFCH1:document.getElementById('vVFCH1').value,vVFCHF:document.getElementById('vVFCHF').value,vCGNROCON:document.getElementById('vCGNROCON').value,GXState:JSON.stringify({_EventName:'EENTER.'})})})">Buscar</button>
                    <table id="Grid2ContainerTbl"></table>'''
                if self.search_get:
                    body=body.replace('<input id="vCGNROCON">', '''<input id="vCGNROCON" onblur="window.__getPending=true;fetch(location.pathname+'?lookup=1&amp;bl='+encodeURIComponent(this.value)+'&amp;from='+encodeURIComponent(document.getElementById('vVFCH1').value)+'&amp;to='+encodeURIComponent(document.getElementById('vVFCHF').value)).then(()=>window.__getPending=false)">''')
                    body=body.replace('onclick="fetch(', 'onclick="if(window.__getPending)return;fetch(')
                return 200,'text/html',body
            bl = form['vCGNROCON'][0] if post else query['bl'][0]
            self.searches.append(bl)
            mid = getattr(self, 'manifest', '1-0-00001-A01-01/09/26')
            sequence = getattr(self,'sequences',{}).get(bl,'1')
            href = 'hcglineas.aspx?'+urlencode({'mid':mid,'bl':bl,'seq':sequence})
            row = mid.split('-')+['img','img',sequence,bl]+['']*15
            payload = {'gxHiddens':{'GXH_vCGNROCON':bl,'GXH_vVFCH1':form.get('vVFCH1',[''])[0],
                'GXH_vVFCHF':form.get('vVFCHF',[''])[0],'Grid2ContainerDataV':json.dumps([row]),'nRC_Grid2':'1'},
                'gxGrids':[{'GridName':'Grid2','Count':1,'0':{'Props':[['vVLIN_0001',href]]}}],
                'gxMessages':{'MAIN':[]}}
            if not post:
                from .bls_search import FIELDS
                row[5],row[6]=href,href
                payload={'gxValues':[{'CmpContext':'','IsMasterPage':'False','AV15vFch1':query['from'][0],
                    'AV16VfchF':query['to'][0],'AV5CGNroCon':bl}], 'gxMessages':{'MAIN':[]},
                    'gxHiddens':{'Grid2ContainerDataV':'[[]]'},
                    'gxGrids':[{'GridName':'Grid2','Count':1,'Columns':[{} for _ in range(24)],
                                '0':{'Props':[[field+'_0001',value] for field,value in zip(FIELDS,row)]}}]}
            return 200,'application/json',json.dumps(payload)
        if path.lower().endswith('/hcglineas.aspx'):
            from core.tables import DETAIL_FIELDS
            offset = int(json.loads(form['GXState'][0])['GRID1_nFirstRecordOnPage'])+2 if post else 0
            self.offsets.append(offset)
            if offset==self.fail_offset:
                return 503,'text/html','Fallo controlado después de páginas verificadas'
            eof = self.empty or offset>=6
            if self.repeated_last and offset>=6:
                offset,eof = 4,True
            count = 0 if self.empty else 2 if offset<6 else 1
            values=[]
            for number in range(offset+1,offset+count+1):
                values.append(['icon']*5+[f'{number:03d}','','001.000','CA','02.000','0.000',
                    'A001','Depósito','013','MARCAS','ACT','','','','0'])
            if offset==self.changed_offset and values:
                values[0][14]='CAMBIADO'
            state = dict(zip(['CGTPOTRANS','CGTPOMIC','CGNROMIC','RGDEPID','CGFCHARR'],query['mid'][0].split('-')))
            grid = {'Count':count,'Columns':[{} for _ in range(20)]}
            if values: grid['0']={'Props':[[f+'_0001'] for f in DETAIL_FIELDS]}
            state.update(CGNROCON=query['bl'][0],CGNROCONDNA=query['seq'][0],nRC_Grid1=str(count),
                         Grid1ContainerData=grid,GRID1_nFirstRecordOnPage=str(offset),GRID1_nEOF='1' if eof else '0')
            body = ''.join('<input name="'+key+'" value="'+escape(json.dumps(value),quote=True)+'">'
                           for key,value in [('GXState',state),('Grid1ContainerDataV',values)])
            if not eof: body+='<button class="PagingButtonsNext">Siguiente</button>'
            return 200,'text/html',body
        return 404,'text/html','Ruta no permitida en la prueba local'
