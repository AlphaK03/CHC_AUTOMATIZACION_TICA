"""Instala un Edge WebDriver propio y compatible, sin consultar TICA."""
from pathlib import Path
import argparse
import json
import os
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chc_runtime.selenium_browser import prepare_daily_browser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Protocolo para el arranque de Workbench.')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    cancelled = threading.Event()

    def emit(event, **data):
        print(json.dumps({'event': event, **data}, ensure_ascii=False) if args.json else data.get('message', ''), flush=True)

    def listen():
        try:
            os.read(sys.stdin.fileno(), 256)
        finally:
            cancelled.set()

    if args.json:
        threading.Thread(target=listen, daemon=True).start()
    try:
        result = prepare_daily_browser(log=lambda message: emit('log', message=message), cancelled=cancelled)
        emit('result', **result, message='Navegador listo para las bases diarias (' + result['version'] + ').')
        return 0
    except Exception as error:
        emit('error', message='No se pudo preparar el navegador: ' + str(error)
             + ' Ejecuta Instalar_Base_Diaria.bat para volver a intentarlo. Los pendientes se conservan.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
