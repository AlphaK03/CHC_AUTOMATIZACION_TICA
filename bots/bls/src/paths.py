"""
paths.py
Single source of truth for the application's writable base directory.

When running as a frozen .exe (PyInstaller):
    sys.executable  ->  path/to/BLs_BOT_AstraCode.exe
    sys._MEIPASS    ->  temp extraction dir (read-only bundled code)
    APP_DIR         ->  directory containing the .exe  ← writable

When running as a plain Python script (development):
    APP_DIR         ->  repository root, above src/
"""

import os
import sys


def _resolve() -> str:
    if getattr(sys, "frozen", False):
        # Frozen: write next to the .exe, not in the temp _MEIPASS dir
        return os.path.dirname(sys.executable)
    # Development: use the repository root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


APP_DIR: str = _resolve()
