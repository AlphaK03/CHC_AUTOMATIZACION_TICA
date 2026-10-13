"""Proveedor diario aislado: fuentes originales, SQLite y protocolo JSONL."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
from data_store import MONTHS, REGIMENES, RangeStore, RunLock
from runner import run_downloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--day', required=True, type=date.fromisoformat)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--driver', required=True, type=Path)
    parser.add_argument('--visible', action='store_true')
    parser.add_argument('--offline-fixture', action='store_true')
    args = parser.parse_args()
    if args.offline_fixture and args.database.resolve().is_relative_to(HERE.parents[1] / 'bots' / 'detalles' / 'data'):
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
    try:
        pending = run_downloads(
            args.database, config, REGIMENES, MONTHS[args.day.month - 1], args.day.year,
            'Rango personalizado', lambda message: emit('log', message=message), cancelled,
            start=args.day.day, end=args.day.day, **({'factory': factory} if factory else {}))
        if cancelled.is_set():
            emit('result', complete=False, stopped=True, message='Descarga detenida.')
            return 0
        with RunLock(args.database):
            store = RangeStore(args.database)
            try:
                lists, missing = store.collect(args.day.strftime('%Y-%m'), [(args.day.day, args.day.day)])
            finally:
                store.close()
        emit('result', complete=not pending and not missing, duas=lists[0] if not missing else [],
             message='; '.join(missing))
        return 0
    except Exception as error:
        emit('result', complete=False, fatal=True, message=str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
