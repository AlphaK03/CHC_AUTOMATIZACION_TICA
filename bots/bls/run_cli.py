"""Ejecuta la consola del bot desde cualquier carpeta de trabajo."""
import runpy
import sys
from pathlib import Path

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
    runpy.run_module('cli', run_name='__main__')
