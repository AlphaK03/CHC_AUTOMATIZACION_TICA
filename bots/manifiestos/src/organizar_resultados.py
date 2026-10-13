"""Migra salidas a CSV públicos y almacenamiento privado; pospone archivos en uso."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from conocimientos_queue import OutputLock
from resultados import (FLOWS, LEGACY_FOLDERS, application_base, custom_workspace,
                        output_base, output_paths, parse_result_name, csv_name, csv_directory, register_csv_location)
from utils import load_config

HISTORICAL_PATTERN = re.compile(r'^(\d{2})(\d{4})_Manifiesto_(MOV|Contenedores)_'
                                r'(AEREO|MARITIMO|TERRESTRE)_.*\.(csv|xlsx)$', re.I)


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def describe(source):
    original = Path(str(source)[:-4]) if source.name.endswith('.tmp') else source
    parsed = parse_result_name(original)
    if parsed:
        return parsed, 'tmp' if source.name.endswith('.tmp') else source.suffix.lower().lstrip('.')
    match = HISTORICAL_PATTERN.fullmatch(source.name)
    if match:
        month, year, procedure, mode, ext = match.groups()
        return (('movimientos' if procedure.lower() == 'mov' else 'contenedores'),
                mode.lower(), int(month), int(year), ''), ext.lower()
    return None


def source_roots(config, flow):
    from resultados import PROJECT_ROOT
    custom = custom_workspace(config, flow)
    roots = [custom] if custom else [output_base(config, flow), PROJECT_ROOT/'src'/LEGACY_FOLDERS[flow]]
    if flow == 'conocimientos' and not custom:
        roots.append(PROJECT_ROOT/'src/output_manifest_conocimientos_v2')
    return list(dict.fromkeys(root.resolve() for root in roots))


def _priority(source):
    return ('historicos' in source.parts or '_historico_' in source.stem,
            source.parent.name not in ('SQLite', 'CSV'), str(source))


def _historical_csv(destination, source):
    tag = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:10]
    return destination.with_name(destination.stem + '_historico_' + tag + '.csv')


def _move(source, destination, roots, destinations, moved, records, state='Organizado'):
    source, destination = source.resolve(), destination.resolve()
    if source == destination:
        return
    if not any(source.is_relative_to(root) for root in roots) or not any(destination.is_relative_to(root) for root in destinations):
        raise ValueError('Ruta de migración fuera de las carpetas autorizadas')
    if destination.exists():
        raise RuntimeError(f'Colisión sin resolver: {destination}')
    before = checksum(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    moved.append((source, destination))
    if checksum(destination) != before:
        raise RuntimeError('El contenido cambió al trasladar el archivo')
    records.append({'source': str(source), 'destination': str(destination), 'state': state, 'sha256': before})


def organize_results(config, only=None):
    records, groups, misc, roots_by_flow = [], {}, {}, {}
    for flow in FLOWS:
        if only and flow != only[0]:
            continue
        roots = source_roots(config, flow)
        roots_by_flow[flow] = roots
        private = application_base(config, flow).resolve()
        for root in roots:
            if not root.exists():
                continue
            for source in root.rglob('*'):
                if not source.is_file() or source.resolve().is_relative_to(private):
                    continue
                detail = describe(source)
                if not detail:
                    if not only and source.suffix.lower() != '.csv':
                        misc.setdefault(source.resolve(), (root, flow))
                    continue
                (actual_flow, mode, month, year, qualifier), ext = detail
                if actual_flow != flow or ext not in ('csv','sqlite3','xlsx','tmp'):
                    continue
                if only and (mode, month, year) != only[1:]:
                    continue
                groups.setdefault((flow, mode, month, year), {})[source.resolve()] = (root, qualifier, ext)

    blocked = set()
    blocked_parents = set()
    for (flow, mode, month, year), candidates in sorted(groups.items()):
        paths = output_paths(config, flow, mode, month, year)
        public, private = output_base(config, flow).resolve(), application_base(config, flow).resolve()
        roots = roots_by_flow[flow]
        dbs = [source for source, (_, _, ext) in candidates.items() if ext == 'sqlite3']
        # Reservar ambas rutas, antigua y nueva, durante todo el traslado.
        locks, moved, group_records = [], [], []
        try:
            for db in sorted(set(dbs + [paths.database.resolve()])):
                locks.append(OutputLock(str(db) + '.lock'))
            if any(Path(str(db)+suffix).exists() for db in dbs for suffix in ('-journal','-wal')):
                raise RuntimeError('La base tiene un journal pendiente; se conserva para el siguiente inicio')
            confirmed_database = bool(dbs) or paths.database.exists()
            for source in sorted(candidates, key=_priority):
                root, qualifier, ext = candidates[source]
                if ext == 'csv':
                    destination = csv_directory(paths.period, qualifier) / csv_name(flow, mode, month, year, qualifier)
                    historical = ('historicos' in source.parts or '_historico_' in source.stem or
                                  (flow == 'conocimientos' and not qualifier and not confirmed_database))
                    if source == destination.resolve():
                        continue
                    if '_historico_' in source.stem:
                        destination = csv_directory(paths.period, qualifier, True) / source.name
                    elif historical or destination.exists():
                        historical_csv = csv_directory(paths.period, qualifier, True) / destination.name
                        destination = _historical_csv(historical_csv, source)
                    if source == destination.resolve():
                        continue
                    state = 'Histórico' if '_historico_' in destination.stem else 'Organizado'
                elif ext == 'sqlite3':
                    destination = paths.database
                    if source == destination.resolve():
                        continue
                    if destination.exists() or 'historicos' in source.parts:
                        tag = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:10]
                        destination = private/'historicos/SQLite'/flow/str(year)/mode/(source.stem+'_'+tag+'.sqlite3')
                    state = 'Organizado'
                else:
                    destination = private/'archivos_originales'/flow/str(year)/mode/source.name
                    if destination.exists():
                        tag = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:10]
                        destination = destination.with_name(destination.stem+'_'+tag+destination.suffix)
                    state = 'Archivado'
                _move(source, destination, roots, [public, private], moved, group_records, state)
                if ext == 'sqlite3' and destination != paths.database:
                    register_csv_location(destination, _historical_csv(paths.period/'historicos'/paths.csv.name, source))
            records.extend(group_records)
        except (RuntimeError, PermissionError) as exc:
            for source, destination in reversed(moved):
                if destination.exists() and not source.exists():
                    destination.rename(source)
            blocked.add((flow, mode, month, year))
            blocked_parents.update(db.parent.parent if db.parent.name == 'SQLite' else db.parent for db in dbs)
            records.append({'source': str(dbs[0] if dbs else paths.csv), 'state': 'Pospuesto', 'reason': str(exc)})
        except BaseException:
            for source, destination in reversed(moved):
                if destination.exists() and not source.exists():
                    destination.rename(source)
            raise
        finally:
            for lock in reversed(locks):
                lock.close()

    if not only:
        for source, (root, flow) in sorted(misc.items()):
            if not source.exists() or any(source.is_relative_to(parent) for parent in blocked_parents):
                continue
            if source.name.endswith('.lock'):
                detail = describe(Path(str(source)[:-5]))
                if detail and tuple(detail[0][:4]) in blocked:
                    continue
                try:
                    probe = OutputLock(source)
                    probe.close()
                except RuntimeError:
                    records.append({'source': str(source), 'state': 'Pospuesto', 'reason': 'Bloqueo en uso'})
                    continue
            private = application_base(config, flow).resolve()
            if source.suffix.lower() == '.xlsx' and 'bases_bls' in source.relative_to(root).parts:
                workspace = custom_workspace(config, flow)
                from resultados import PROJECT_ROOT
                destination_root = workspace/'bases_bls' if workspace else PROJECT_ROOT/'bases_bls'
                destination = destination_root/source.name
            else:
                destination_root = private
                destination = private/'archivos_originales'/root.name/source.relative_to(root)
            if destination.exists():
                tag = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:10]
                destination = destination.with_name(destination.stem+'_'+tag+destination.suffix)
            moved = []
            try:
                _move(source, destination, [root], [destination_root], moved, records, 'Archivado')
            except (PermissionError, RuntimeError) as exc:
                for original, destination in reversed(moved):
                    if destination.exists() and not original.exists():
                        destination.rename(original)
                records.append({'source': str(source), 'state': 'Pospuesto', 'reason': str(exc)})
        for root in {r for roots in roots_by_flow.values() for r in roots}:
            if root.exists():
                for folder in sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
                    if not folder.resolve().is_relative_to(root):
                        continue
                    try:
                        folder.rmdir()  # Exclusivamente directorios vacíos; conserva cualquier archivo.
                    except OSError:
                        pass
    if records:
        report = application_base(config, only[0] if only else None)/'organizacion'
        report.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        (report/f'organizacion_{stamp}.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


if __name__ == '__main__':
    records = organize_results(load_config())
    print(json.dumps({'files':len(records), 'states':{state:sum(r['state']==state for r in records)
          for state in sorted({r['state'] for r in records})}}, ensure_ascii=False))
