"""Ejecuta la aplicación desde la raíz del repositorio."""
import runpy
import sys
from pathlib import Path

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
    runpy.run_module('main', run_name='__main__')
