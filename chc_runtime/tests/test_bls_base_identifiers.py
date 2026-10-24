"""Generador de Manifiestos en su propio proceso; fuentes siempre temporales."""
from contextlib import closing
import csv
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bots/manifiestos/src'))
import bls_base
from conocimientos import COLUMNS
from chc_runtime.bls_identifiers import install_base_support
from chc_runtime.knowledge_fixture import create
from chc_runtime.knowledge_source import KnowledgeSource

ORIGINAL = bls_base.normalize_record
install_base_support()


def record(number='0002601287L', sequence='003', bl='00001234567890123456789'):
    return {'IDManifiesto': f'4-1-{number}-P001-13/10/26', 'Secuencia Tica': sequence,
            'BL original': bl, 'Courier': 'N'}


class BaseIdentifierTests(unittest.TestCase):
    def test_original_numeric_normalization_and_suffix_text_are_preserved(self):
        numeric = record('0002601287')
        self.assertEqual(bls_base.normalize_record(numeric), ORIGINAL(numeric))
        normalized = bls_base.normalize_record(record())
        self.assertEqual(normalized[:4], (record()['IDManifiesto'], 3, '003', record()['BL original']))
        self.assertEqual(normalized[-1], 2601287)
        parts, day = bls_base.manifest_identity(record()['IDManifiesto'])
        self.assertEqual(parts[2], '0002601287L')
        self.assertEqual(day.isoformat(), '2026-10-13')
        install_base_support()
        self.assertEqual(bls_base.normalize_record(record()), normalized)
        for row in (record('2601287LL'), record('260L1287'), record(sequence='0'), record(bl='')):
            with self.subTest(row=row), self.assertRaises(ValueError):
                bls_base.normalize_record(row)

    def test_automatic_base_with_numeric_and_suffix_keeps_courier_and_sources_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = [create(root, 'air', mode='aereo', number='0002601287L'),
                     create(root, 'sea', number='0002601287')]
            hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            source = KnowledgeSource(root, Event(), lambda *args, **kwargs: None)
            result = source.build(['2026-09|maritimo', '2026-09|aereo'])
            self.assertEqual((result['stats']['invalid'], result['stats']['conflicts'], result['stats']['exported']), (0, 0, 2))
            with closing(sqlite3.connect(Path(result['output']).as_uri()+'?mode=ro', uri=True)) as db:
                rows = db.execute('SELECT * FROM BLS').fetchall()
            self.assertEqual({r[0].split('-')[2] for r in rows}, {'0002601287', '0002601287L'})
            self.assertTrue(all(r[2] == '00001234567890123456789' for r in rows))
            self.assertTrue(source.build(['2026-09|maritimo', '2026-09|aereo'])['reused'])
            self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, hashes)

    def test_manual_base_keeps_distinct_suffixes_duplicates_and_conflicts_audited(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            incoming = root/'conocimientos.csv'
            rows = [record(), record(), record('0002601287'), record('0002601287M'),
                    record('0002601287M', bl='999'), record('0002601287LL')]
            with incoming.open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(COLUMNS)
                writer.writerows([[r.get(c, '') for c in COLUMNS] for r in rows])
            sources = bls_base.inspect_sources(incoming)
            self.assertEqual({p.key for s in sources for p in s.periods}, {('2026-10', 'aereo')})
            stats = bls_base.build_base(sources, root/'base.sqlite3', audit_dir=root/'audit')
            self.assertEqual((stats['duplicates'], stats['conflicts'], stats['invalid'], stats['exported']), (1, 1, 1, 2))
            with closing(sqlite3.connect((root/'base.sqlite3').as_uri()+'?mode=ro', uri=True)) as db:
                ids = {r[0] for r in db.execute('SELECT IDManifiesto FROM BLS')}
            self.assertEqual(ids, {record()['IDManifiesto'], record('0002601287')['IDManifiesto']})


if __name__ == '__main__': unittest.main()
