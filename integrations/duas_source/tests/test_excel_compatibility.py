"""SpreadsheetML ordering and optional actual Microsoft Excel validation."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from excel_format import write_excel, empty_columns
from data_store import OUTPUT_NAMES


class ExcelCompatibilityTests(unittest.TestCase):
    def test_worksheet_properties_precede_dimension(self):
        with tempfile.TemporaryDirectory() as folder:
            for values in ([], [['001-2026-000001']]):
                path = Path(folder) / 'test.xlsx'
                write_excel(path, 'septiembre26', ['NroDUA'], values)
                with ZipFile(path) as archive:
                    root = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
                names = [child.tag.rsplit('}', 1)[-1] for child in root]
                self.assertEqual(names[:4], ['sheetPr', 'dimension', 'sheetViews', 'sheetFormatPr'])
                self.assertEqual(root[1].attrib['ref'], f'A1:A{len(values) + 1}')

    @unittest.skipUnless(os.environ.get('DUA_TEST_EXCEL'), 'Set DUA_TEST_EXCEL to validate with Microsoft Excel')
    def test_excel_opens_original_and_three_totals_without_repair(self):
        import win32com.client
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in OUTPUT_NAMES:
                write_excel(root / name, 'septiembre26', ['NroDUA'], [['001-2026-000001']])
            columns = empty_columns('TRANSITO')
            original = root / 'original.xlsx'
            write_excel(original, 'septiembre26', columns,
                        [['001', '2026', '000001', '01/09/2026', '', '000000001', '001', '003', '', '', '']])
            empty = root / 'empty.xlsx'
            write_excel(empty, 'septiembre26', columns, [])
            app = win32com.client.DispatchEx('Excel.Application')
            try:
                app.Visible = False
                app.DisplayAlerts = False
                app.AutomationSecurity = 3
                for path in [*(root / name for name in OUTPUT_NAMES), original, empty]:
                    with self.subTest(path=path.name):
                        book = app.Workbooks.Open(Filename=str(path), UpdateLinks=0, ReadOnly=True,
                                                 IgnoreReadOnlyRecommended=True, CorruptLoad=0)
                        try:
                            # CorruptLoad=0 requests normal loading, not repair
                            # or data extraction. Excel rejects the old layout.
                            self.assertTrue(book.Saved)
                            self.assertEqual(book.Worksheets(1).Name, 'septiembre26')
                            if path == original:
                                self.assertEqual(book.Worksheets(1).Range('A2').Value2, '001')
                                self.assertEqual(book.Worksheets(1).Range('C2').Value2, '000001')
                        finally:
                            book.Close(SaveChanges=False)
            finally:
                app.Quit()
