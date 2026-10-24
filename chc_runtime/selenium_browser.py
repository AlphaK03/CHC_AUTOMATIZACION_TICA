"""Navegador incluido: sustituye solo el arranque, conserva el extractor original."""
from .distribution import chromium_binary, daily_driver


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
