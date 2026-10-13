"""Registrar en la instalación nueva la muestra validada, sin repetir consultas."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'bots' / 'detalles'
sys.path.insert(0, str(BOT / 'src'))
from core.catalog import TableCatalog
from core.job_store import JobStore, RunLock
from flows.detalles_flow import DetallesFlow
import utils


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-storage', type=Path, required=True)
    args = parser.parse_args()
    source = args.source_storage.resolve()
    if not source.is_relative_to((ROOT / 'runtime' / 'details_validation').resolve()):
        raise ValueError('Se admite únicamente la muestra aislada de esta validación.')
    report = json.loads((source / 'report.json').read_text(encoding='utf-8'))
    if not report.get('ok') or report.get('confirmed_rows') != 2:
        raise ValueError('La muestra no tiene dos resultados validados.')
    origin = sqlite3.connect((source / 'data' / 'queues' / 'catalog.sqlite3').as_uri() + '?mode=ro', uri=True)
    origin.row_factory = sqlite3.Row
    try:
        records = [dict(row) for row in origin.execute('SELECT * FROM saved_tables WHERE deleted=0')]
    finally:
        origin.close()
    if len(records) != 1:
        raise ValueError('La validación debe contener exactamente una tabla.')
    record = records[0]
    catalog = TableCatalog(BOT / 'data' / 'queues')
    destination = catalog.database(record)
    if destination.exists() or catalog.find_by_name(record['name']):
        raise ValueError('La tabla de prueba ya existe; no se sobrescribe.')
    source_db = (source / 'data' / 'queues' / record['filename']).resolve()
    if source_db.parent != (source / 'data' / 'queues').resolve():
        raise ValueError('Archivo fuera de la validación.')
    with RunLock(destination):
        read = sqlite3.connect(source_db.as_uri() + '?mode=ro', uri=True)
        write = sqlite3.connect(destination)
        try:
            read.backup(write)
        finally:
            write.close()
            read.close()
        with catalog.connection() as db:
            columns = list(record)
            db.execute('INSERT INTO saved_tables (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')',
                       [record[key] for key in columns])
        config = utils.load_machine_config()
        if not config.get('output_base_path'):
            config['output_base_path'] = str(BOT / 'output')
            utils.save_machine_config(config)
        session = utils.load_session()
        session.update(active_table_id=record['id'], input_file_path=record['source_path'], sheet_name=record['source_sheet'])
        utils.save_session(session)
        store = JobStore(destination)
        try:
            paths = utils.compute_output_paths(config['output_base_path'], record['output_name'], table_id=record['id'])
            store.export(paths, list(DetallesFlow().extract_data('').columns))
        finally:
            store.close()
    print('Muestra instalada: 2 DUAs reales confirmados, historial y exportaciones conservados. Sin consultas adicionales.')


if __name__ == '__main__':
    main()
