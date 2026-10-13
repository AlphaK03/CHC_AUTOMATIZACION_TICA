"""Compatibilidad de imports; coordinador diario común."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from chc_runtime.daily import *
