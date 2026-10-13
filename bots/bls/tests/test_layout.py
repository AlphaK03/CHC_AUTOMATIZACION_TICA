"""Regresiones de lanzadores y rutas con fuentes en src y datos en la raíz."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from config_manager import _config_path
from paths import APP_DIR


class LayoutTests(unittest.TestCase):
    def test_cli_imports_src_modules_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'run_cli.py'), '--help'],
                cwd=folder, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--exportar-db', result.stdout)
        self.assertIn('--archivo', result.stdout)

    def test_development_paths_and_configuration_example_use_root(self):
        self.assertEqual(Path(APP_DIR), ROOT)
        self.assertEqual(Path(_config_path()), ROOT / 'config.json')
        from config_manager import DEFAULTS
        example = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
        self.assertEqual(example, DEFAULTS)
