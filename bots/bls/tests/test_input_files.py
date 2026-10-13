from contextlib import closing, redirect_stderr, redirect_stdout
import io
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import cli
from config_manager import DEFAULTS
from core.inputs import batch_scope
from input_cache import save_input_cache
from input_files import BLS_COLUMNS, input_sheets, load_input_file
from test_bls_asyncio import frame


def generated_database(path, data):
    """Contrato público de Conocimientos: una tabla, cinco columnas de texto."""
    quoted = ','.join('"' + column + '" TEXT NOT NULL' for column in BLS_COLUMNS)
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute(f'CREATE TABLE BLS ({quoted})')
            db.executemany('INSERT INTO BLS VALUES (?,?,?,?,?)',
                           data[BLS_COLUMNS].itertuples(index=False, name=None))


class InputFilesTests(unittest.TestCase):
    def test_generated_sqlite_and_excel_have_identical_rows_jobs_dates_and_signature(self):
        from core.inputs import input_job, query_dates
        with tempfile.TemporaryDirectory() as folder:
            excel = Path(folder) / 'base.xlsx'
            sqlite = Path(folder) / 'renombrada.db'
            original = frame()
            original.loc[0, 'BL original'] = '00001234567890123456789'
            original.loc[0, 'Secuencia Tica'] = '001'
            original.to_excel(excel, sheet_name='BLS', index=False)
            generated_database(sqlite, original)
            before = sqlite.read_bytes()
            loaded = load_input_file(sqlite)
            expected = load_input_file(excel)
            self.assertEqual(input_sheets(sqlite), ['BLS'])
            self.assertEqual(loaded.to_dict('records'), expected.to_dict('records'))
            self.assertEqual(batch_scope(loaded, DEFAULTS), batch_scope(expected, DEFAULTS))
            for ordinal, record in enumerate(loaded.to_dict('records'), 1):
                self.assertFalse(input_job(record, ordinal)['error'])
                self.assertEqual(query_dates(record, DEFAULTS), ('01/04/2026', '30/04/2026'))
            self.assertEqual(loaded.loc[0, 'Secuencia Tica'], '001')
            self.assertEqual(loaded.loc[0, 'BL original'], '00001234567890123456789')
            with self.assertRaisesRegex(ValueError, 'no.*Faltantes'):
                load_input_file(sqlite, 'Faltantes')
            cache = Path(folder) / 'cache.sqlite3'
            save_input_cache(loaded, cache, sheet_name='BLS')
            self.assertEqual(batch_scope(load_input_file(cache), DEFAULTS),
                             batch_scope(expected, DEFAULTS))
            self.assertEqual(sqlite.read_bytes(), before)

    def test_generated_sqlite_rejects_empty_null_and_incompatible_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'base.sqlite3'
            generated_database(path, frame().head(0))
            with self.assertRaisesRegex(ValueError, 'no contiene BL'):
                input_sheets(path)
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute('DROP TABLE BLS')
                    quoted = ','.join('"' + column + '" TEXT' for column in BLS_COLUMNS)
                    db.execute(f'CREATE TABLE BLS ({quoted})')
                    db.execute('INSERT INTO BLS VALUES (?,?,?,?,?)',
                               [None, '001', '000123', '01/04/2026', '2026-04'])
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'nulos'):
                load_input_file(path)
            self.assertEqual(path.read_bytes(), before)
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute('DROP TABLE BLS')
                    db.execute('CREATE TABLE BLS ("BL original" INTEGER)')
                    db.execute('INSERT INTO BLS VALUES (123)')
            with self.assertRaisesRegex(ValueError, 'cinco columnas TEXT'):
                load_input_file(path)

    def test_missing_sqlite_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'no_existe.sqlite3'
            with self.assertRaises(sqlite3.OperationalError):
                load_input_file(path)
            self.assertFalse(path.exists())

    def test_cli_opens_generated_sqlite_as_bls(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'base.db'
            generated_database(path, frame())
            argv = ['run_cli.py', '--archivo', str(path), '--salida', folder]
            with patch('sys.argv', argv), patch('cli.load_config', return_value=dict(DEFAULTS)), \
                 patch('cli.BLSProcessor') as processor, redirect_stdout(io.StringIO()):
                processor.return_value.run.return_value = {'saved': 3}
                processor.return_value.stats = {}
                cli.main()
            self.assertEqual(processor.call_args.args[0]['sheet_name'], 'BLS')
            self.assertEqual(processor.return_value.run.call_args.args[0].to_dict('records'),
                             load_input_file(path).to_dict('records'))

    def test_excel_and_sqlite_preserve_the_same_selection_and_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            excel = Path(folder) / 'base.xlsx'
            sqlite = Path(folder) / 'entrada.sqlite3'
            original = frame()
            original.loc[0, 'BL original'] = '00001234567890123456789'
            original.loc[0, 'Secuencia Tica'] = '001'
            original.to_excel(excel, sheet_name='BLS', index=False)
            from_excel = load_input_file(excel)
            save_input_cache(from_excel, sqlite, excel, sheet_name='BLS')
            from_sqlite = load_input_file(sqlite)
            self.assertEqual(input_sheets(excel), ['BLS'])
            self.assertEqual(input_sheets(sqlite), ['BLS'])
            self.assertEqual(from_sqlite['BL original'].tolist(), from_excel['BL original'].tolist())
            self.assertEqual(from_sqlite.loc[0, 'Secuencia Tica'], '001')
            self.assertEqual(batch_scope(from_sqlite, DEFAULTS), batch_scope(from_excel, DEFAULTS))

    def test_renamed_sqlite_keeps_its_sheet_and_rejects_another_sheet(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / 'Faltantes.sqlite3'
            copied = Path(folder) / 'copia_renombrada.db'
            save_input_cache(frame(), original, sheet_name='Faltantes')
            shutil.copyfile(original, copied)
            self.assertEqual(input_sheets(copied), ['Faltantes'])
            self.assertEqual(load_input_file(copied).attrs['sheet_name'], 'Faltantes')
            with self.assertRaisesRegex(ValueError, 'no.*BLS'):
                load_input_file(copied, 'BLS')

    def test_previous_cache_without_sheet_metadata_still_opens(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'BLS.sqlite3'
            save_input_cache(frame(), path)
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute("DELETE FROM metadata WHERE key='sheet_name'")
            self.assertEqual(input_sheets(path), ['BLS'])
            self.assertEqual(len(load_input_file(path)), 3)

    def test_progress_database_is_rejected_without_changing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bls.sqlite3'
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute('CREATE TABLE metadata(key TEXT,value TEXT)')
                    db.execute('INSERT INTO metadata VALUES (?,?)', ('signature', 'conservada'))
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'base de progreso'):
                load_input_file(path)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_uses_the_sheet_stored_in_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'entrada.db'
            save_input_cache(frame(), path, sheet_name='Faltantes')
            argv = ['run_cli.py', '--archivo', str(path), '--salida', folder]
            with patch('sys.argv', argv), patch('cli.load_config', return_value=dict(DEFAULTS)), \
                 patch('cli.BLSProcessor') as processor, redirect_stdout(io.StringIO()):
                processor.return_value.run.return_value = {'saved': 3}
                processor.return_value.stats = {}
                cli.main()
            config = processor.call_args.args[0]
            self.assertEqual(config['sheet_name'], 'Faltantes')
            self.assertEqual(processor.return_value.run.call_args.args[0]['BL original'].tolist(),
                             frame()['BL original'].tolist())
            with patch('sys.argv', argv + ['--hoja', 'BLS']), \
                 patch('cli.load_config', return_value=dict(DEFAULTS)), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main()
            self.assertEqual(error.exception.code, 2)
