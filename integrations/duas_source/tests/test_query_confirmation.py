"""Vacíos confirmados y errores: datos locales, nunca consultas a TICA."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from data_store import REGIMENES, RangeStore
from query_confirmation import confirmed_count
from tica_dua_bot import TICADUAExtractor

EXPECTED = {'start': '11/10/26', 'end': '11/10/26', 'regimenCode': '41'}


def response(count=0, expected=None):
    expected = expected or EXPECTED
    return {
        'gxMessages': {'MAIN': []},
        'gxHiddens': {'CAPTCHA1_Validationresult': '1', 'vVCANTREG': str(count),
                      'nRC_Subfile1': str(count), 'Subfile1ContainerDataV': '[]'},
        'gxValues': [{'CmpContext': '', 'IsMasterPage': 'False',
                      'AV13CODI_REGI': expected['regimenCode'],
                      'AV35vFchIni': expected['start'], 'AV32vFchFin': expected['end'],
                      'AV26vCantReg': str(count), 'AV24TIPO_OPERA': '', 'AV31vEstado': '',
                      'AV27vCodAdu': '', 'AV12CODI_ALMA': '', 'AV28vCodAdu2': '', 'AV8CALMDEST': ''}],
        'gxProps': [{'CmpContext': '', 'IsMasterPage': 'False',
                     'BUTTON6': {'Visible': '1' if count else '0'}, 'MENS': {'Visible': '0'}}],
        'gxGrids': [{'GridName': 'Subfile1', 'CmpContext': '', 'Count': count}],
    }


def reply(payload=None, **values):
    return {'done': True, 'status': 200, 'requested': dict(EXPECTED),
            'text': json.dumps(response() if payload is None else payload), **values}


class ConfirmationTests(unittest.TestCase):
    def test_empty_requires_completed_matching_server_response(self):
        self.assertEqual(confirmed_count(reply(), EXPECTED), 0)
        cases = [reply(done=False), reply(status=0), reply(status=503),
                 reply(text='<html>Error</html>'), reply(text='{"gxHiddens":'),
                 reply(requested={**EXPECTED, 'start': '10/10/26'}), reply(error='redirección')]
        for candidate in cases:
            with self.subTest(reply=candidate), self.assertRaises(ValueError):
                confirmed_count(candidate, EXPECTED)
        payload = response()
        payload['gxMessages'] = {}
        with self.assertRaises(ValueError):
            confirmed_count(reply(payload), EXPECTED)

    def test_captcha_messages_query_filters_and_counts_cannot_be_errors_as_empty(self):
        for section, field, value in [
            ('gxHiddens', 'CAPTCHA1_Validationresult', '0'),
            ('gxMessages', 'MAIN', [{'Text': 'Error al consultar'}]),
            ('gxHiddens', 'vVCANTREG', 'desconocido'),
            ('gxHiddens', 'nRC_Subfile1', '1'),
            ('gxHiddens', 'Subfile1ContainerDataV', '[{}]'),
        ]:
            payload = response()
            payload[section][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                confirmed_count(reply(payload), EXPECTED)
        for field, value in [('AV35vFchIni', '10/10/26'), ('AV32vFchFin', '12/10/26'),
                             ('AV13CODI_REGI', '80'), ('AV24TIPO_OPERA', '5'),
                             ('AV26vCantReg', '1')]:
            payload = response()
            payload['gxValues'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                confirmed_count(reply(payload), EXPECTED)
        for section in ('gxHiddens', 'gxValues', 'gxProps', 'gxGrids', 'gxMessages'):
            payload = response()
            del payload[section]
            with self.subTest(missing=section), self.assertRaises(ValueError):
                confirmed_count(reply(payload), EXPECTED)
        payload = response()
        payload['gxProps'][0]['MENS']['Visible'] = '1'
        with self.assertRaises(ValueError):
            confirmed_count(reply(payload), EXPECTED)
        self.assertEqual(confirmed_count(reply(response(1)), EXPECTED), 1)

    def test_some_or_all_empty_regimens_still_prove_complete_daily_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RangeStore(Path(folder) / 'test.sqlite3')
            try:
                ids = store.plan('2026-10', REGIMENES, [(11, 11)])
                for index, key in enumerate(ids):
                    # Dos regímenes vacíos confirmados; los restantes conservan sus DUAs.
                    count = confirmed_count(reply(response(0 if index in (1, 5) else 1)), EXPECTED)
                    store.complete(key, [] if count == 0 else
                                   [{'aduana': '001', 'ano': '2026', 'numero': str(index + 1)}])
                lists, missing = store.collect('2026-10', [(11, 11)])
                self.assertEqual(missing, [])
                self.assertEqual(len(lists[0]), 7)
                for key in ids:
                    store.complete(key, [])
                self.assertEqual(store.collect('2026-10', [(11, 11)]), ([[], [], []], []))
            finally:
                store.close()


FORM = '''<!doctype html><meta charset="utf-8">
<select id="vCODI_REGI"><option value="41">EXPORTACION TEMPORAL</option></select>
<input id="vVFCHINI"><input id="vVFCHFIN"><input id="_cfield">
<div id="captchaImage"><img src="/Captcha/images/74.jpg"></div>
<p>Cantidad de registros: 0</p>
<button name="BUTTON1" onclick="confirmQuery()">Confirmar</button>
<button name="BUTTON6" style="display:none" onclick="showXML()">Datos XML</button>
<script>
function confirmQuery(){
  const values=new URLSearchParams({vVFCHINI:document.getElementById('vVFCHINI').value,
    vVFCHFIN:document.getElementById('vVFCHFIN').value,
    vCODI_REGI:document.getElementById('vCODI_REGI').value,
    cfield:document.getElementById('_cfield').value,GXState:'{"_EventName":"EENTER."}'});
  const request=new XMLHttpRequest();request.open('POST',location.href);
  request.addEventListener('load',()=>{try{if(JSON.parse(request.responseText).gxHiddens.vVCANTREG==='1')
    document.getElementsByName('BUTTON6')[0].style.display='block';}catch(e){}});
  request.send(values.toString());
}
function showXML(){document.body.innerHTML='<root><dua><aduana>001</aduana><ano>2026</ano><numero>000001</numero></dua></root>';}
</script>'''


@contextmanager
def local_portal():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(FORM.encode())

        def do_POST(self):
            fields = parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
            expected = {key: fields[field][0] for key, field in
                        [('start', 'vVFCHINI'), ('end', 'vVFCHFIN'), ('regimenCode', 'vCODI_REGI')]}
            mode = parse_qs(urlsplit(self.path).query).get('mode', ['empty'])[0]
            payload = response(1 if mode == 'positive' else 0, expected)
            if mode == 'captcha':
                payload['gxHiddens']['CAPTCHA1_Validationresult'] = '0'
            self.send_response(503 if mode == 'http-error' else 200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/hciduare.aspx'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@unittest.skipUnless(os.environ.get('DUA_TEST_DRIVER'), 'Edge local opcional')
class BrowserConfirmationTests(unittest.TestCase):
    def test_submission_observer_empty_positive_and_failures_on_local_server(self):
        class LocalDates(TICADUAExtractor):
            def seleccionar_fecha(self, expected, input_id):
                self.driver.execute_script('document.getElementById(arguments[0]).value=arguments[1]',
                                           input_id, expected.strftime('%d/%m/%y'))
        bot = LocalDates({'edge_driver_path': os.environ['DUA_TEST_DRIVER'], 'mostrar_navegador': False})
        self.addCleanup(bot.close)
        with local_portal() as url:
            with patch('tica_dua_bot.URL', url):
                self.assertEqual(bot.fetch_range('EXPORTACION TEMPORAL', '2026-10', 11, 11), [])
            with patch('tica_dua_bot.URL', url + '?mode=positive'):
                self.assertEqual(bot.fetch_range('EXPORTACION TEMPORAL', '2026-10', 11, 11)[0]['numero'], '000001')
            for mode in ('http-error', 'captcha'):
                with self.subTest(mode=mode), patch('tica_dua_bot.URL', url + '?mode=' + mode):
                    with self.assertRaises(ValueError):
                        bot.fetch_range('EXPORTACION TEMPORAL', '2026-10', 11, 11)


if __name__ == '__main__':
    unittest.main()
