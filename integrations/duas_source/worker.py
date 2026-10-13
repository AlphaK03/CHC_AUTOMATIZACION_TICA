"""Proveedor diario aislado: fuentes originales, SQLite y protocolo JSONL."""
import argparse
from contextlib import contextmanager, nullcontext
from datetime import date
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
from data_store import MONTHS, REGIMENES, REGIMENES_IMPORTACION, RangeStore, RunLock
from runner import run_downloads


@contextmanager
def import_cache_gate(database, cancelled, emit):
    """Serializar proveedores permite reutilizar la caché sin consultas duplicadas."""
    announced = False
    while not cancelled.is_set():
        gate = RunLock(str(database) + '.proveedor')
        try:
            gate.__enter__()
        except RuntimeError:
            if not announced:
                emit('log', message='Esperando la base de importación que está preparando otro bot.')
                announced = True
            cancelled.wait(.2)
            continue
        try:
            yield True
        finally:
            gate.__exit__(None, None, None)
        return
    yield False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--day', required=True, type=date.fromisoformat)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--driver', required=True, type=Path)
    parser.add_argument('--visible', action='store_true')
    parser.add_argument('--offline-fixture', action='store_true')
    parser.add_argument('--selection', choices=('total', 'transito', 'importacion'), default='total')
    args = parser.parse_args()
    protected = [HERE.parents[1] / 'bots' / module / 'data' for module in ('detalles', 'duas_transito', 'talon', 'xmovimientos')]
    protected.append(HERE / 'data')
    if args.offline_fixture and any(args.database.resolve().is_relative_to(folder) for folder in protected):
        parser.error('La fixture requiere almacenamiento separado de la instalación normal.')
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    cancelled = threading.Event()
    def listen():
        while True:
            message = os.read(sys.stdin.fileno(), 256)
            if not message or b'stop' in message:
                cancelled.set()
                return
    threading.Thread(target=listen, daemon=True).start()
    def emit(kind, **values):
        print(json.dumps({'event': kind, **values}, ensure_ascii=False), flush=True)
    factory = None
    if args.offline_fixture:
        class LocalExtractor:
            def __init__(self, *a, **kw): pass
            def fetch_range(self, regimen, period, start, end):
                return [{'aduana': '001', 'ano': period[:4], 'numero': f'{start:02}{REGIMENES.index(regimen) + 1:04}'}]
            def close(self): pass
        factory = LocalExtractor
    config = {'edge_driver_path': str(args.driver), 'mostrar_navegador': args.visible}
    regimens = REGIMENES if args.selection == 'total' else ['TRANSITO'] if args.selection == 'transito' else [item for item in REGIMENES if item in REGIMENES_IMPORTACION]
    try:
        with (import_cache_gate(args.database, cancelled, emit) if args.selection == 'importacion' else nullcontext(True)) as acquired:
            if not acquired:
                emit('result', complete=False, stopped=True, message='Descarga detenida.')
                return 0
            pending = run_downloads(
                args.database, config, regimens, MONTHS[args.day.month - 1], args.day.year,
                'Rango personalizado', lambda message: emit('log', message=message), cancelled,
                start=args.day.day, end=args.day.day, **({'factory': factory} if factory else {}))
            if cancelled.is_set():
                emit('result', complete=False, stopped=True, message='Descarga detenida.')
                return 0
            with RunLock(args.database):
                store = RangeStore(args.database)
                try:
                    lists, missing = store.collect(args.day.strftime('%Y-%m'), [(args.day.day, args.day.day)])
                    missing = [message for message in missing if message.partition(':')[0] in regimens]
                finally:
                    store.close()
        selection = 0 if args.selection == 'total' else 1 if args.selection == 'transito' else 2
        emit('result', complete=not pending and not missing, duas=lists[selection] if not missing else [],
             message='; '.join(missing))
        return 0
    except Exception as error:
        emit('result', complete=False, fatal=True, message=str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
