"""Compara cuatro estrategias con un máximo de cuatro BL y dos rondas alternadas."""
import argparse
import asyncio
import csv
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core.engine import BLSProcessor
from data_reader import leer_bls


async def benchmark(args):
    data = leer_bls(args.archivo, 'BLS').head(args.limite)
    folder = Path(args.salida).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    strategies = [('nuevo_navegador_1', False, 'browser', 1),
                  ('reutilizado_navegador_1', True, 'browser', 1),
                  ('reutilizado_http_1', True, 'http', 1),
                  ('reutilizado_http_2', True, 'http', 2)]
    reports, reference = [], None
    for round_index in range(2):
        order = strategies if round_index == 0 else list(reversed(strategies))
        for name, reuse, detail, workers in order:
            config = {'sheet_name': 'BLS', 'output_base_path': str(folder / f'ronda_{round_index + 1}' / name),
                      'cant_hilos': workers, 'max_retries': 1, 'headless': True, 'timeout': 30,
                      'dates_from_input': True, 'reuse_context': reuse, 'detail_strategy': detail}
            processor = BLSProcessor(config, Event())
            started = time.perf_counter()
            result = await processor.run_async(data)
            elapsed = time.perf_counter() - started
            report = {'strategy': name, 'round': round_index + 1, 'seconds': round(elapsed, 3),
                      **result, **processor.stats}
            if result['pending'] or result['saved'] != len(data):
                report['matches_reference'] = False
            else:
                with Path(result['output_csv']).open(encoding='utf-8-sig', newline='') as stream:
                    rows = list(csv.reader(stream))
                if reference is None:
                    reference = rows
                report['matches_reference'] = rows == reference
            reports.append(report)
            print(json.dumps(report, ensure_ascii=True), flush=True)
            (folder / 'comparacion.json').write_text(json.dumps({'sample_rows': len(data), 'runs': reports},
                ensure_ascii=False, indent=2), encoding='utf-8')
    summary = [{'strategy': name, 'median_seconds': round(statistics.median(r['seconds'] for r in reports if r['strategy'] == name), 3),
                'all_rows_equal': all(r['matches_reference'] for r in reports if r['strategy'] == name),
                'contexts': [r['contexts_created'] for r in reports if r['strategy'] == name],
                'browser_requests': [r['browser_requests'] for r in reports if r['strategy'] == name],
                'http_requests': [r['http_requests'] for r in reports if r['strategy'] == name]}
               for name, _, _, _ in strategies]
    (folder / 'comparacion.json').write_text(json.dumps({'sample_rows': len(data), 'runs': reports, 'summary': summary},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archivo', required=True)
    parser.add_argument('--salida', required=True)
    parser.add_argument('--limite', type=int, default=4, choices=range(1, 5))
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(benchmark(parser.parse_args()))
