"""Retirada recuperable de un lote propio, sin tocar entradas ni CSV públicos."""
from contextlib import ExitStack
import copy
import json
import logging
import os
from pathlib import Path
import re
import uuid

from .job_store import RunLock


def write_json(path, value):
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def checked_work(root, flow, record):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', str(record['id'])):
        raise ValueError('Identidad de lote inválida. No se borró nada.')
    expected = root / 'data' / 'jobs' / flow / record['id']
    work = Path(record['work'])
    if work.absolute() != expected.absolute() or work.resolve() != expected.absolute():
        raise ValueError('La carpeta del lote no es una carpeta interna propia. No se borró nada.')
    for path in [work, *work.parents]:
        if path.is_symlink() or path.is_junction():
            raise ValueError('No se pueden borrar lotes mediante enlaces de carpetas.')
        if path == root:
            break
    for value in record.get('databases', []):
        if not Path(value).resolve().is_relative_to(work.resolve()):
            raise ValueError('La ejecución contiene una base externa. No se borró nada.')
    return work


def files_and_locks(work):
    files, locks = [], set()
    for path in sorted(work.rglob('*')):
        if path.is_symlink() or path.is_junction():
            raise ValueError('La carpeta contiene enlaces. No se borró nada.')
        if not path.is_file():
            continue
        if path.name.endswith('.lock'):
            locks.add(Path(str(path)[:-5]))
        else:
            files.append(path)
            if path.suffix.lower() in ('.sqlite3', '.sqlite', '.db'):
                locks.add(path)
    return files, sorted(locks)


def restore_files(work, archive, relatives):
    for relative in reversed(relatives):
        source, target = archive / 'files' / relative, work / relative
        if source.exists():
            if target.exists():
                raise RuntimeError('La recuperación encontró archivos nuevos; se conserva el respaldo: '+str(archive))
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)


def recover(root, flow, index):
    """Un cierre durante el traslado vuelve atrás si el catálogo aún conserva el lote."""
    folder = root / 'data' / 'deleted' / flow
    if folder.resolve() != folder.absolute():
        raise ValueError('La carpeta de respaldos no puede ser un enlace.')
    for journal in sorted(folder.glob('*/deletion.json')):
        data = json.loads(journal.read_text(encoding='utf-8'))
        if data['state'] != 'moving':
            continue
        record = data['record']
        work = checked_work(root, flow, record)
        committed = journal.parent.name in index.get('deletedBatches', [])
        if not committed and any(item['id'] == record['id'] for item in index['history']):
            # El diario es interno, pero validar también sus rutas antes de recuperar.
            for relative in data['files'] + data['locks']:
                if not relative or Path(relative).anchor or '..' in Path(relative).parts:
                    raise ValueError('Ruta inválida en el respaldo de borrado.')
            with ExitStack() as stack:
                for relative in data['locks']:
                    stack.enter_context(RunLock(work / relative))
                restore_files(work, journal.parent, data['files'])
            data['state'] = 'restored'
        else:
            data['state'] = 'deleted'
        try:
            write_json(journal, data)
        except OSError:
            logging.exception('La recuperación terminó; no se pudo actualizar su aviso: %s', journal)


def delete_batch(service, request):
    record = service.active()
    if service.processing:
        raise ValueError('Detenga la consulta antes de eliminar la base.')
    if (not record or request.get('confirmTableId') != record['id']
            or request.get('confirmTableName') != record['name']):
        raise ValueError('La ejecución seleccionada cambió. Confirme de nuevo.')
    if request.get('confirmation') != 'BORRAR':
        raise ValueError('Escriba exactamente BORRAR para confirmar.')
    work = checked_work(service.root, service.flow, record)
    if service.public_root().resolve().is_relative_to(work.resolve()):
        raise ValueError('La carpeta de resultados públicos está dentro del lote. No se borró nada.')
    input_path = record.get('spec', {}).get('input')
    if input_path and Path(input_path).resolve().is_relative_to(work.resolve()):
        raise ValueError('La base de entrada está dentro del lote. No se borró nada.')
    for other in service.index['history']:
        if other['id'] != record['id'] and Path(other['work']).resolve() == work.resolve():
            raise ValueError('Esta carpeta también pertenece a otra ejecución. No se borró nada.')
    files, locks = files_and_locks(work)
    archive_folder = service.root / 'data' / 'deleted' / service.flow
    if archive_folder.resolve() != archive_folder.absolute():
        raise ValueError('La carpeta de respaldos no puede ser un enlace.')
    old_index = copy.deepcopy(service.index)
    with ExitStack() as stack:
        for path in locks:
            stack.enter_context(RunLock(path))
        archive = archive_folder / uuid.uuid4().hex
        archive.mkdir(parents=True)
        relatives = [str(path.relative_to(work)) for path in files]
        data = {'state': 'moving', 'record': record, 'files': relatives,
                'locks': [str(path.relative_to(work)) for path in locks]}
        journal = archive / 'deletion.json'
        write_json(journal, data)
        try:
            for source, relative in zip(files, relatives):
                destination = archive / 'files' / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
            service.index['history'] = [item for item in service.index['history'] if item['id'] != record['id']]
            service.index['active'] = ''
            # Recibo por operación: volver a crear el mismo ID no puede reactivar
            # un respaldo cuyo aviso final quedó pendiente de escribir.
            service.index.setdefault('deletedBatches', []).append(archive.name)
            service.save()
        except Exception:
            service.index = old_index
            restore_files(work, archive, relatives)
            data['state'] = 'restored'
            write_json(journal, data)
            raise
        # El catálogo ya confirmó el borrado. Si falla este aviso, el próximo inicio
        # reconoce la ausencia del lote y conserva el respaldo sin restaurarlo.
        data['state'] = 'deleted'
        try:
            write_json(journal, data)
        except OSError:
            pass
    service._jobs = {}
    service._result_counts = {}
    service.message = 'Base eliminada. Respaldo recuperable: ' + str(archive)
    logging.info('Base «%s» retirada de %s. Respaldo recuperable: %s', record['name'], service.flow, archive)
    return {'deletedId': record['id'], 'backup': str(archive)}
