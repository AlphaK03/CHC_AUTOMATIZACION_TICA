"""Proceso de exportación online separado de Qt y de todos los bots."""
import argparse
import json
from pathlib import Path
import sys

from .service import CloudService
from .auth import AuthenticationRequired
from .graph import GraphError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage',required=True,type=Path)
    parser.add_argument('--app',required=True,type=Path)
    args = parser.parse_args()
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8',line_buffering=True)
    service = CloudService(args.storage,json.loads(args.app.read_text(encoding='utf-8')))
    def emit(value):
        print(json.dumps(value,ensure_ascii=False),flush=True)
    emit({'event':'ready'})
    try:
        for line in sys.stdin:
            request = json.loads(line)
            if request['command']=='shutdown':
                break
            try:
                emit({'event':'result','command':request['command'],**service.execute(request)})
            except Exception as error:
                message = str(error) if isinstance(error,(ValueError,GraphError,AuthenticationRequired)) else 'SharePoint no está disponible. El trabajo local continúa; puedes volver a intentar la conexión o publicación.'
                emit({'event':'error','command':request['command'],'message':message})
            emit({'event':'idle'})
    finally:
        service.db.close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
