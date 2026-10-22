"""Rutas de distribución independientes del usuario y del lugar de instalación."""
import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]


def packaged():
    return (CODE_ROOT / 'distribution.json').is_file()


def data_root():
    override = os.environ.get('CHC_WORKBENCH_HOME')
    if override:
        return Path(override).expanduser().resolve()
    if packaged():
        local = os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData/Local')
        return Path(local) / 'CHC Consultores' / 'Workbench'
    return CODE_ROOT


def bot_data_root(module):
    return data_root() / 'bots' / module


def daily_driver():
    if packaged():
        return CODE_ROOT / '_runtime/selenium/chromedriver-win64/chromedriver.exe'
    return CODE_ROOT / 'integrations/duas_source/drivers/msedgedriver.exe'


def chromium_options():
    # Chromium completo admite ventana y headless; evita distribuir otro navegador.
    return {'channel': 'chromium'} if packaged() else {}


def missing_driver_message():
    if packaged():
        return 'Falta el navegador incluido. Vuelve a instalar CHC Workbench; tus bases y resultados se conservan.'
    return 'Ejecuta Instalar_Base_Diaria.bat antes de iniciar el modo diario.'


def chromium_binary():
    import json
    revision = json.loads((CODE_ROOT / 'distribution.json').read_text(encoding='utf-8'))['chromium_revision']
    return CODE_ROOT / '_runtime/browsers' / ('chromium-' + revision) / 'chrome-win64/chrome.exe'


def configure_environment():
    if packaged():
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(CODE_ROOT / '_runtime/browsers')
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        os.environ['PYTHONUTF8'] = '1'


configure_environment()
