"""Descarga BLs o exporta sus resultados confirmados sin abrir la interfaz."""
import argparse
import json
import logging
from pathlib import Path
from threading import Event

from config_manager import load_config
from core.engine import BLSProcessor
from core.store import export_saved
from input_files import load_input_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archivo', help='Excel .xlsx o base de entrada SQLite del bot')
    parser.add_argument('--hoja', help='BLS por defecto en Excel; hoja guardada en SQLite')
    parser.add_argument('--limite', type=int)
    parser.add_argument('--salida', required=True)
    parser.add_argument('--concurrencia', type=int, default=2, choices=range(1, 21))
    parser.add_argument('--intentos', type=int, default=3, choices=range(1, 11))
    parser.add_argument('--detalle', choices=('http', 'browser'), default='http')
    parser.add_argument('--contexto-nuevo', action='store_true')
    parser.add_argument('--exportar-db')
    args = parser.parse_args()
    if args.exportar_db:
        path = Path(args.exportar_db).resolve()
        print(json.dumps({'exported': export_saved(path, args.salida), 'database': str(path),
                          'csv': str(Path(args.salida).resolve())}, ensure_ascii=False))
        return
    if not args.archivo:
        parser.error('Indique --archivo o --exportar-db')
    if args.limite is not None and args.limite < 1:
        parser.error('--limite debe ser positivo')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = load_config()
    try:
        data = load_input_file(args.archivo, args.hoja)
    except Exception as exc:
        parser.error(str(exc))
    config.update(sheet_name=data.attrs['sheet_name'], output_base_path=args.salida, cant_hilos=args.concurrencia,
                  max_retries=args.intentos, detail_strategy=args.detalle,
                  reuse_context=not args.contexto_nuevo, dates_from_input=True, headless=True,
                  timeout=max(15, config.get('timeout', 30)))
    if args.limite:
        data = data.head(args.limite)
    stop = Event()
    processor = BLSProcessor(config, stop)
    try:
        result = processor.run(data)
    except KeyboardInterrupt:
        stop.set()
        raise
    print(json.dumps({**result, **processor.stats}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
