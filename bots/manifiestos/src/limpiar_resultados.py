"""Limpieza explícita de CSV repetidos; nunca elimina bases ni filas individuales."""
import csv
import json
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from conocimientos_queue import OutputLock
from organizar_resultados import checksum
from resultados import FLOWS, application_base, output_base, output_paths, parse_result_name


def schema(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        header = next(csv.reader(stream), [])
    indices = [i for i, name in enumerate(header) if not name.startswith('index_flujo_')]
    return header, indices, tuple(header[i] for i in indices)


def rows(path, header, indices):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        if next(reader, []) != header:
            raise ValueError('El encabezado cambió durante la comparación')
        for row in reader:
            if len(row) != len(header):
                raise ValueError('CSV con columnas incompletas; se conserva')
            yield (json.dumps([row[i] for i in indices], ensure_ascii=False),)


def covered_by(candidate, retained, temporary_root):
    """Compara multiconjuntos exactos: las repeticiones legítimas también cuentan."""
    a_header, a_indices, a_schema = schema(candidate)
    b_header, b_indices, b_schema = schema(retained)
    if not a_schema or a_schema != b_schema:
        return False, None
    with tempfile.TemporaryDirectory(dir=temporary_root) as folder, closing(
            sqlite3.connect(str(Path(folder)/'comparacion.sqlite3'))) as db:
        db.execute('PRAGMA journal_mode=OFF')
        for table, path, header, indices in (
                ('retained', retained, b_header, b_indices),
                ('candidate', candidate, a_header, a_indices)):
            db.execute(f'CREATE TABLE {table} (data TEXT PRIMARY KEY, copies INTEGER NOT NULL)')
            db.executemany(f'INSERT INTO {table} VALUES (?,1) ON CONFLICT(data) DO UPDATE SET copies=copies+1',
                           rows(path, header, indices))
        count = db.execute('SELECT COALESCE(SUM(copies),0) FROM candidate').fetchone()[0]
        missing = db.execute('''SELECT 1 FROM candidate c LEFT JOIN retained r ON r.data=c.data
            WHERE r.copies IS NULL OR c.copies>r.copies LIMIT 1''').fetchone()
        return missing is None, count


def clean_duplicate_results(config, apply=False):
    groups, records = defaultdict(list), []
    roots = {output_base(config, flow).resolve() for flow in FLOWS}
    for root in roots:
        if root.exists():
            for path in root.rglob('*.csv'):
                detail = parse_result_name(path)
                if detail:
                    groups[detail].append(path.resolve())
    report_root = application_base(config)/'organizacion'
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    report = report_root/f'limpieza_{stamp}.json'
    for detail, paths in sorted(groups.items()):
        flow, mode, month, year, qualifier = detail
        paths = sorted(set(paths), key=lambda p: ('_historico_' in p.stem, -p.stat().st_size, str(p)))
        lock = None
        try:
            database = output_paths(config, flow, mode, month, year).database
            lock = OutputLock(str(database)+'.lock')
            retained = []
            for candidate in paths:
                digest = checksum(candidate)
                target, reason, count = None, '', None
                if '_historico_' in candidate.stem and qualifier in ('fallidos','fallidas','estado'):
                    header, indices, _ = schema(candidate)
                    if next(rows(candidate, header, indices), None) is None:
                        reason = 'Control histórico vacío'
                if not reason:
                    for other, other_digest in retained:
                        if digest == other_digest:
                            target, reason = other, 'Copia idéntica (SHA-256)'
                            break
                        if '_historico_' in candidate.stem:
                            covered, count = covered_by(candidate, other, report_root)
                            if covered:
                                target, reason = other, 'Versión antigua: todos sus registros y repeticiones están conservados'
                                break
                if not reason:
                    retained.append((candidate, digest))
                    continue
                record = {'source':str(candidate), 'sha256':digest, 'reason':reason,
                          'retained':str(target) if target else None, 'rows':count,
                          'state':'Previsto'}
                if target:
                    record['retained_sha256'] = checksum(target)
                records.append(record)
                if apply:
                    # Persistir intención antes de borrar; verificar rutas y ambas copias.
                    report.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
                    if not any(candidate.is_relative_to(root) for root in roots) or candidate.suffix != '.csv':
                        raise ValueError('Archivo fuera de las rutas de CSV autorizadas')
                    if checksum(candidate) != digest or (target and checksum(target) != record['retained_sha256']):
                        raise RuntimeError('El contenido cambió durante la limpieza')
                    candidate.unlink()
                    record['state'] = 'Eliminado'
        except (RuntimeError, PermissionError, ValueError, csv.Error) as exc:
            records.append({'source':str(paths[0]), 'state':'Pospuesto', 'reason':str(exc)})
        finally:
            if lock:
                lock.close()
    report.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


if __name__ == '__main__':
    import argparse
    from utils import load_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true', help='Eliminar solo los CSV comprobados como redundantes')
    args = parser.parse_args()
    result = clean_duplicate_results(load_config(), apply=args.aplicar)
    print(json.dumps(result, ensure_ascii=False, indent=2))
