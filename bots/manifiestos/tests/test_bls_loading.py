import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bls_base import (BuildCancelled, catalog_sources, choose_candidates,
                      discover_sources, inspect_sources)
from conocimientos import COLUMNS, KnowledgeStore
from resultados import output_paths

JAN = '1-0-20240739-P027-02/01/25'


class LoadingTests(unittest.TestCase):
    def test_catalog_reads_only_names_and_filters_managed_periods_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            jan = output_paths({'output_manifest_conocimientos_folder':folder}, 'conocimientos','maritimo',1,2025)
            feb = output_paths({'output_manifest_conocimientos_folder':folder}, 'conocimientos','aereo',2,2025)
            for paths in (jan, feb):
                paths.csv.write_bytes(b'not read at catalog time')
                paths.database.write_bytes(b'not a database; do not open')
            historical = jan.period/'historicos'/('conocimientos_maritimo_enero25_historico_old.csv')
            historical.parent.mkdir()
            historical.write_bytes(b'old data')
            with patch.object(Path, 'open', side_effect=AssertionError('El catálogo abrió datos')):
                catalog, errors = catalog_sources([root])
            self.assertFalse(errors)
            self.assertEqual(len(catalog),4)
            selected = choose_candidates(catalog,year=2025,month=1,mode='maritimo')
            self.assertEqual([c.path for c in selected], [jan.database.resolve()])
            self.assertNotIn(historical.resolve(), {c.path for c in catalog})
            catalog, _ = catalog_sources([root], include_history=True)
            self.assertIn(historical.resolve(), {c.path for c in catalog})

    def test_preferred_loading_never_reads_exported_csv_or_old_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = output_paths({'output_manifest_conocimientos_folder':folder}, 'conocimientos','maritimo',1,2025)
            store = KnowledgeStore(paths.csv, {}, db_path=paths.database)
            store.save(JAN,1,[[JAN,'001','000123','N']+['']*(len(COLUMNS)-4)],{'kept':1})
            store.close()
            paths.csv.write_bytes(b'\xff invalid CSV that must not be read')
            old = paths.period/'historicos/conocimientos_maritimo_enero25_historico_old.csv'
            old.parent.mkdir()
            old.write_bytes(b'\xff old CSV that must not be read')
            sources, errors = discover_sources([folder],include_history=False,prefer_sqlite=True)
            self.assertFalse(errors)
            self.assertEqual([(s.kind,s.rows) for s in sources],[('SQLite',1)])

    def test_external_mixed_file_is_not_discarded_by_misleading_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'conocimientos_maritimo_2024_12.csv'
            with path.open('w',newline='',encoding='utf-8') as stream:
                writer=csv.writer(stream)
                writer.writerow(COLUMNS)
                writer.writerow([JAN,'001','000123','N']+['']*(len(COLUMNS)-4))
            catalog, _ = catalog_sources([path])
            chosen = choose_candidates(catalog,year=2025,month=1,mode='maritimo')
            self.assertEqual([c.path for c in chosen],[path.resolve()])
            sources, errors = discover_sources([c.path for c in chosen])
            self.assertFalse(errors)
            self.assertEqual(sources[0].periods[0].key,('2025-01','maritimo'))

    def test_stop_interrupts_sqlite_aggregation_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.sqlite3'
            store = KnowledgeStore(Path(folder)/'source.csv', {}, db_path=path)
            store.save(JAN,1,[[JAN,str(n),'000123','N']+['']*(len(COLUMNS)-4)
                             for n in range(5000)],{'kept':5000})
            store.close()
            before = path.read_bytes()
            class StopDuringQuery:
                calls=0
                def is_set(self):
                    self.calls+=1
                    return self.calls>=3
            stop=StopDuringQuery()
            with self.assertRaises(BuildCancelled):
                inspect_sources(path,stop=stop)
            self.assertGreaterEqual(stop.calls,3)
            self.assertEqual(path.read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
