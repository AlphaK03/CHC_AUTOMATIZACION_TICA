import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from core.inputs import batch_scope
from input_cache import load_input_cache, save_input_cache
from test_bls_asyncio import frame


class InputCacheTests(unittest.TestCase):
    def test_roundtrip_preserves_text_order_and_batch_identity(self):
        data = frame()
        data.loc[0, 'BL original'] = '00001234567890123456789'
        data.loc[1, 'Secuencia Tica'] = '001'
        data['Extra'] = [None, float('nan'), '013']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'BLS.sqlite3'
            save_input_cache(data, path)
            restored = load_input_cache(path)
        self.assertEqual(restored['BL original'].tolist(), data['BL original'].tolist())
        self.assertEqual(restored.loc[1, 'Secuencia Tica'], '001')
        self.assertEqual(restored['Extra'].tolist(), ['', 'nan', '013'])
        self.assertEqual(batch_scope(restored, {'sheet_name': 'BLS'}),
                         batch_scope(data, {'sheet_name': 'BLS'}))

    def test_failed_replace_keeps_previous_cache_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'BLS.sqlite3'
            original = frame()
            save_input_cache(original, path)
            with patch('input_cache.os.replace', side_effect=PermissionError('bloqueado')):
                with self.assertRaises(PermissionError):
                    save_input_cache(original.head(1), path)
            self.assertEqual(load_input_cache(path)['BL original'].tolist(),
                             original['BL original'].tolist())
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_incomplete_or_nontext_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'BLS.sqlite3'
            save_input_cache(frame(), path)
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute('UPDATE input_rows SET payload=? WHERE ordinal=1', (json.dumps([1]),))
            with self.assertRaisesRegex(ValueError, 'Fila de caché'):
                load_input_cache(path)
            save_input_cache(frame(), path)
            self.assertEqual(len(load_input_cache(path)), 3)
