"""Resumir diagnósticos existentes de XMovimientos sin cambiar SQLite ni resultados.

Por defecto solo revisa. Sustituir contenido exige --apply --confirm BORRAR.
No sigue enlaces fuera de data/exports y no importa motores ni consulta TICA.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chc_runtime.identifiers import normalize_dua
from chc_runtime.job_store import RunLock, atomic_output
from chc_runtime.movement_evidence import compact_form, read_summary, summarize_html, verified_empty_observation


def _stamp(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def candidates(root):
    exports = (root / 'data/exports').resolve()
    if not exports.is_dir():
        raise ValueError('No existe data/exports dentro de la raíz del bot indicada.')
    for folder in sorted(exports.rglob('diagnosticos')):
        if not folder.is_dir():
            continue
        folder.resolve().relative_to(exports)
        for path in sorted(folder.glob('*.html')):
            try:
                normalize_dua(path.stem)
            except ValueError:
                continue
            path.resolve().relative_to(exports)
            yield path


def convert_file(path, apply=False, journal=None):
    """Un archivo por vez: verificar, registrar y reemplazar atómicamente."""
    stamp = _stamp(path)
    old = path.read_bytes()
    source = old.decode('utf-8')
    sidecar = path.with_suffix('.json')
    snapshot = None
    old_json = None
    json_stamp = None
    if sidecar.is_file():
        sidecar.resolve().relative_to(path.parent.resolve())
        json_stamp = _stamp(sidecar)
        old_json = sidecar.read_bytes()
        snapshot = json.loads(old_json.decode('utf-8'))
    document = summarize_html(source, path.stem, snapshot,
                              captured_at=datetime.fromtimestamp(stamp[1] / 1e9, timezone.utc).isoformat(),
                              timestamp_origin='file_mtime')
    restored = read_summary(document)
    if restored is None:
        raise ValueError('El resumen generado no se puede leer.')
    replacements = []
    if len(document.encode('utf-8')) < len(old):
        replacements.append((path, old, document, stamp))
    if snapshot is not None:
        new_json = json.dumps(compact_form(snapshot), ensure_ascii=False, indent=2)
        if len(new_json.encode('utf-8')) < len(old_json):
            replacements.append((sidecar, old_json, new_json, json_stamp))
    result = {'path': str(path), 'status': 'converted' if apply else 'preview',
              'verified_empty': verified_empty_observation(restored, path.stem),
              'before_bytes': sum(len(old) for _, old, _, _ in replacements),
              'after_bytes': sum(len(new.encode('utf-8')) for _, _, new, _ in replacements),
              'files': [{'path': str(p), 'before_sha256': hashlib.sha256(old).hexdigest(),
                         'after_sha256': hashlib.sha256(new.encode('utf-8')).hexdigest()}
                        for p, old, new, _ in replacements]}
    if not replacements:
        result['status'] = 'unchanged'
    if apply and replacements:
        # El diario se escribe ANTES de descartar el contenido original.
        if journal is None:
            raise ValueError('La conversión requiere un diario de comprobación.')
        journal({**result, 'status': 'prepared'})
        for destination, old_bytes, text, original_stamp in replacements:
            if _stamp(destination) != original_stamp or destination.read_bytes() != old_bytes:
                raise RuntimeError('El archivo cambió durante la revisión; se conserva sin sustituir.')
            with atomic_output(destination, newline='') as stream:
                stream.write(text)
            if destination.read_bytes() != text.encode('utf-8'):
                raise RuntimeError('No se pudo comprobar el archivo convertido.')
            os.utime(destination, ns=(original_stamp[1], original_stamp[1]))
        journal(result)
    return result


def compact(root, apply=False, confirmation='', limit=None, report=None):
    root = Path(root).resolve()
    if root.name.casefold() != 'xmovimientos':
        raise ValueError('La raíz debe ser la carpeta de datos xmovimientos, no la del Workbench u otro bot.')
    exports = (root / 'data/exports').resolve()
    exports.relative_to(root)
    if not exports.is_dir():
        raise ValueError('No existe data/exports dentro de la raíz del bot indicada.')
    if apply and confirmation != 'BORRAR':
        raise ValueError('Para sustituir el contenido pesado se requiere --confirm BORRAR exacto.')
    if limit is not None and limit < 1:
        raise ValueError('--limit debe ser mayor que cero.')
    paths = candidates(root)
    totals = {'root': str(root), 'mode': 'apply' if apply else 'preview', 'examined': 0,
              'convertible': 0, 'unchanged': 0, 'errors': 0, 'before_bytes': 0, 'after_bytes': 0}
    with ExitStack() as stack:
        if apply:
            stack.enter_context(RunLock(root / 'data/evidence_compaction'))
            # Los mismos bloqueos del motor: si una descarga usa un lote, abortar.
            # No abrir conexiones SQLite ni crear servicios para inspeccionarlos.
            for database in sorted((root / 'data/queues').glob('*.sqlite3')):
                database.resolve().relative_to(root)
                stack.enter_context(RunLock(database))
        if apply and report is None:
            name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.jsonl'
            report = root / 'data/evidence_compaction' / name
        stream = None
        if report is not None:
            report = Path(report).resolve()
            report.parent.mkdir(parents=True, exist_ok=True)
            stream = stack.enter_context(report.open('x', encoding='utf-8'))
            totals['report'] = str(report)

        def journal(record):
            if stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())

        journal({'event': 'start', **totals})
        for path in paths:
            if limit is not None and totals['examined'] >= limit:
                break
            totals['examined'] += 1
            try:
                result = convert_file(path, apply=apply, journal=journal)
                totals['unchanged' if result['status'] == 'unchanged' else 'convertible'] += 1
                totals['before_bytes'] += result['before_bytes']
                totals['after_bytes'] += result['after_bytes']
                if not apply or result['status'] == 'unchanged':
                    journal(result)
            except (OSError, ValueError, RuntimeError) as exc:
                totals['errors'] += 1
                journal({'path': str(path), 'status': 'error', 'error': str(exc)[:500]})
                print(f'Conservado sin completar: {path}: {str(exc)[:200]}', file=sys.stderr)
            if totals['examined'] % 100 == 0:
                print(f"Revisados {totals['examined']}; errores {totals['errors']}", file=sys.stderr, flush=True)
        totals['saved_bytes'] = totals['before_bytes'] - totals['after_bytes']
        journal({'event': 'finish', **totals})
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Raíz de datos del bot xmovimientos; obligatoria salvo modo interactivo.')
    parser.add_argument('--interactive', action='store_true', help='Mostrar destino/muestra y pedir BORRAR antes de convertir.')
    parser.add_argument('--apply', action='store_true', help='Sustituir diagnósticos comprobados; no toca SQLite/CSV.')
    parser.add_argument('--confirm', default='', help='Confirmación exacta BORRAR para descartar contenido pesado.')
    parser.add_argument('--limit', type=int, help='Revisar solo esta cantidad de HTML.')
    parser.add_argument('--report', type=Path, help='Diario JSONL nuevo; en aplicación se crea uno por defecto.')
    args = parser.parse_args()
    if args.interactive:
        if args.apply or args.confirm:
            parser.error('--interactive pide su propia confirmación; no combinar con --apply/--confirm.')
        if args.root is None:
            installed = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
            installed = installed / 'CHC Consultores/Workbench/bots/xmovimientos'
            args.root = installed if (installed / 'data/exports').is_dir() else Path(__file__).resolve().parents[1] / 'bots/xmovimientos'
        print('Destino: ' + str(args.root.resolve()), flush=True)
        print('Muestra de hasta cinco diagnósticos, sin cambios:', flush=True)
        try:
            print(json.dumps(compact(args.root, limit=5), ensure_ascii=False, indent=2), flush=True)
            confirmation = input('Para convertir TODOS los diagnósticos de este destino, escribe BORRAR: ')
        except (EOFError, OSError, ValueError, RuntimeError) as exc:
            parser.exit(1, str(exc) + '\n')
        if confirmation != 'BORRAR':
            print('Cancelado. No se sustituyeron archivos.')
            return 0
        args.apply, args.confirm = True, confirmation
        args.limit = None
    elif args.root is None:
        parser.error('Se requiere --root o --interactive.')
    try:
        result = compact(args.root, args.apply, args.confirm, args.limit, args.report)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
