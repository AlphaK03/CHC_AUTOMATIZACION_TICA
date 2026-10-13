"""Publica los tres Excel compatibles desde una sola captura validada."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import hashlib

from data_store import MONTHS, OUTPUT_NAMES, REGIMENES, RunLock
from excel_format import write_excel
from original_exports import stage_originals
from output_paths import filesystem_path, display_path, prepare_output_folder

JOURNAL = '.publicacion_pendiente.json'
MANIFEST = 'ultima_entrega.json'


def safe_target(base, name):
    base = filesystem_path(base)
    target = filesystem_path(base / name)
    if not target.is_relative_to(base) or target == base:
        raise ValueError('Ruta de exportación inválida.')
    return target


def atomic_copy(source, target):
    source, target = filesystem_path(source), filesystem_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.publicando-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as out, open(source, 'rb') as stream:
            shutil.copyfileobj(stream, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path, value):
    path = filesystem_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.estado-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def recover_publication(base):
    """Caller holds the publication lock. Restore unfinished sets before any new export."""
    base = filesystem_path(base)
    journal = base / JOURNAL
    if not journal.exists():
        return
    state = json.loads(journal.read_text(encoding='utf-8'))
    generation = (base / state['generation']).resolve()
    if not generation.is_relative_to(base / 'entregas'):
        raise ValueError('Ruta de recuperación inválida.')
    if not state.get('complete'):
        errors = []
        for name in state['prior']:
            try:
                target = safe_target(base, name)
                if state['prior'][name]:
                    backup = safe_target(generation / '_previous', name)
                    if target.exists() and hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(backup.read_bytes()).digest():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    atomic_copy(backup, target)
                else:
                    target.unlink(missing_ok=True)
            except OSError as exc:
                errors.append(str(exc))
        if errors:
            raise OSError('Cierra los Excel y vuelve a exportar para recuperar la entrega anterior. ' + '; '.join(errors))
    journal.unlink()


def commit_generation(base, generation, names, obsolete=()):
    """Publish/recover the complete managed set, including nested original files."""
    base, generation = filesystem_path(base), filesystem_path(generation)
    previous = generation / '_previous'
    previous.mkdir()
    prior = {}
    for name in dict.fromkeys([*names, *obsolete]):
        target = safe_target(base, name)
        prior[name] = target.exists()
        if prior[name]:
            backup = safe_target(previous, name)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
    state = dict(generation=str(generation.relative_to(base)), prior=prior, complete=False)
    atomic_json(base / JOURNAL, state)
    try:
        for name in names:
            target = safe_target(base, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy(safe_target(generation, name), target)
        for name in obsolete:
            safe_target(base, name).unlink(missing_ok=True)
        atomic_json(base / JOURNAL, {**state, 'complete': True})
    except BaseException:
        recover_publication(base)
        raise
    (base / JOURNAL).unlink()


def prepare_originals(base, generation, store, period, mode):
    files, pending = stage_originals(generation, store, period, mode)
    manifest = f'entregas/originales-{period}.json'
    previous_files = {}
    if (base / manifest).exists():
        previous_files = json.loads((base / manifest).read_text(encoding='utf-8'))['files']
    # Only replace files previously managed for this period. Other years,
    # legacy files and user workbooks are never removed.
    for name in previous_files:
        relative = Path(name)
        if len(relative.parts) != 3 or relative.parts[0] not in REGIMENES or relative.parts[1] != period or relative.suffix != '.xlsx':
            raise ValueError('El registro de originales contiene una ruta inválida.')
        safe_target(base, name)
    metadata = dict(period=period, mode=mode, files=files, pending=pending,
                    generation=str(generation.relative_to(base)))
    (generation / manifest).parent.mkdir(parents=True, exist_ok=True)
    atomic_json(generation / manifest, metadata)
    return files, pending, manifest, set(previous_files) - set(files)


def publish_originals(base, period, store, mode):
    base = prepare_output_folder(base)
    with RunLock(base / '.publicacion'):
        recover_publication(base)
        generation = base / 'entregas' / period / uuid.uuid4().hex
        generation.mkdir(parents=True)
        files, pending, manifest, obsolete = prepare_originals(base, generation, store, period, mode)
        commit_generation(base, generation, [*files, manifest], obsolete)
        return [str(display_path(base / name)) for name in files], pending


def publish(base, period, ranges, lists, store=None):
    base = prepare_output_folder(base)
    with RunLock(base / '.publicacion'):
        recover_publication(base)
        generation = base / 'entregas' / period / uuid.uuid4().hex
        generation.mkdir(parents=True)
        year, month = map(int, period.split('-'))
        sheet = MONTHS[month - 1].lower() + str(year)[-2:]
        for name, duas in zip(OUTPUT_NAMES, lists, strict=True):
            write_excel(generation / name, sheet, ['NroDUA'], ([dua] for dua in duas))
        original_files, original_manifest, obsolete = {}, None, ()
        if store is not None:
            mode = 'month' if len(ranges) == 2 else 'halves'
            original_files, _, original_manifest, obsolete = prepare_originals(base, generation, store, period, mode)
        metadata = dict(period=period, ranges=ranges, sheet=sheet,
                        files=dict(zip(OUTPUT_NAMES, map(len, lists), strict=True)),
                        generation=str(generation.relative_to(base)))
        metadata['originals'] = original_files
        atomic_json(generation / MANIFEST, metadata)
        names = [*OUTPUT_NAMES, MANIFEST, *original_files]
        if original_manifest:
            names.append(original_manifest)
        commit_generation(base, generation, names, obsolete)
        return [str(display_path(base / name)) for name in OUTPUT_NAMES]
