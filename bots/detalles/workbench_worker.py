"""Entrada aislada de detalles; protocolo y persistencia comunes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime import worker
if __name__ == '__main__':
    raise SystemExit(worker.main('detalles'))
else:
    sys.modules[__name__] = worker
