"""Una página llena repetida solo termina con EOF y respuesta coherente de TICA."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime.profiles import load_profile
from chc_runtime.transit import FIELDS, confirmed_last_page


class TransitPaginationTest(unittest.TestCase):
    def test_exactly_fifty_requires_confirmed_matching_end(self):
        clean = load_profile('duas_transito')['flow']()._clean
        values = [[f'{item:04}', '00001234', '', 'Carga, con; texto', '2', 'CAJA',
                   'Consignatario', '', '', '', '', '', 'NO'] for item in range(1, 51)]
        rows = [{**{key: clean(value[index]) for key, index in
                    zip(FIELDS[:-1], (0, 1, 3, 4, 5, 6, 12))},
                 'numero_del_dua': '001-2026-078194'} for value in values]
        payload = {'gxMessages': {'MAIN': [], 'MPW0015': []},
                   'gxHiddens': {'CODI_ADUAN': '001', 'ANO_PRESE': '2026',
                                 'NUME_CORRE': '078194', 'SERIES_nEOF': '1',
                                 'nRC_Series': '50', 'SeriesContainerDataV': json.dumps(values)},
                   'gxGrids': [{'GridName': 'Series', 'Count': 50}]}
        self.assertTrue(confirmed_last_page(payload, rows, clean))
        changes = [({'SERIES_nEOF': '0'}, None), ({'NUME_CORRE': '078195'}, None),
                   ({'nRC_Series': '49'}, None), ({'SeriesContainerDataV': '[]'}, None),
                   ({'SeriesContainerDataV': 'invalid'}, None),
                   ({}, {'MAIN': ['Error del portal']}), ({}, {'MPW0015': []})]
        for hidden, messages in changes:
            with self.subTest(hidden=hidden, messages=messages):
                broken = deepcopy(payload)
                broken['gxHiddens'].update(hidden)
                if messages is not None:
                    broken['gxMessages'] = messages
                self.assertFalse(confirmed_last_page(broken, rows, clean))
        changed = deepcopy(values)
        changed[0][3] = 'Otra carga'
        payload['gxHiddens']['SeriesContainerDataV'] = json.dumps(changed)
        self.assertFalse(confirmed_last_page(payload, rows, clean))
        self.assertFalse(confirmed_last_page(None, rows, clean))


if __name__ == '__main__':
    unittest.main()
