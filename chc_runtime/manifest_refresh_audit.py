"""Experimento independiente: refrescar exclusivamente manifiestos confirmados.

Las fuentes se abren solo lectura. No importa servicios del Workbench, no
recupera reservas y no publica resultados ni cobertura del experimento.
"""
import argparse
import asyncio
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import zlib


ROOT = Path(__file__).resolve().parents[1]
FLOWS = ('conocimientos', 'duas')
IDENTITY_LABELS = ('Trans.', 'Ing Sal', 'Manifiesto', 'Cod Ubicacion', 'Fecha')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def packed(value):
    return zlib.compress(encoded(value))


def unpacked(value):
    return json.loads(zlib.decompress(value))


def fingerprints(rows, flow, mid):
    result = Counter()
    for row in rows:
        if (not isinstance(row, list) or len(row) != (15 if flow == 'conocimientos' else 11)
                or row[0 if flow == 'conocimientos' else -1] != mid):
            raise ValueError('Identidad o columnas inválidas; comparación sin confirmar')
        result[hashlib.sha256(encoded(row)).hexdigest()] += 1
    return result


def reader(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    db.execute('PRAGMA query_only=ON')
    return db


def open_audit(path):
    if not Path(path).is_file():
        raise ValueError('No existe la referencia experimental')
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    if db.execute('PRAGMA user_version').fetchone()[0] != 1:
        db.close()
        raise ValueError('No es una referencia experimental compatible')
    return db


def freeze(root, output, year, month, mode, flows=FLOWS, limit=0):
    """Congela la cohorte por base con una transacción de lectura consistente."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if (root / 'data/jobs') == output or (root / 'data/jobs') in output.parents:
        raise ValueError('El experimento debe quedar fuera de data/jobs')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Creación exclusiva: nunca sustituir una referencia tomada anteriormente.
    with output.open('xb'):
        pass
    try:
        with closing(sqlite3.connect(output)) as audit:
            audit.executescript('''
                PRAGMA user_version=1;
                CREATE TABLE metadata(value TEXT NOT NULL);
                CREATE TABLE sources(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL,
                    flow TEXT NOT NULL, scope TEXT NOT NULL, captured TEXT NOT NULL,
                    saved INTEGER NOT NULL, skipped INTEGER NOT NULL);
                CREATE TABLE targets(id INTEGER PRIMARY KEY, source INTEGER NOT NULL,
                    manifest TEXT NOT NULL, ordinal INTEGER NOT NULL, saved_at TEXT NOT NULL,
                    old_count INTEGER NOT NULL, hashes BLOB NOT NULL, historical_seconds REAL,
                    UNIQUE(source,manifest));
                CREATE TABLE observations(target INTEGER PRIMARY KEY, checked TEXT NOT NULL,
                    status TEXT NOT NULL, new_count INTEGER, added INTEGER, removed INTEGER,
                    seconds REAL NOT NULL, error TEXT NOT NULL, stats TEXT, rows BLOB);
            ''')
            audit.execute('INSERT INTO metadata VALUES (?)', (json.dumps(dict(
                created=now(), root=str(root), year=year, month=month, mode=mode,
                flows=list(flows), limit_per_database=limit)),))
            for flow in flows:
                if flow not in FLOWS:
                    raise ValueError('Procedimiento no permitido')
                session = json.loads((root / 'data/workbench' / flow / 'session.json').read_text(encoding='utf-8'))
                candidates = [h for h in session.get('history', [])
                              if h.get('spec', {}).get('year') == year
                              and h.get('spec', {}).get('month') == month]
                # Todos los lotes del período, sin fusionar bases históricas.
                seen = set()
                for record in candidates:
                    for raw in record.get('databases', []):
                        path = Path(raw).resolve()
                        if path in seen:
                            continue
                        seen.add(path)
                        if not path.is_relative_to(root / 'data/jobs' / flow):
                            raise ValueError('La fuente no pertenece al procedimiento: ' + str(path))
                        with closing(reader(path)) as source:
                            source.execute('BEGIN')
                            scope = json.loads(source.execute('SELECT scope FROM metadata').fetchone()[0])
                            if scope.get('mode') != mode:
                                continue
                            if (scope.get('year') != year or scope.get('month') != month
                                    or scope.get('flow', 'conocimientos') != flow):
                                raise ValueError('Los metadatos del lote y de SQLite no coinciden')
                            jobs = source.execute('''SELECT j.id,j.ordinal,j.updated,j.kept_count,m.stats
                                FROM jobs j JOIN manifests m ON m.id=j.id
                                WHERE j.state='Guardado' ORDER BY j.ordinal,j.id''').fetchall()
                            skipped = source.execute("SELECT count(*) FROM jobs WHERE state!='Guardado'").fetchone()[0]
                            sid = audit.execute('INSERT INTO sources(path,flow,scope,captured,saved,skipped) VALUES (?,?,?,?,?,?)',
                                (str(path), flow, json.dumps(scope), now(), len(jobs), skipped)).lastrowid
                            for mid, ordinal, saved_at, kept, raw_stats in jobs[:limit or None]:
                                rows = [json.loads(r[0]) for r in source.execute(
                                    'SELECT data FROM rows WHERE manifest=? ORDER BY sequence', (mid,))]
                                stats = json.loads(raw_stats)
                                if len(rows) != kept or len(rows) != stats['kept']:
                                    raise ValueError('Conteo original inconsistente: ' + mid)
                                audit.execute('''INSERT INTO targets(source,manifest,ordinal,saved_at,old_count,hashes,historical_seconds)
                                    VALUES (?,?,?,?,?,?,?)''', (sid, mid, ordinal, saved_at, len(rows),
                                    packed(fingerprints(rows, flow, mid)), stats.get('seconds')))
            if not audit.execute('SELECT count(*) FROM targets').fetchone()[0]:
                raise ValueError('No hay manifiestos Guardado para esta selección')
            audit.commit()
    except BaseException:
        # Solo el archivo creado exclusivamente por esta llamada, sin datos previos.
        output.unlink(missing_ok=True)
        raise
    return report(output)


def compare(db, target, rows, stats, seconds):
    old = Counter(unpacked(target['hashes']))
    fresh = fingerprints(rows, target['flow'], target['manifest'])
    if stats['kept'] != len(rows):
        raise ValueError('La extracción no confirma la cantidad de filas')
    added, removed = sum((fresh - old).values()), sum((old - fresh).values())
    delta = len(rows) - target['old_count']
    status = ('aumento' if delta > 0 else 'disminucion' if delta < 0 else
              'cambio' if added or removed else 'sin_cambios')
    with db:
        db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)',
            (target['id'], now(), status, len(rows), added, removed, seconds, '',
             json.dumps(stats), packed(rows)))


def failure(db, target, status, error, seconds):
    with db:
        db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)',
            (target['id'], now(), status, None, None, None, seconds, str(error), None, None))


def report(path):
    with closing(open_audit(path)) as db:
        groups = [dict(r) for r in db.execute('''SELECT s.flow,s.path,s.saved,s.skipped,
            count(t.id) selected,coalesce(sum(t.old_count),0) old_rows,
            coalesce(sum(t.historical_seconds),0) historical_seconds FROM sources s
            JOIN targets t ON t.source=s.id GROUP BY s.id''')]
        rows = [dict(r) for r in db.execute('''SELECT s.flow,s.path source,t.manifest,
            t.old_count,o.new_count,o.new_count-t.old_count delta,o.added,o.removed,
            coalesce(o.status,'pendiente') status,o.seconds,o.error FROM targets t
            JOIN sources s ON s.id=t.source LEFT JOIN observations o ON o.target=t.id
            ORDER BY s.id,t.ordinal''')]
        comparison = []
        for flow in FLOWS:
            selected = [r for r in rows if r['flow'] == flow]
            confirmed = [r for r in selected if r['new_count'] is not None]
            comparison.append(dict(flow=flow, selected=len(selected), compared=len(confirmed),
                baseline_rows=sum(r['old_count'] for r in selected),
                compared_old_rows=sum(r['old_count'] for r in confirmed),
                fresh_rows=sum(r['new_count'] for r in confirmed),
                delta=sum(r['delta'] for r in confirmed),
                statuses=dict(Counter(r['status'] for r in selected))))
        return dict(reference=str(Path(path).resolve()), groups=groups, comparison=comparison,
                    totals=dict(Counter(r['status'] for r in rows)), manifests=rows)


def differences(path):
    """Filas frescas sin versión idéntica en la referencia, con multiplicidad.

    Una versión modificada cuenta como añadida y otra retirada; no se debe
    interpretar cada versión añadida como un nuevo BL o una nueva asociación.
    """
    output = []
    with closing(open_audit(path)) as db:
        for target in db.execute('''SELECT t.*,s.flow,s.path,o.rows,o.status,o.new_count
                FROM targets t JOIN sources s ON s.id=t.source
                JOIN observations o ON o.target=t.id
                WHERE o.status IN ('aumento','disminucion','cambio')'''):
            remaining = Counter(unpacked(target['hashes']))
            added = []
            for row in unpacked(target['rows']):
                digest = hashlib.sha256(encoded(row)).hexdigest()
                if remaining[digest]:
                    remaining[digest] -= 1
                else:
                    added.append(row)
            output.append(dict(flow=target['flow'],source=target['path'],manifest=target['manifest'],
                status=target['status'],old_count=target['old_count'],new_count=target['new_count'],
                fresh_versions=added,removed_versions=sum(remaining.values())))
    return output


async def run(path, workers=4, retry_errors=False, fixture_factory=None):
    sys.path.insert(0, str(ROOT / 'bots/manifiestos/src'))
    from conocimientos_queue import OutputLock
    if not Path(path).is_file():
        raise ValueError('No existe la referencia experimental')
    lock = OutputLock(str(Path(path).resolve()) + '.lock')
    try:
        return await _run(path, workers, retry_errors, fixture_factory)
    finally:
        lock.close()


async def _run(path, workers=4, retry_errors=False, fixture_factory=None):
    """Obtiene enlaces frescos pero extrae solo identidades de la cohorte congelada."""
    if not 1 <= workers <= 4:
        raise ValueError('Use de 1 a 4 consultas simultáneas')
    sys.path.insert(0, str(ROOT / 'bots/manifiestos/src'))
    from conocimientos import extract_table, parse_main_rows
    from manifest_scraper import ManifestScraper
    from tablas_flow import IsolatedTableRequest
    from tablas_manifiesto import parse_table
    from playwright.async_api import async_playwright
    from .distribution import chromium_options
    with closing(open_audit(path)) as db:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, **chromium_options())
            try:
                for source in db.execute('SELECT * FROM sources').fetchall():
                    targets = db.execute('''SELECT t.*,s.flow FROM targets t JOIN sources s ON s.id=t.source
                        LEFT JOIN observations o ON o.target=t.id WHERE t.source=? AND
                        (o.target IS NULL OR (? AND o.status IN ('error','sin_enlace'))) ORDER BY t.ordinal''',
                        (source['id'], int(retry_errors))).fetchall()
                    if not targets:
                        continue
                    scope, flow = json.loads(source['scope']), source['flow']
                    scraper = ManifestScraper({'timeout_manifest':120}, browser, request_factory=pw.request)
                    scraper._conoc_mode = scope['mode']
                    scraper.conoc_dates = [datetime.strptime(scope[k], '%Y-%m-%d') for k in ('desde','hasta')]
                    scraper._conoc_link_lock = asyncio.Lock()
                    scraper._conoc_link_refreshed = 0
                    scraper._conoc_link_field = 'vVCONS' if flow == 'conocimientos' else 'vVDUAS'
                    portal = fixture_factory(scraper, source) if fixture_factory else None
                    try:
                        await scraper.open_page()
                        await scraper._query_conoc_main()
                        snapshot = parse_main_rows(scraper.conoc_main_grid, scraper.conoc_main_values,
                                                   scraper.URL, scraper._conoc_link_field)
                        links = {}
                        for item in snapshot:
                            if item is None:
                                continue
                            href, info, _ = item
                            mid = '-'.join(info[k].strip() for k in IDENTITY_LABELS)
                            if mid in links and links[mid] != href:
                                raise ValueError('Enlaces ambiguos para ' + mid)
                            links[mid] = href
                        agent = await scraper.page.evaluate('navigator.userAgent')
                        queue = asyncio.Queue()
                        for target in targets:
                            queue.put_nowait(target)

                        async def worker():
                            while not queue.empty():
                                target = queue.get_nowait()
                                started, request = time.monotonic(), None
                                try:
                                    mid = target['manifest']
                                    href = links.get(mid)
                                    if not href:
                                        failure(db, target, 'sin_enlace', 'No aparece en el listado confirmado; no equivale a cero', 0)
                                        continue
                                    options = dict(courier=scope.get('courier'), checkpoint=None,
                                        renew_link=lambda: scraper._renew_conoc_link(mid))
                                    if flow == 'duas':
                                        request = IsolatedTableRequest(pw.request, scraper.context, agent)
                                        async def renew():
                                            link = await scraper._renew_conoc_link(mid)
                                            await request.refresh()
                                            return link
                                        options.update(courier=None, parse_html=lambda html, expected: parse_table(html, expected, 'duas'),
                                            sequence_key=lambda row, position: position, sort_rows=False,
                                            request_attempts=1, recover_errors=False, expected_status=200,
                                            parse_in_thread=True, renew_link=renew)
                                    rows, stats = await extract_table(request or scraper.context.request,
                                        href, mid, 0 if flow == 'duas' else 120, **options)
                                    compare(db, target, rows, stats, round(time.monotonic()-started, 3))
                                except Exception as exc:
                                    failure(db, target, 'error', str(exc) or type(exc).__name__, round(time.monotonic()-started, 3))
                                finally:
                                    if request:
                                        await request.close()
                                    queue.task_done()
                                    row = db.execute('SELECT status,new_count FROM observations WHERE target=?', (target['id'],)).fetchone()
                                    print(json.dumps(dict(flow=flow, manifest=target['manifest'],
                                        old=target['old_count'], status=row['status'] if row else 'interrumpido',
                                        new=row['new_count'] if row else None), ensure_ascii=False), flush=True)
                        tasks = [asyncio.create_task(worker()) for _ in range(min(workers, len(targets)))]
                        try:
                            await asyncio.gather(*tasks)
                        finally:
                            for task in tasks:
                                task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                    except Exception as exc:
                        for target in targets:
                            if not db.execute('SELECT 1 FROM observations WHERE target=?', (target['id'],)).fetchone():
                                failure(db, target, 'error', 'Listado sin confirmar: ' + str(exc), 0)
                    finally:
                        if scraper.context:
                            await scraper.context.close()
                        if portal:
                            portal.close()
            finally:
                await browser.close()
    return report(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('freeze', help='Solo lectura local; congela Guardado')
    capture.add_argument('--root', type=Path, default=ROOT / 'bots/manifiestos')
    capture.add_argument('--output', type=Path, required=True)
    capture.add_argument('--year', type=int, required=True)
    capture.add_argument('--month', type=int, required=True, choices=range(1, 13))
    capture.add_argument('--mode', choices=('maritimo','aereo','terrestre'), required=True)
    capture.add_argument('--flow', choices=FLOWS, action='append')
    capture.add_argument('--limit', type=int, default=0, help='Por base; cero = todos')
    fresh = sub.add_parser('run', help='Consulta real de la cohorte; reanuda comparaciones faltantes')
    fresh.add_argument('reference', type=Path)
    fresh.add_argument('--workers', type=int, default=4, choices=range(1, 5))
    fresh.add_argument('--retry-errors', action='store_true')
    show = sub.add_parser('report', help='Solo lectura del experimento')
    show.add_argument('reference', type=Path)
    diff = sub.add_parser('differences', help='Versiones de filas añadidas/modificadas; solo lectura')
    diff.add_argument('reference', type=Path)
    args = parser.parse_args()
    if args.command == 'freeze':
        if args.limit < 0:
            parser.error('--limit debe ser cero o positivo')
        value = freeze(args.root, args.output, args.year, args.month, args.mode, args.flow or FLOWS, args.limit)
    elif args.command == 'run':
        value = asyncio.run(run(args.reference, args.workers, args.retry_errors))
    elif args.command == 'differences':
        value = differences(args.reference)
    else:
        value = report(args.reference)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
