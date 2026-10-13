"""Prueba real explícita, limitada a dos DUAs del original en instalación aislada."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'workbench'))
sys.path.insert(0, str(ROOT / 'workbench' / 'tests'))
from test_details_bridge import APP, wait_until
from details_bridge import DetailsBridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--sample', type=Path, default=ROOT / 'runtime' / 'details_validation' / 'sample')
    args = parser.parse_args()
    reference = json.loads((args.sample / 'referencia.json').read_text(encoding='utf-8'))
    if len(reference['expected']) != 2:
        raise ValueError('La muestra debe contener exactamente dos DUAs.')
    storage = ROOT / 'runtime' / 'details_validation' / ('live-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    if storage.exists():
        raise ValueError('No se reutiliza una instalación para esta prueba real.')
    bridge = DetailsBridge(storage_root=storage)
    events = []
    bridge.eventReceived.connect(events.append)
    bridge.eventReceived.connect(lambda event: print(event['message'], flush=True) if event['event'] == 'log' else None)

    def call(command, data=None, timeout=45000):
        start = len(events)
        if not bridge._send(command, data):
            raise RuntimeError(bridge.error)
        wait_until(lambda: not bridge.busy, timeout=timeout)
        results = [event for event in events[start:] if event['event'] in {'result', 'error'}]
        if not results or results[-1]['event'] == 'error':
            raise RuntimeError(bridge.error)
        return results[-1]

    report = {'storage_root': str(storage), 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'input_duas': list(reference['expected']), 'portal_queries_limit': 2, 'max_retries': 1, 'workers': 1}
    try:
        bridge.connectModule()
        wait_until(lambda: bridge.ready or bool(bridge.error))
        if not bridge.ready:
            raise RuntimeError(bridge.error)
        wait_until(lambda: not bridge.busy)
        call('configure', {'config': {'output_base_path': str(storage / 'output'), 'cant_hilos': 1, 'max_retries': 1, 'timeout': 30}})
        prepared = call('prepare_import', {'source': str((args.sample / 'muestra_original.xlsx').resolve()),
                                          'sheet': 'muestra_original', 'name': 'Validación · 2 DUAs originales'})['importPlan']
        call('import', prepared)
        if bridge.summary['total'] != 2:
            raise ValueError('La tabla no contiene exactamente dos DUAs; no se ejecutará.')
        result = call('run', timeout=240000)
        report['summary'] = bridge.summary
        report['run_status'] = result['runStatus']
        if bridge.summary['attempts'] > 2:
            raise AssertionError('Se excedió el límite de dos intentos.')
        csv_path = next(Path(bridge.outputFolder).glob('Detalles_DUAs_*.csv'))
        with csv_path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            report['columns'] = reader.fieldnames
            actual = {row['numero_del_dua']: row for row in reader}
        report['confirmed_rows'] = len(actual)
        report['field_differences'] = {dua: [key for key in expected if actual.get(dua, {}).get(key) != str(expected[key])]
                                       for dua, expected in reference['expected'].items()}
        report['source_still_unchanged'] = hashlib.sha256(Path(reference['source_database']).read_bytes()).hexdigest() == reference['source_sha256_before']
        report['output_csv'] = str(csv_path)
        report['ok'] = len(actual) == 2 and len(report['columns']) == 38 and not any(report['field_differences'].values())
        if len(actual) == 2:
            # Con el lote completo, volver a ejecutar solo exporta; no consulta.
            before = bridge.summary['attempts']
            call('run', timeout=45000)
            report['no_repeat_after_resume'] = bridge.summary['attempts'] == before
    except Exception as error:
        report['ok'] = False
        report['error'] = str(error)
    finally:
        bridge.shutdown()
        wait_until(lambda: bridge.isClosed, timeout=45000)
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        storage.mkdir(parents=True, exist_ok=True)
        (storage / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({key: value for key, value in report.items() if key != 'columns'}, ensure_ascii=False, indent=2), flush=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
