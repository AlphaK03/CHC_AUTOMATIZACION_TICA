"""Interfaz y worker reales con respuestas sintéticas; ningún acceso al portal."""
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import main
from runner import run_downloads
from data_store import OUTPUT_NAMES


class UITests(unittest.TestCase):
    def test_download_and_merge_buttons_use_verified_store(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            original_tk = tk.Tk
            failures = []
            stage = [0]
            calls = []
            deadline = time.monotonic() + 30
            class Browser:
                def __init__(self, *args, **kwargs): pass
                def fetch_range(self, regimen, period, start, end):
                    calls.append((regimen, period, start, end))
                    return []
                def close(self): pass

            def offline(*args, **kwargs):
                return run_downloads(*args, **kwargs, factory=Browser)

            def widgets(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from widgets(child)

            def create_root():
                root = original_tk()
                root.withdraw()
                def drive():
                    try:
                        if time.monotonic() > deadline:
                            raise AssertionError('El worker no terminó')
                        buttons = {str(w.cget('text')): w for w in widgets(root) if 'text' in w.keys() and hasattr(w, 'invoke')}
                        start = next(w for label, w in buttons.items() if 'Iniciar' in label)
                        merge = buttons['Unir archivos finales']
                        if stage[0] == 0:
                            buttons['Todos los regímenes'].invoke()
                            start.invoke()
                            self.assertEqual(str(merge.cget('state')), 'disabled')
                            stage[0] = 1
                        elif stage[0] == 1 and str(start.cget('state')) == 'normal':
                            self.assertEqual(len(calls), 18)
                            self.assertTrue(all(row[1] == '2026-03' for row in calls))
                            buttons['Exportar originales…'].invoke()
                            buttons = {str(w.cget('text')): w for w in widgets(root) if 'text' in w.keys() and hasattr(w, 'invoke')}
                            buttons['Exportar a Excel'].invoke()
                            stage[0] = 2
                        elif stage[0] == 2 and str(merge.cget('state')) == 'normal':
                            originals = list(folder.glob('*/2026-03/*.xlsx'))
                            self.assertEqual(len(originals), 18)
                            merge.invoke()
                            stage[0] = 3
                        elif stage[0] == 3 and str(merge.cget('state')) == 'normal':
                            self.assertTrue(all((folder / name).exists() for name in OUTPUT_NAMES))
                            self.assertEqual(len(list(folder.glob('*/2026-03/*.xlsx'))), 9)
                            stage[0] = 4
                            root.destroy()
                            return
                        root.after(30, drive)
                    except BaseException as exc:
                        failures.append(exc)
                        root.destroy()
                root.after(100, drive)
                return root

            with patch('main.tk.Tk', side_effect=create_root), \
                    patch('main.cargar_app_config', return_value={'output_folder': str(folder), 'edge_driver_path': 'unused'}), \
                    patch('main.cargar_seleccion', return_value={'regimen': 'TRANSITO', 'mes': 'Marzo', 'anio': '2026', 'rango': 'Ambos'}), \
                    patch('main.guardar_seleccion'), patch('main.get_database_path', return_value=folder / 'duas.sqlite3'), \
                    patch('main.run_downloads', side_effect=offline), \
                    patch('main.messagebox.showinfo'), patch('main.messagebox.showerror') as errors:
                main.mostrar_interfaz()
                if failures:
                    raise failures[0]
                errors.assert_not_called()
                self.assertEqual(stage[0], 4)


if __name__ == '__main__':
    unittest.main()
