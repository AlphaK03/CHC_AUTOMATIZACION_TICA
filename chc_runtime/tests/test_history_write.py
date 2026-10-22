"""Historial auxiliar: bloqueo transitorio Windows sin truncar lo ya guardado."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chc_runtime.manifest_service import write_json


class HistoryWriteTests(unittest.TestCase):
    def test_retries_transient_replace_and_keeps_old_file_on_permanent_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.json';path.write_text('{"saved":1}',encoding='utf-8')
            old=path.read_bytes()
            import os
            replace=os.replace;calls=[]
            def blocked(source,target):
                calls.append(source)
                self.assertEqual(path.read_bytes(),old)
                if len(calls)<3:raise PermissionError('lector activo')
                replace(source,target)
            with patch('chc_runtime.manifest_service.os.replace',blocked),patch('chc_runtime.manifest_service.time.sleep'):
                write_json(path,{'saved':2})
            self.assertEqual(json.loads(path.read_text()),{'saved':2})
            with patch('chc_runtime.manifest_service.os.replace',side_effect=PermissionError('permiso')),patch('chc_runtime.manifest_service.time.sleep'):
                with self.assertRaises(PermissionError):write_json(path,{'saved':3})
            self.assertEqual(json.loads(path.read_text()),{'saved':2})
            self.assertEqual(list(Path(folder).glob('*.new')),[])


if __name__=='__main__':unittest.main()
