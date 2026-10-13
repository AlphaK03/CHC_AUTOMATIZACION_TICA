"""Ejecuta Conocimientos, DUAs o Movimientos, con salida organizada y reanudación."""
import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from playwright.async_api import async_playwright

from manifest_scraper import ManifestScraper
from utils import load_config
from conocimientos import KnowledgeStore, DEFAULT_CONCURRENCY, validate_concurrency
from resultados import failure_csv_path, output_paths


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--procedimiento', choices=('conocimientos', 'duas', 'movimientos'), default='conocimientos')
    parser.add_argument('--modalidad', choices=ManifestScraper.MODE_MAP, default='aereo')
    parser.add_argument('--mes', type=int, choices=range(1, 13))
    parser.add_argument('--ano', type=int)
    parser.add_argument('--desde', help='Fecha inicial YYYY-MM-DD, dentro del mes')
    parser.add_argument('--hasta', help='Fecha final YYYY-MM-DD, dentro del mes')
    parser.add_argument('--manifiesto', action='append', help='ID completo; se puede repetir')
    parser.add_argument('--limite', type=int, help='Primeros N manifiestos de la selección')
    parser.add_argument('--courier', choices=('N', 'S', 'todos'), default='todos')
    parser.add_argument('--concurrencia', type=validate_concurrency,
                        help='Descargas simultáneas (1 a 32; por defecto, config.json)')
    parser.add_argument('--salida', type=Path, help='Carpeta de trabajo con resultados CSV y datos_app separados')
    parser.add_argument('--solo-sqlite', action='store_true', help='Guardar sin exportar CSV al terminar')
    parser.add_argument('--exportar-db', type=Path, help='Exportar un SQLite existente sin descargar')
    parser.add_argument('--visible', action='store_true')
    args = parser.parse_args()
    if args.concurrencia is None:
        args.concurrencia = load_config().get(args.procedimiento + '_concurrencia', DEFAULT_CONCURRENCY if args.procedimiento == 'conocimientos' else 4)
    if args.procedimiento != 'conocimientos' and args.courier != 'todos':
        parser.error('--courier solo aplica a Conocimientos')
    if not args.exportar_db and (args.mes is None or args.ano is None or args.salida is None):
        parser.error('Indique --mes, --ano y --salida, o utilice --exportar-db')
    return args


async def run(args):
    if args.exportar_db:
        store = KnowledgeStore.open_existing(args.exportar_db)
        try:
            failed = failure_csv_path(store.csv_path)
            store.export(failed)
            print(f'Exportado: {store.csv_path}')
        finally:
            store.close()
        return
    args.salida = args.salida.resolve()
    args.salida.mkdir(parents=True, exist_ok=True)
    config = load_config()
    prefix = args.procedimiento
    config.update({
        'output_manifest_' + prefix + '_folder': str(args.salida),
        prefix + '_fecha_inicio': args.desde, prefix + '_fecha_fin': args.hasta,
        prefix + '_manifest_ids': args.manifiesto,
        prefix + '_limite_manifiestos': args.limite,
        prefix + '_concurrencia': args.concurrencia,
        prefix + '_exportar_csv': not args.solo_sqlite,
    })
    if prefix == 'conocimientos':
        config['conocimientos_courier'] = None if args.courier == 'todos' else args.courier
    paths = output_paths(config, prefix, args.modalidad, args.mes, args.ano)
    log_folder = paths.private_period / 'logs'
    log_folder.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[
        logging.StreamHandler(), logging.FileHandler(log_folder / (prefix + '.log'), encoding='utf-8')])
    started = time.perf_counter()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.visible)
        scraper = ManifestScraper(config, browser, request_factory=pw.request)
        try:
            if prefix == 'conocimientos':
                await scraper.run_conocimientos_for_mode(args.modalidad, args.mes, args.ano)
            else:
                await scraper.run_tracked_table(prefix, args.modalidad, args.mes, args.ano)
            report = {'seconds': round(time.perf_counter() - started, 3),
                      'summary': scraper.conoc_summary, 'progress': scraper.conoc_progress,
                      'extracted': scraper.conoc_stats}
            report_path = log_folder / ('resultado_' + time.strftime('%Y%m%d_%H%M%S') + '.json')
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(run(arguments()))
