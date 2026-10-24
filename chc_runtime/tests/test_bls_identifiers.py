"""Entrada BLs con sufijo: identidad textual, firmas antiguas y rechazo estricto."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bots/bls/src'))
import pandas as pd
from core import inputs, store
from config_manager import DEFAULTS
from chc_runtime.bls_identifiers import install_input_support

ORIGINAL = inputs.input_job
install_input_support()


def record(number='0002601287L'):
    return {'IDManifiesto': f'4-1-{number}-P001-13/10/26', 'Secuencia Tica': '003',
            'BL original': '00001234567890123456789', 'Fecha Manifiesto': '13/10/2026', 'Mes': '2026-10'}


class BLSIdentifierTests(unittest.TestCase):
    def test_suffix_preserves_text_key_and_derived_fields_even_after_store_preload(self):
        job = store.input_job(record(), 7)
        self.assertFalse(job['error'], job)
        self.assertEqual(job['key'], ORIGINAL(record(), 7)['key'])
        self.assertEqual(job['record']['IDManifiesto'], record()['IDManifiesto'])
        self.assertEqual(job['record']['ID3'], '0002601287L')
        self.assertEqual(job['record']['BL original'], record()['BL original'])
        self.assertEqual(job['record']['Secuencia Tica'], '003')
        self.assertNotEqual(job['key'], inputs.input_job(record('0002601287'), 7)['key'])
        install_input_support()
        self.assertEqual(store.input_job(record(), 7), job)

    def test_numeric_jobs_and_batch_signatures_remain_identical(self):
        for number in ('0002601287', '1', '20260001'):
            with self.subTest(number=number):
                row = record(number)
                self.assertEqual(inputs.input_job(row, 1), ORIGINAL(row, 1))
                data = pd.DataFrame([row])
                actual = inputs.batch_scope(data, DEFAULTS)
                with patch.object(inputs, 'input_job', ORIGINAL):
                    expected = inputs.batch_scope(data, DEFAULTS)
                self.assertEqual(actual, expected)

    def test_unknown_number_formats_are_still_rejected(self):
        for number in ('L2601287', '260L1287', '2601287LL', '2601287 L', '2601287/', '2601287é', ''):
            with self.subTest(number=number):
                self.assertTrue(inputs.input_job(record(number), 1)['error'])
        self.assertFalse(inputs.input_job(record('0002601287l'), 1)['error'])

    def test_suffix_does_not_bypass_bl_sequence_date_mode_or_location_validation(self):
        for changes in ({'BL original': ''}, {'Secuencia Tica': '0'}, {'Secuencia Tica': 'x'},
                        {'Fecha Manifiesto': '14/10/2026'},
                        {'IDManifiesto': '8-1-2601287L-P001-13/10/26'},
                        {'IDManifiesto': '4-1-2601287L-001-13/10/26'},
                        {'IDManifiesto': '4-1-2601287L-P001-32/10/26'}):
            with self.subTest(changes=changes):
                self.assertTrue(inputs.input_job({**record(), **changes}, 1)['error'])


if __name__ == '__main__': unittest.main()
