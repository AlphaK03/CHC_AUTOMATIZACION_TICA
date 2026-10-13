"""Instala un Edge WebDriver propio y compatible, sin consultar TICA."""
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'integrations' / 'duas_source'
sys.path.insert(0, str(SOURCE / 'src'))
import driver_updater

edge = driver_updater.get_edge_version()
destination = SOURCE / 'drivers' / 'msedgedriver.exe'
installed = driver_updater.get_current_driver_version(str(destination))
if not installed or installed.split('.')[:3] != edge.split('.')[:3]:
    version = driver_updater.get_latest_compatible_version(edge)
    driver_updater.download_driver(version, str(destination))
    print('Edge WebDriver instalado:', version)
else:
    print('Edge WebDriver compatible:', installed)
