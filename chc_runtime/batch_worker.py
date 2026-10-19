"""Protocolo JSONL para motores por manifiesto y BLs, aislados de Qt."""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import threading
import traceback
from .activity import ActivityReporter, EventLog, COMMANDS

ROOT = Path(__file__).resolve().parents[1]


def main(module='manifiestos'):
    # Windows usa la página de códigos local para pipes: JSONL siempre es UTF-8.
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8',errors='replace')
    sys.stdin.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', default='conocimientos')
    parser.add_argument('--storage-root', type=Path, required=True)
    parser.add_argument('--offline-fixture', action='store_true')
    args = parser.parse_args()
    flow = 'bls' if module == 'bls' else args.flow
    sys.path.insert(0, str(ROOT / 'bots' / module / 'src'))
    # Cargar extensiones nativas antes de bloquear el hilo principal leyendo stdin.
    # NumPy en Windows puede bloquear su inicialización desde el trabajador.
    import pandas
    if module == 'bls':
        from .bls_identifiers import install_input_support
        install_input_support()
        from core.engine import BLSProcessor
        from input_files import load_input_file
    else:
        from manifest_scraper import ManifestScraper
        if flow in ('bases','bls_source'):
            from .bls_identifiers import install_base_support
            install_base_support()
    from chc_runtime.manifest_service import BatchService
    lock = threading.Lock()
    def emit(event, **data):
        with lock:
            print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)
    stop = threading.Event()
    reporter = ActivityReporter(emit)
    with reporter.session('Cargando bases de datos'):
        service = BatchService(args.storage_root, flow, emit, stop, args.offline_fixture)
    log_folder = args.storage_root / 'data' / 'logs'
    log_folder.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[EventLog(emit), logging.StreamHandler(sys.stderr),
                        logging.FileHandler(log_folder/(flow+'.log'),encoding='utf-8')],
                        format='%(asctime)s %(levelname)s %(message)s')
    active = None
    def execute(request):
        command = request['command']
        try:
            with reporter.session(COMMANDS.get(command, 'Procesando solicitud')):
                result = service.execute(command, request)
            emit('result', command=command, requestId=request.get('requestId'), **(result or {}))
        except asyncio.CancelledError:
            emit('result', command=command, requestId=request.get('requestId'), stopped=True)
        except Exception as exc:
            logging.exception('Falló el comando %s de %s.', command, flow)
            emit('error', command=command, requestId=request.get('requestId'), message=str(exc))
        finally:
            emit('idle', command=command, snapshot=service.snapshot())
    emit('ready', snapshot=service.snapshot())
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                command = request['command']
                if command in ('stop', 'shutdown'):
                    stop.set()
                    emit('stopping')
                    if command == 'shutdown':
                        break
                elif active and active.is_alive():
                    emit('error', command=command, message='Este procedimiento sigue trabajando; deténgalo antes de cambiarlo.')
                else:
                    stop.clear()
                    active = threading.Thread(target=execute, args=(request,), daemon=True)
                    active.start()
            except Exception as exc:
                emit('error', message=str(exc))
    finally:
        stop.set()
        if active:
            active.join(20)
            if active.is_alive():
                # El próximo inicio recupera reservas bajo el bloqueo de su lote.
                os._exit(0)
        service.close()
    return 0
