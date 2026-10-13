"""Compatibilidad clásica opcional, enteramente dentro de la copia del Workbench."""
import json
import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
if __name__ == '__main__':
    config = root/'config/config.json'
    if not config.exists():
        config.parent.mkdir(parents=True,exist_ok=True)
        config.write_text(json.dumps({'timeout_manifest':120,'headless':False},indent=2),encoding='utf-8')
    sys.path.insert(0,str(root/'src'))
    os.chdir(root/'src')
    runpy.run_path(str(root/'src/manifest_gui.py'),run_name='__main__')
