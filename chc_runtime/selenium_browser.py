"""Arranque y comprobación local del navegador del proveedor diario."""
import os
from pathlib import Path

from .distribution import chromium_binary, daily_driver, missing_driver_message, packaged


def validate_daily_browser(driver_path=None):
    """Detectar incompatibilidad antes de consumir oportunidades del calendario.

    Solo lee versiones locales. La distribución usa su Chromium propio y no
    depende del Edge que Windows actualiza. Nunca descarga ni abre un navegador.
    """
    driver = Path(driver_path) if driver_path is not None else daily_driver()
    if not driver.is_file():
        raise RuntimeError(missing_driver_message())
    if packaged() or os.name != 'nt':
        return
    from integrations.duas_source.src.driver_updater import (
        get_current_driver_version, get_edge_version,
    )
    try:
        edge = get_edge_version()
    except RuntimeError as error:
        raise RuntimeError(f'{error} Ejecuta Instalar_Base_Diaria.bat antes de iniciar.') from error
    installed = get_current_driver_version(str(driver))
    if not installed:
        raise RuntimeError('No se pudo comprobar el controlador de Edge. '
                           'Ejecuta Instalar_Base_Diaria.bat antes de iniciar.')
    if installed.split('.')[:3] != edge.split('.')[:3]:
        raise RuntimeError(f'Edge {edge} y su controlador {installed} son incompatibles. '
                           'Ejecuta Instalar_Base_Diaria.bat y vuelve a iniciar. '
                           'Los días pendientes se conservan.')


def prepare_daily_browser(driver_path=None, log=lambda message: None, cancelled=None):
    """Actualizar solo el controlador propio cuando cambie la compilación Edge.

    Se ejecuta fuera de Qt. Publica el ejecutable verificado bajo bloqueo y
    conserva el anterior si la descarga falla o se cancela.
    """
    import tempfile
    from threading import Event
    from .job_store import RunLock
    cancelled = cancelled or Event()
    driver = Path(driver_path) if driver_path is not None else daily_driver()
    if packaged():
        validate_daily_browser(driver)
        return {'updated': False, 'version': 'incluido'}
    from integrations.duas_source.src import driver_updater

    def check_cancelled(*args):
        if cancelled.is_set():
            raise RuntimeError('Preparación del navegador cancelada; controlador anterior conservado.')

    with RunLock(str(driver) + '.actualizacion'):
        check_cancelled()
        log('Comprobando navegador para las bases diarias…')
        edge = driver_updater.get_edge_version()
        installed = driver_updater.get_current_driver_version(str(driver))
        if installed and installed.split('.')[:3] == edge.split('.')[:3]:
            return {'updated': False, 'version': installed}
        log('Actualizando navegador para las bases diarias…')
        version = driver_updater.get_latest_compatible_version(edge)
        check_cancelled()
        # El actualizador original también usa un temporal. Esta etapa adicional
        # impide reemplazar el controlador vigente tras una cancelación tardía.
        with tempfile.TemporaryDirectory(prefix='chc-driver-', dir=driver.parent) as folder:
            staged = Path(folder) / driver.name
            driver_updater.download_driver(version, str(staged), progress_callback=check_cancelled)
            check_cancelled()
            if (driver_updater.get_current_driver_version(str(staged)) != version
                    or version.split('.')[:3] != edge.split('.')[:3]):
                raise RuntimeError('El controlador descargado no corresponde al navegador instalado.')
            os.replace(staged, driver)
        return {'updated': True, 'version': version}


def bundled_extractor():
    from tica_dua_bot import TICADUAExtractor
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    class BundledExtractor(TICADUAExtractor):
        def get_browser_instance(self):
            options = Options()
            options.binary_location = str(chromium_binary())
            if not self.config.get('mostrar_navegador', True):
                options.add_argument('--headless')
            for flag in ('--disable-extensions', '--disable-popup-blocking', '--disable-notifications',
                         '--disable-blink-features=AutomationControlled'):
                options.add_argument(flag)
            driver = webdriver.Chrome(service=Service(str(daily_driver())), options=options)
            try:
                driver.command_executor._client_config.timeout = 210
                driver.set_page_load_timeout(180)
            except Exception:
                driver.quit()
                raise
            return driver
    return BundledExtractor
