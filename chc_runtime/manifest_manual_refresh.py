"""Refresco solicitado por botón: fuentes bloqueadas, copia y reemplazo completo."""
import asyncio
from contextlib import ExitStack, closing
import json
import logging
from pathlib import Path
import sqlite3
import time
import uuid

from .manifest_refresh_audit import freeze, run, report, reader, open_audit, unpacked, fingerprints, now


def apply_manifest(db, target, observation, run_id):
    """Verifica referencia y reemplaza todas las filas en una sola transacción."""
    rows = unpacked(observation['rows'])
    stats = json.loads(observation['stats'])
    fresh = fingerprints(rows, target['flow'], target['manifest'])
    if len(rows) != observation['new_count'] or len(rows) != stats['kept']:
        raise ValueError('La descarga fresca no acredita todas sus filas')
    db.execute('BEGIN IMMEDIATE')
    try:
        job = db.execute('SELECT state,source_ordinal FROM jobs WHERE id=?', (target['manifest'],)).fetchone()
        saved = db.execute('SELECT stats FROM manifests WHERE id=?', (target['manifest'],)).fetchone()
        if not job or job[0] != 'Guardado' or not saved:
            raise ValueError('El manifiesto dejó de estar Guardado; se conserva sin actualizar')
        stats = dict(json.loads(saved[0]),**stats)
        if 'seconds' in observation.keys():
            stats['seconds'] = observation['seconds']
        previous = [json.loads(r[0]) for r in db.execute(
            'SELECT data FROM rows WHERE manifest=? ORDER BY sequence', (target['manifest'],))]
        if dict(fingerprints(previous, target['flow'], target['manifest'])) != unpacked(target['hashes']):
            raise ValueError('El resultado original cambió desde la referencia; actualización cancelada')
        if fresh != fingerprints(previous, target['flow'], target['manifest']):
            db.execute('DELETE FROM rows WHERE manifest=?', (target['manifest'],))
            db.executemany('INSERT INTO rows VALUES (?,?,?)',
                ((target['manifest'], int(row[1]) if target['flow']=='conocimientos' else n,
                  json.dumps(row,ensure_ascii=False)) for n,row in enumerate(rows)))
        db.execute('UPDATE manifests SET stats=? WHERE id=?', (json.dumps(stats),target['manifest']))
        db.execute('''UPDATE jobs SET attempts=attempts+1,pages=?,read_count=?,kept_count=?,updated=?
            WHERE id=?''', (stats['pages'],stats['read'],stats['kept'],now(),target['manifest']))
        db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?)',
            (run_id,target['manifest'],observation['checked'],now(),'Guardado','Actualización manual confirmada'))
        db.commit()
    except BaseException:
        db.rollback()
        raise


async def refresh_saved(root, record, flow, modes, workers, notify, fixture=False):
    if flow not in ('conocimientos','duas'):
        raise ValueError('Actualizar guardados solo está disponible en Conocimientos y DUAs')
    from conocimientos_queue import OutputLock
    from .manifest_fixture import FixturePortal
    root = Path(root).resolve()
    operation_id = uuid.uuid4().hex
    folder = root / 'data/refresh_saved' / flow / operation_id
    folder.mkdir(parents=True)
    started = time.monotonic()
    result = dict(id=operation_id, total=0, processed=0, updated=0, unchanged=0,
                  failed=0, delta=0, seconds=0, folder=str(folder), references=[])
    with ExitStack() as stack:
        selected = []
        for raw in dict.fromkeys(record.get('databases', [])):
            path = Path(raw).resolve()
            if not path.is_relative_to(root / 'data/jobs' / flow):
                raise ValueError('Base fuera del almacenamiento de esta ejecución')
            with closing(reader(path)) as db:
                scope = json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0])
                if scope.get('mode') not in modes:
                    continue
                if (scope.get('year'),scope.get('month'),scope.get('flow','conocimientos')) != (
                        record['spec']['year'],record['spec']['month'],flow):
                    raise ValueError('La base no coincide con el mes/procedimiento seleccionado')
            stack.enter_context(closing(OutputLock(str(path)+'.lock')))
            selected.append((path,scope['mode']))
        if not set(modes).issubset({mode for path,mode in selected}):
            raise ValueError('No hay base guardada para alguna de las modalidades seleccionadas')
        # Todos los bloqueos se adquieren antes de tomar referencias o escribir.
        for mode in dict.fromkeys(mode for path,mode in selected):
            reference = folder / (mode + '.sqlite3')
            value = freeze(root, reference, record['spec']['year'], record['spec']['month'],
                mode, flows=(flow,), record_id=record['id'], full_month=True)
            result['total'] += sum(g['selected'] for g in value['groups'])
            result['references'].append(str(reference))
        if not result['total']:
            raise ValueError('No hay manifiestos Guardado en las modalidades seleccionadas')
        notify(dict(stage='prepared', **result))
        completed = 0
        def progress(event):
            nonlocal completed
            if event['stage']=='done':
                completed += 1
            notify(dict(event, total=result['total'], processed=completed))
        def factory(scraper, source):
            scope = json.loads(source['scope'])
            portal = FixturePortal(scope['mode'],dict(record['spec'],start=scope['desde'],end=scope['hasta']))
            portal.refresh_details = True
            scraper.URL = portal.url
            return portal
        for reference in result['references']:
            await run(reference, workers=min(4,workers), fixture_factory=factory if fixture else None,
                      progress_callback=progress)
        # Hasta aquí no se ha escrito ningún dato de las fuentes.
        notify(dict(stage='applying', **result))
        for reference in result['references']:
            with closing(open_audit(reference)) as audit:
                audit.execute('''CREATE TABLE IF NOT EXISTS applications (
                    target INTEGER PRIMARY KEY,status TEXT NOT NULL,error TEXT NOT NULL)''')
                for source in audit.execute('SELECT * FROM sources').fetchall():
                    path = Path(source['path'])
                    backup = root / 'data/backups/refresh_saved' / operation_id / source['flow'] / (str(source['id'])+'-'+path.name)
                    backup.parent.mkdir(parents=True,exist_ok=True)
                    with closing(reader(path)) as original, closing(sqlite3.connect(backup)) as copy:
                        original.backup(copy)
                        if copy.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise ValueError('No se verificó el respaldo; se conserva el original sin reemplazar')
                    with closing(sqlite3.connect(path, timeout=2)) as original:
                        run_id = 'refresh-'+operation_id
                        with original:
                            original.execute('INSERT INTO runs VALUES (?,?,NULL,?,?)',
                                (run_id,now(),'Actualizando guardados',audit.execute(
                                    'SELECT count(*) FROM targets WHERE source=?',(source['id'],)).fetchone()[0]))
                        failures = 0
                        try:
                            for target in audit.execute('''SELECT t.*,s.flow FROM targets t
                                    JOIN sources s ON s.id=t.source WHERE t.source=?''',(source['id'],)).fetchall():
                                await asyncio.sleep(0)
                                observation = audit.execute('SELECT * FROM observations WHERE target=?',(target['id'],)).fetchone()
                                error = ''
                                try:
                                    if not observation or observation['rows'] is None:
                                        raise ValueError(observation['error'] if observation else 'Sin extracción completa')
                                    apply_manifest(original,target,observation,run_id)
                                    result['delta'] += observation['new_count']-target['old_count']
                                    result['unchanged' if observation['status']=='sin_cambios' else 'updated'] += 1
                                except Exception as exc:
                                    error = str(exc)
                                    failures += 1
                                    result['failed'] += 1
                                    logging.warning('[REFRESCO] %s: se conserva el resultado anterior: %s',target['manifest'],error)
                                with audit:
                                    audit.execute('INSERT INTO applications VALUES (?,?,?)',
                                        (target['id'],'error' if error else 'applied',error))
                                result['processed'] += 1
                                notify(dict(stage='applied',manifest=target['manifest'], **result))
                        except BaseException:
                            with original:
                                original.execute('UPDATE runs SET finished=?,state=? WHERE id=?',
                                    (now(),'Actualización interrumpida',run_id))
                            raise
                        else:
                            with original:
                                original.execute('UPDATE runs SET finished=?,state=? WHERE id=?',
                                    (now(),'Finalizada con actualización pendiente' if failures else 'Finalizada',run_id))
    result['seconds'] = round(time.monotonic()-started,1)
    try:
        from .manifest_service import write_json
        write_json(folder/'receipt.json',result)
    except OSError as exc:
        result['receiptError'] = str(exc)
        logging.exception('No se pudo escribir el recibo auxiliar; SQLite conserva las actualizaciones confirmadas.')
    return result
