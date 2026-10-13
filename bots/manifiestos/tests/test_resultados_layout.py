import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from conocimientos import KnowledgeStore, GridPage
from tablas_manifiesto import ManifestTableStore
from resultados import (MONTHS, FLOWS, output_paths, csv_for_database, csv_name,
                        parse_result_name, exclusion_csv_path, location_file)
from organizar_resultados import organize_results, checksum
from limpiar_resultados import clean_duplicate_results
from conocimientos_queue import OutputLock
from bls_base import default_roots, default_selection, inspect_sources

MID = '1-0-00000024-P027-01/01/26'


def legacy_store(root, flow='conocimientos', month=1, mode='maritimo'):
    folder = root/'resultados'/flow/'2026'/f'{month:02d}'/mode
    name = f'{flow}_{mode}_2026_{month:02d}'
    csv_path = folder/'CSV'/(name+'.csv')
    db_path = folder/'SQLite'/(name+'.sqlite3')
    scope = {'flow':flow, 'year':2026, 'month':month, 'mode':mode, 'version':1}
    cls = KnowledgeStore if flow == 'conocimientos' else ManifestTableStore
    return cls(csv_path, scope, db_path=db_path)


class ResultLayoutTests(unittest.TestCase):
    def test_previous_flat_layout_keeps_history_name_and_database_bytes(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            root = Path(folder)
            paths = output_paths({}, 'conocimientos', 'maritimo', 1, 2026)
            store = KnowledgeStore(paths.csv, {}, db_path=paths.database)
            store.close()
            before = checksum(paths.database)
            old = root/'resultados/2026/maritimo'
            old.mkdir(parents=True)
            name = 'conocimientos_maritimo_enero26_historico_1234567890.csv'
            (old/name).write_bytes(b'unique historic data')
            organize_results({})
            self.assertEqual((paths.period/'historicos'/name).read_bytes(), b'unique historic data')
            self.assertEqual(checksum(paths.database), before)
            self.assertEqual(csv_for_database(paths.database), paths.csv)
            self.assertEqual(organize_results({}), [])

    def test_cleanup_preserves_unique_values_and_legitimate_row_multiplicity(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            paths = output_paths({}, 'duas', 'aereo', 1, 2026)
            def write(path, rows):
                with path.open('w', encoding='utf-8-sig', newline='') as stream:
                    csv.writer(stream).writerows([['index_flujo_duas', 'BL'], *rows])
            write(paths.csv, [[1, '000123'], [2, '000123'], [3, '000124']])
            subset = paths.csv.with_name(paths.csv.stem+'_historico_subset.csv')
            write(subset, [[91, '000123']])
            unique = paths.csv.with_name(paths.csv.stem+'_historico_unique.csv')
            write(unique, [[1, '123']])
            repeated = paths.csv.with_name(paths.csv.stem+'_historico_repeated.csv')
            write(repeated, [[1, '000123'], [2, '000123'], [3, '000123']])
            identical = paths.csv.with_name(paths.csv.stem+'_historico_identical.csv')
            identical.write_bytes(paths.csv.read_bytes())
            before = paths.csv.read_bytes()
            preview = clean_duplicate_results({}, apply=False)
            self.assertEqual(len([r for r in preview if r['state']=='Previsto']), 2)
            self.assertTrue(subset.exists())
            result = clean_duplicate_results({}, apply=True)
            self.assertEqual(len([r for r in result if r['state']=='Eliminado']), 2)
            self.assertFalse(subset.exists())
            self.assertFalse(identical.exists())
            self.assertTrue(unique.exists())
            self.assertTrue(repeated.exists())
            self.assertEqual(paths.csv.read_bytes(), before)

    def test_cleanup_defers_active_period_and_only_removes_empty_old_control(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            paths = output_paths({}, 'conocimientos', 'maritimo', 1, 2026)
            paths.csv.write_bytes(b'BL\n0001\n')
            copy = paths.csv.with_name(paths.csv.stem+'_historico_copy.csv')
            copy.write_bytes(paths.csv.read_bytes())
            empty = paths.period/'conocimientos_fallidos_maritimo_enero26_historico_empty.csv'
            empty.write_bytes(b'IDManifiesto,fila_origen,motivo_fallo\n')
            required = paths.period/'duas_excluidas_maritimo_enero26.csv'
            required.write_bytes(b'IDManifiesto,motivo\n')
            lock = OutputLock(str(paths.database)+'.lock')
            try:
                result = clean_duplicate_results({}, apply=True)
                self.assertTrue(any(r['state']=='Pospuesto' for r in result))
                self.assertTrue(copy.exists())
                self.assertTrue(empty.exists())
            finally:
                lock.close()
            clean_duplicate_results({}, apply=True)
            self.assertFalse(copy.exists())
            self.assertFalse(empty.exists())
            self.assertTrue(required.exists())

    def test_month_names_and_variants_round_trip_for_every_flow(self):
        self.assertEqual(parse_result_name('manifiestos_aereo_2026_02_.csv'),
                         ('tabla','aereo',2,2026,''))
        for flow in FLOWS:
            for month in range(1,13):
                for qualifier in ('','excluidas','fallidos','estado'):
                    name = csv_name(flow,'maritimo',month,2026,qualifier)
                    self.assertIn(MONTHS[month-1]+'26', name)
                    self.assertEqual(parse_result_name(name), (flow,'maritimo',month,2026,qualifier))

    def test_flat_csv_and_private_database_locations_are_portable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'first'
            with patch('resultados.PROJECT_ROOT', root):
                paths = output_paths({},'conocimientos','maritimo',1,2026)
                self.assertEqual(paths.csv, root/'resultados/conocimientos/2026/maritimo/conocimientos_maritimo_enero26.csv')
                self.assertFalse(paths.database.is_relative_to(root/'resultados'))
                self.assertEqual(csv_for_database(paths.database), paths.csv)
                store = KnowledgeStore(paths.csv, {}, db_path=paths.database)
                store.close()
            moved = Path(folder)/'second'
            shutil.copytree(root, moved)
            database = moved / paths.database.relative_to(root)
            self.assertEqual(csv_for_database(database), moved / paths.csv.relative_to(root))
            reopened = KnowledgeStore.open_existing(database)
            self.assertEqual(reopened.csv_path, moved / paths.csv.relative_to(root))
            reopened.close()

    def test_migration_preserves_saved_pending_partial_pages_and_resume(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            root = Path(folder)
            store = legacy_store(root)
            pending = MID.replace('00000024','00000025')
            partial = MID.replace('00000024','00000026')
            store.prepare_selection([(1,'url',{},MID),(2,'url',{},pending),(3,'url',{},partial)])
            store.start_run()
            store.claim(MID)
            row = [MID,'001','0000123','N'] + ['']*11
            store.save(MID,1,[row],{'pages':1,'read':1,'kept':1})
            store.claim(pending)
            store.fail(pending,2,'network')
            store.claim(partial)
            page = GridPage({}, {}, [[partial,'1','0000004','N']+['']*11],0,False)
            store.save_checkpoint(partial,page)
            store.export()
            old_db, old_csv = store.db_path, store.csv_path
            store.close()
            before_db, before_csv = checksum(old_db), checksum(old_csv)
            records = organize_results({})
            self.assertFalse(any(r['state']=='Pospuesto' for r in records))
            paths = output_paths({},'conocimientos','maritimo',1,2026)
            self.assertEqual(checksum(paths.database), before_db)
            self.assertEqual(checksum(paths.csv), before_csv)
            self.assertFalse(old_db.exists())
            self.assertTrue(location_file(paths.database).exists())
            store = KnowledgeStore.open_existing(paths.database)
            store.start_run()
            self.assertEqual([job['state'] for job in store.jobs()], ['Guardado','Pendiente','Pendiente'])
            self.assertEqual(store.load_checkpoint(partial)[0].rows, page.rows)
            self.assertEqual(store.job(MID)['attempts'],1)
            store.export()
            store.close()
            self.assertEqual(checksum(paths.csv),before_csv)
            self.assertEqual(organize_results({}),[])
            self.assertTrue(all(p.suffix=='.csv' for p in (root/'resultados').rglob('*') if p.is_file()))
            sources = inspect_sources(paths.csv) + inspect_sources(paths.database)
            self.assertFalse(default_selection(sources)[sources[0].key])
            self.assertIn(paths.database.parents[2], default_roots({}))

    def test_active_group_is_postponed_then_moved_with_latest_progress(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            root = Path(folder)
            store = legacy_store(root)
            store.prepare_selection([(20,'url',{},MID)])
            store.start_run()
            store.claim(MID)
            old_db, old_csv = store.db_path, store.csv_path
            records = organize_results({})
            self.assertTrue(any(r['state']=='Pospuesto' for r in records))
            self.assertTrue(old_db.exists())
            self.assertFalse(output_paths({},'conocimientos','maritimo',1,2026).database.exists())
            store.save(MID,1,[[MID,'001','0000007','N']+['']*11],{'pages':1,'read':1,'kept':1})
            store.finish_run(1)
            store.export()
            store.close()
            self.assertFalse(any(r['state']=='Pospuesto' for r in organize_results({})))
            paths = output_paths({},'conocimientos','maritimo',1,2026)
            resumed = KnowledgeStore.open_existing(paths.database)
            self.assertTrue(resumed.completed(MID))
            self.assertEqual(resumed.job(MID)['attempts'],1)
            resumed.close()
            self.assertFalse(old_db.exists())
            self.assertFalse(old_csv.exists())

    def test_exclusions_persist_and_export_both_standardized_csvs(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            store = legacy_store(Path(folder), 'duas')
            store.prepare_selection([(20,'url',{},MID)])
            store.start_run()
            store.claim(MID)
            store.exclude(MID,1,'frmAmbiente')
            store.finish_run(1)
            store.export()
            store.close()
            organize_results({})
            paths = output_paths({},'duas','maritimo',1,2026)
            store = KnowledgeStore.open_existing(paths.database)
            self.assertEqual(store.job(MID)['state'],'Excluido')
            store.export()
            store.close()
            self.assertEqual(exclusion_csv_path(paths.csv).name,'duas_excluidas_maritimo_enero26.csv')
            self.assertEqual(exclusion_csv_path(paths.csv).parent, paths.period/'fallidos')
            self.assertTrue(paths.csv.exists())
            self.assertEqual(organize_results({}), [])
            with exclusion_csv_path(paths.csv).open(encoding='utf-8-sig',newline='') as stream:
                self.assertEqual(list(csv.DictReader(stream))[0]['IDManifiesto'],MID)

    def test_historical_csvs_and_auxiliary_files_are_preserved_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            root = Path(folder)
            store = legacy_store(root)
            store.save(MID,1,[[MID,'1','00001','N']+['']*11],{'pages':1})
            store.export()
            canonical = store.csv_path.read_bytes()
            store.close()
            old = root/'resultados/conocimientos/historicos/conocimientos_maritimo_2026_01.csv'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'old CSV with 000001\r\n')
            report = root/'resultados/organizacion/report.json'
            report.parent.mkdir()
            report.write_text('{}')
            xlsx = root/'resultados/bases_bls/example.xlsx'
            xlsx.parent.mkdir()
            xlsx.write_bytes(b'original workbook bytes')
            organize_results({})
            paths = output_paths({},'conocimientos','maritimo',1,2026)
            self.assertEqual(paths.csv.read_bytes(),canonical)
            historical = list((paths.period/'historicos').glob('*_historico_*.csv'))
            self.assertEqual(len(historical),1)
            self.assertEqual(historical[0].read_bytes(),b'old CSV with 000001\r\n')
            self.assertTrue((root/'bases_bls/example.xlsx').exists())
            self.assertTrue(all(p.suffix=='.csv' for p in (root/'resultados').rglob('*') if p.is_file()))
            self.assertEqual(organize_results({}),[])

    def test_rename_failure_rolls_back_the_group(self):
        with tempfile.TemporaryDirectory() as folder, patch('resultados.PROJECT_ROOT', Path(folder)):
            root = Path(folder)
            store = legacy_store(root)
            store.save(MID,1,[[MID,'1','00001','N']+['']*11],{'pages':1})
            store.export()
            old_db, old_csv = store.db_path, store.csv_path
            store.close()
            rename = Path.rename
            def fail_database(source,destination):
                if source == old_db:
                    raise PermissionError('file in use')
                return rename(source,destination)
            with patch.object(Path,'rename',fail_database):
                records = organize_results({},only=('conocimientos','maritimo',1,2026))
            self.assertEqual(records[0]['state'],'Pospuesto')
            self.assertTrue(old_db.exists())
            self.assertTrue(old_csv.exists())
            self.assertFalse(output_paths({},'conocimientos','maritimo',1,2026).csv.exists())
