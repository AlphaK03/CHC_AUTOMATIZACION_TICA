"""Genera una base BL unificada usando únicamente salidas locales de Conocimientos."""
import argparse
import json
import re

from bls_base import (available_periods, build_base, default_roots, default_selection,
                      discover_sources, catalog_sources, choose_candidates)
from utils import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--carpeta', action='append', help='Carpeta de entrada; repetible. Por defecto, salidas de la app.')
    parser.add_argument('--ano', type=int, choices=range(2000, 2100))
    parser.add_argument('--mes', type=int, choices=range(1, 13))
    parser.add_argument('--periodo', action='append', help='Mes de arribo AAAA-MM; repetible para unir varios meses.')
    parser.add_argument('--modalidad', choices=('maritimo', 'aereo', 'terrestre'))
    parser.add_argument('--salida', help='Base de destino: XLSX o SQLite (.sqlite3/.sqlite/.db)')
    parser.add_argument('--detectar', action='store_true', help='Solo listar fuentes, sin generar la base')
    parser.add_argument('--listar', action='store_true', help='Listar archivos disponibles sin leer sus datos')
    parser.add_argument('--incluir-historicos', action='store_true', help='Agregar versiones históricas a las entradas')
    parser.add_argument('--formato', choices=('preferir-sqlite','sqlite','csv','excel','todos'), default='preferir-sqlite')
    args = parser.parse_args()
    if not args.detectar and not args.listar and not args.salida:
        parser.error('Indique --salida o use --listar / --detectar')
    if args.periodo and any(not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', period) for period in args.periodo):
        parser.error('--periodo debe tener el formato AAAA-MM')
    catalog, errors = catalog_sources(args.carpeta or default_roots(load_config()),
                                      include_history=args.incluir_historicos)
    kind = {'preferir-sqlite':'preferred','sqlite':'SQLite','csv':'CSV','excel':'XLSX','todos':'all'}[args.formato]
    candidates = choose_candidates(catalog, args.ano, args.mes, args.modalidad, kind)
    if args.periodo:
        candidates = [c for c in candidates if not c.managed or c.period in args.periodo]
    if args.listar:
        print(json.dumps({'files':[{'path':str(c.path),'kind':c.kind,'period':c.period,
            'mode':c.mode,'historical':c.historical} for c in candidates],'errors':errors}, ensure_ascii=False, indent=2))
        return
    sources, read_errors = discover_sources([c.path for c in candidates], include_history=args.incluir_historicos)
    errors += read_errors
    if args.detectar:
        print(json.dumps({'sources': [{'path': str(s.path), 'sheet': s.sheet, 'kind': s.kind,
               'period': s.period, 'mode': s.mode, 'rows': s.rows,
               'downloaded_periods': [vars(period) for period in s.periods]} for s in sources], 'errors': errors},
               ensure_ascii=False, indent=2))
        return
    if errors:
        parser.error('Hay fuentes que no se pudieron leer. Revise --detectar antes de generar: ' + str(errors))
    choices = default_selection(sources)
    sources = [source for source in sources if choices[source.key]]
    periods = None
    if args.periodo:
        periods = {key for key in available_periods(sources) if key[0] in args.periodo
                   and (args.modalidad is None or key[1] == args.modalidad)}
        missing = set(args.periodo) - {key[0] for key in periods}
        if missing:
            parser.error('No hay fuentes elegidas con datos para los períodos: ' + ', '.join(sorted(missing)))
        sources = [source for source in sources if any(period.key in periods and period.rows > 0 for period in source.periods)]
    if not sources:
        parser.error('No hay fuentes con datos de Conocimientos en las carpetas indicadas')
    stats = build_base(sources, args.salida, year=args.ano, month=args.mes, mode=args.modalidad, periods=periods,
        progress=lambda e: print(json.dumps(e, ensure_ascii=True), flush=True) if e['phase'] == 'read' and e['read'] % 2000 else None)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
