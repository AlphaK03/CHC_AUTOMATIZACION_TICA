import asyncio
import csv
import gc
import sys
import tempfile
import time
from threading import Event
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from config_manager import DEFAULTS
from core.engine import BLSProcessor
from test_bls_asyncio import frame
from main import App
from input_cache import load_input_cache, save_input_cache
from test_input_files import generated_database


class UITests(unittest.TestCase):
    def tearDown(self):
        # Liberar los intérpretes Tk destruidos en su hilo propietario, antes de
        # que el próximo trabajador active la recolección de ciclos pendientes.
        gc.collect()

    def test_file_picker_opens_both_formats_in_background_and_preserves_previous_base_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            excel = Path(folder) / 'base.xlsx'
            sqlite = Path(folder) / 'entrada.db'
            generated = Path(folder) / 'base_conocimientos.sqlite3'
            frame().to_excel(excel, sheet_name='BLS', index=False)
            save_input_cache(frame(), sqlite, sheet_name='BLS')
            generated_database(generated, frame())
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('main.APP_DIR', folder), patch('main.load_config', return_value=dict(DEFAULTS)), \
                     patch('main._setup_logging'), patch.object(App, '_load_saved_data'), \
                     patch('main.save_config'), patch('main.messagebox.showerror') as error:
                    app = App(root)
                    for path in (excel, generated, sqlite):
                        with patch('main.filedialog.askopenfilename', return_value=str(path)) as picker:
                            app._select_file()
                        self.assertTrue(app._loading_data)
                        self.assertIsNotNone(app._loading_mask)
                        self.assertIn('SQLite', str(picker.call_args.kwargs['filetypes']))
                        deadline = time.monotonic() + 5
                        while app._loading_data and time.monotonic() < deadline:
                            root.update()
                            time.sleep(.01)
                        self.assertFalse(app._loading_data)
                        self.assertEqual(app.duals_df['BL original'].tolist(), frame()['BL original'].tolist())
                        self.assertEqual(app.config['sheet_name'], 'BLS')
                        self.assertEqual(app._loaded_file_path, str(path))
                        self.assertNotIn('disabled', app.file_button.state())
                    previous = app.duals_df
                    bad = Path(folder) / 'no_es_una_base.sqlite3'
                    bad.write_text('archivo inválido', encoding='utf-8')
                    app._load_sheet(str(bad))
                    deadline = time.monotonic() + 5
                    while app._loading_data and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(app._loading_data)
                    self.assertIs(app.duals_df, previous)
                    self.assertEqual(app._loaded_file_path, str(sqlite))
                    self.assertNotIn('disabled', app.notebook.state())
                    error.assert_called_once()
                    root.after_cancel(app.event_poll_id)
            finally:
                if 'app' in locals() and app._loading_thread is not None:
                    app._loading_thread.join(5)
                root.destroy()

    def test_startup_failure_removes_overlay_and_allows_selecting_a_new_base(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data/Datos_Cargados/BLS.sqlite3'
            path.parent.mkdir(parents=True)
            path.write_text('caché dañada', encoding='utf-8')
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('main.APP_DIR', folder), patch('main.load_config', return_value=dict(DEFAULTS)), \
                     patch('main._setup_logging'):
                    app = App(root)
                    deadline = time.monotonic() + 5
                    while app._loading_data and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(app._loading_data)
                    self.assertIsNone(app._loading_mask)
                    self.assertIsNone(app.duals_df)
                    self.assertNotIn('disabled', app.file_button.state())
                    self.assertNotIn('disabled', app.notebook.state())
                    self.assertIn('Seleccione el Excel', app.status_var.get())
                    root.after_cancel(app.event_poll_id)
            finally:
                root.destroy()

    def test_startup_load_is_background_blocks_controls_and_migrates_excel_once(self):
        with tempfile.TemporaryDirectory() as folder:
            cached = Path(folder) / 'data/Datos_Cargados/BLS.xlsx'
            cached.parent.mkdir(parents=True)
            frame().to_excel(cached, sheet_name='BLS', index=False)
            release = Event()
            from data_reader import leer_bls
            def slow_excel(path, sheet):
                release.wait(5)
                return leer_bls(path, sheet)
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('main.APP_DIR', folder), patch('main.load_config', return_value=dict(DEFAULTS)), \
                     patch('main._setup_logging'), patch('main.leer_bls', side_effect=slow_excel) as reader:
                    app = App(root)
                    self.assertTrue(app._loading_data)
                    self.assertIsNotNone(app._loading_mask)
                    for control in (app.start_btn, app.file_button, app.new_batch_button, app.notebook):
                        self.assertIn('disabled', control.state())
                    app._start()
                    self.assertFalse(app._processing)
                    root.update()
                    release.set()
                    deadline = time.monotonic() + 5
                    while app._loading_data and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(app._loading_data)
                    self.assertIsNone(app._loading_mask)
                    self.assertNotIn('disabled', app.notebook.state())
                    self.assertNotIn('disabled', app.start_btn.state())
                    self.assertEqual(len(app.duals_df), 3)
                    sqlite = cached.with_suffix('.sqlite3')
                    self.assertTrue(sqlite.exists())
                    self.assertTrue(cached.exists())
                    self.assertEqual(load_input_cache(sqlite)['BL original'].tolist(),
                                     app.duals_df['BL original'].tolist())
                    reader.reset_mock()
                    app._load_saved_data()
                    deadline = time.monotonic() + 5
                    while app._loading_data and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(app._loading_data)
                    reader.assert_not_called()
                    root.after_cancel(app.event_poll_id)
            finally:
                release.set()
                if 'app' in locals() and app._loading_thread is not None:
                    app._loading_thread.join(5)
                root.destroy()

    def test_browser_install_status_is_visible_and_restores_saved_progress(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with patch('main.load_config', return_value=dict(DEFAULTS)), patch('main._setup_logging'), \
                 patch.object(App, '_load_saved_data'):
                app = App(root)
                app.progress_var.set(37)
                app.rows_var.set('994 BL guardados')
                app._display_progress({'phase': 'browser_setup', 'message': 'Descargando Chromium…'})
                root.update()
                self.assertEqual(str(app.progress_bar.cget('mode')), 'indeterminate')
                self.assertEqual(app.status_var.get(), 'Descargando Chromium…')
                self.assertEqual(app.rows_var.get(), '994 BL guardados')
                self.assertEqual(app.progress_var.get(), 37)
                app._display_progress({'phase': 'network_wait', 'message': 'Esperando reconexión…'})
                app._display_progress({'kind': 'job', 'total': 100, 'saved': 38, 'pending': 62, 'rows': []})
                self.assertEqual(str(app.progress_bar.cget('mode')), 'indeterminate')
                self.assertEqual(app.status_var.get(), 'Esperando reconexión…')
                app._display_progress({'phase': 'network_resumed', 'message': 'Conexión recuperada',
                                       'total': 100, 'saved': 38, 'pending': 62})
                self.assertEqual(str(app.progress_bar.cget('mode')), 'determinate')
                self.assertEqual(app.progress_var.get(), 38)
                app._display_progress({'phase': 'download', 'total': 100, 'saved': 37, 'pending': 63})
                self.assertEqual(str(app.progress_bar.cget('mode')), 'determinate')
                self.assertEqual(app.progress_var.get(), 37)
                root.after_cancel(app.event_poll_id)
        finally:
            root.destroy()

    def test_gui_pipeline_uses_sqlite_and_updates_only_via_event_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            config = dict(DEFAULTS, sheet_name='BLS', output_base_path=folder, cant_hilos=2, max_retries=1)
            class Session:
                async def query(self, record):
                    await asyncio.sleep(.04 if record['Secuencia Tica'] == '1' else .001)
                    return {'status': 'success', 'columns': ['BL', 'Aduana'], 'rows': [[record['BL original'], '013']]}
                async def close(self):
                    pass
            class Processor(BLSProcessor):
                def run(self, data):
                    return asyncio.run(self.run_async(data, session_factory=lambda worker: Session()))
            root = tk.Tk()
            root.withdraw()
            try:
                with patch('main.load_config', return_value=config), patch('main.save_config'), \
                     patch('main._setup_logging'), patch.object(App, '_load_saved_data'), \
                     patch('main.BLSProcessor', Processor), patch('main.messagebox.showinfo') as info:
                    app = App(root)
                    app.duals_df = frame()
                    app._start()
                    deadline = time.monotonic() + 5
                    while app._processing and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(app._processing)
                    self.assertEqual(app.last_summary['saved'], 3)
                    self.assertEqual(app.last_summary['pending'], 0)
                    self.assertTrue(Path(app.last_summary['database']).exists())
                    self.assertEqual(len(app.job_table.get_children()), 3)
                    self.assertEqual(app.progress_var.get(), 100)
                    with Path(app.last_summary['output_csv']).open(encoding='utf-8-sig', newline='') as stream:
                        self.assertEqual(list(csv.reader(stream))[1:], [['0001', '013'], ['0002', '013'], ['0003', '013']])
                    info.assert_called_once()
                    app._start()
                    deadline = time.monotonic() + 5
                    while app._processing and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertEqual(app.last_summary['attempts'], 3)
                    root.after_cancel(app.event_poll_id)
            finally:
                root.destroy()


if __name__ == '__main__':
    unittest.main()
