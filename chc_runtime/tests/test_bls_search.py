"""Respuestas GET locales: validar filtros, esquema e identidad antes de usar líneas."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'bots/bls/src'))
from core.tables import InvalidResponse
from chc_runtime.bls_page_fixture import BLSPagePortal
from chc_runtime.bls_search import parse_search_response


class BLSSearchTests(unittest.TestCase):
    def setUp(self):
        self.record={'IDManifiesto':'1-0-00001-A01-01/09/26','Secuencia Tica':'1','BL original':'0000123'}
        self.dates=('01/09/2026','30/09/2026')
        # Sin servidor ni navegador: solo el generador local de respuestas.
        portal=BLSPagePortal.__new__(BLSPagePortal)
        portal.searches=[]
        _,_,body=portal.response('/Tica/hcgconocimientos.aspx',
            {'lookup':['1'],'bl':['0000123'],'from':[self.dates[0]],'to':[self.dates[1]]},{},False)
        self.payload=json.loads(body)

    def test_complete_get_preserves_text_identity_and_link(self):
        selected,manifests=parse_search_response(self.payload,self.record,self.dates)
        self.assertEqual(selected['sequence'],'1')
        self.assertIn('bl=0000123',selected['href'])
        self.assertEqual(manifests,[self.record['IDManifiesto']])

    def test_stale_filters_messages_or_incomplete_schema_rejected(self):
        variants=[]
        for field in ('AV5CGNroCon','AV15vFch1','AV16VfchF'):
            data=copy.deepcopy(self.payload);data['gxValues'][0][field]='otro';variants.append(data)
        data=copy.deepcopy(self.payload);data['gxMessages']['MAIN']=['Error'];variants.append(data)
        data=copy.deepcopy(self.payload);data['gxGrids'][0]['Columns'].pop();variants.append(data)
        data=copy.deepcopy(self.payload);data['gxGrids'][0]['0']['Props'][0][0]='OTRO_0001';variants.append(data)
        data=copy.deepcopy(self.payload);data['gxGrids'][0]['Count']=2;variants.append(data)
        data=copy.deepcopy(self.payload);data['gxValues'].append(data['gxValues'][0].copy());variants.append(data)
        for data in variants:
            with self.subTest(data=data),self.assertRaises(InvalidResponse):
                parse_search_response(data,self.record,self.dates)

    def test_other_manifest_bl_or_sequence_cannot_select_a_detail(self):
        for position in (0,7,8):
            data=copy.deepcopy(self.payload)
            data['gxGrids'][0]['0']['Props'][position][1]='999'
            selected,_=parse_search_response(data,self.record,self.dates)
            self.assertIsNone(selected)


if __name__=='__main__':unittest.main()
