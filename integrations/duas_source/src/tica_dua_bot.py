"""Consulta Selenium con verificación de fechas y respuesta XML completa."""
from datetime import date
import re
from threading import Event
import unicodedata
import xml.etree.ElementTree as ET

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select

from captcha import word_for
from data_store import MONTHS, normalize_record
from query_confirmation import INSTALL_OBSERVER, confirmed_count

URL = 'https://ticaconsultas.hacienda.go.cr/Tica/hciduare.aspx'


class Cancelled(Exception):
    pass


def parse_date(value):
    parts = re.findall(r'\d+', value)
    if len(parts) != 3:
        raise ValueError('Fecha no reconocida en el formulario.')
    if len(parts[0]) == 4:
        year, month, day = map(int, parts)
    else:
        day, month, year = map(int, parts)
        if year < 100:
            year += 2000
    return date(year, month, day)


def parse_xml(raw):
    match = re.search(r'<root(?:\s[^>]*)?\s*/>', raw)
    if match:
        document = match[0]
    else:
        match = re.search(r'<root(?:\s[^>]*)?>', raw)
        end = raw.rfind('</root>')
        if not match or end < match.start():
            raise ValueError('El portal no entregó un XML completo.')
        document = raw[match.start():end + len('</root>')]
    root = ET.fromstring(document)
    if root.tag != 'root' or (root.text or '').strip() or any(child.tag != 'dua' for child in root):
        raise ValueError('La respuesta del portal no corresponde a una lista de DUAs.')
    result = []
    for dua in root:
        record = {field.tag: (field.text or '').strip() for field in dua}
        _, normalized = normalize_record(record)
        result.append(normalized)
    return result


class TICADUAExtractor:
    def __init__(self, config, log_callback=None, cancel_event=None):
        self.config = dict(config)
        self.log = log_callback or print
        self.cancel_event = cancel_event or Event()
        self.driver = self.get_browser_instance()

    def check_cancelled(self):
        if self.cancel_event.is_set():
            raise Cancelled('Descarga detenida; los rangos pendientes se conservan.')

    def wait(self, condition, seconds=15):
        def checked(driver):
            self.check_cancelled()
            return condition(driver)
        return WebDriverWait(self.driver, seconds, poll_frequency=.25).until(checked)

    def get_browser_instance(self):
        options = Options()
        if not self.config.get('mostrar_navegador', True):
            options.add_argument('--headless')
        for flag in ('--disable-extensions', '--disable-popup-blocking', '--disable-notifications',
                     '--disable-blink-features=AutomationControlled'):
            options.add_argument(flag)
        driver = webdriver.Edge(service=Service(self.config['edge_driver_path']), options=options)
        try:
            # ChromiumRemoteConnection uses 120 s by default in Selenium 4.28.
            # Configure this driver's HTTP requests (not a global setting) so
            # navigation can reach its own 180 s limit and return its error.
            driver.command_executor._client_config.timeout = 210
            # Las consultas del portal pueden tardar varios minutos en responder.
            # Es un máximo de navegación, no una pausa fija antes de continuar.
            driver.set_page_load_timeout(180)
        except Exception:
            driver.quit()
            raise
        return driver

    @staticmethod
    def normalizar_texto(value):
        return unicodedata.normalize('NFKD', value).encode('ASCII', 'ignore').decode().upper().strip()

    def seleccionar_fecha(self, expected, input_id):
        def active(driver):
            calendars = driver.find_elements(By.XPATH, "//div[contains(@class,'calendar') and contains(@style,'display: block')]")
            return calendars[-1] if calendars else False

        self.wait(EC.element_to_be_clickable((By.ID, input_id + '_dp_trigger'))).click()
        calendar = self.wait(active)
        title_path = ".//td[contains(@class,'calendartitle')]"
        for _ in range(240):
            self.check_cancelled()
            title = self.normalizar_texto(calendar.find_element(By.XPATH, title_path).text)
            match = re.fullmatch(r'([A-Z]+),?\s+(\d{4})', title)
            if not match or match[1] not in MONTHS:
                raise ValueError('No se reconoce el mes del calendario.')
            visible = (int(match[2]), MONTHS.index(match[1]) + 1)
            target = (expected.year, expected.month)
            if visible == target:
                break
            arrow = '‹' if visible > target else '›'
            calendar.find_element(By.XPATH, f".//td[contains(@class,'calendar-nav') and normalize-space(text())='{arrow}']").click()
            self.wait(lambda driver: active(driver) and self.normalizar_texto(active(driver).find_element(By.XPATH, title_path).text) != title)
            calendar = self.wait(active)
        else:
            raise ValueError('No se pudo seleccionar el mes solicitado.')
        calendar.find_element(By.XPATH, ".//td[contains(@class,'day') and not(contains(@class,'othermonth')) "
                              f"and normalize-space(text())='{expected.day}']").click()
        def selected(driver):
            try:
                return parse_date(driver.find_element(By.ID, input_id).get_attribute('value')) == expected
            except ValueError:
                return False
        self.wait(selected)
        self.driver.find_element(By.TAG_NAME, 'body').click()

    def fetch_range(self, regimen, period, start, end):
        self.check_cancelled()
        year, month = map(int, period.split('-'))
        initial, final = date(year, month, start), date(year, month, end)
        self.driver.get(URL)
        selector = self.wait(EC.presence_of_element_located((By.ID, 'vCODI_REGI')))
        Select(selector).select_by_visible_text(regimen)
        self.seleccionar_fecha(initial, 'vVFCHINI')
        self.seleccionar_fecha(final, 'vVFCHFIN')
        image = self.wait(EC.presence_of_element_located((By.CSS_SELECTOR, '#captchaImage img')))
        word = word_for(image.get_attribute('src'))
        captcha = self.driver.find_element(By.ID, '_cfield')
        self.driver.execute_script('''
            const input=arguments[0]; input.value=arguments[1];
            for (const kind of ['input','change','blur']) input.dispatchEvent(new Event(kind,{bubbles:true}));
        ''', captcha, word)
        self.wait(EC.element_to_be_clickable((By.NAME, 'BUTTON1')))
        values = self.driver.execute_script('''return {
            start: document.getElementById('vVFCHINI').value,
            end: document.getElementById('vVFCHFIN').value,
            regimen: document.getElementById('vCODI_REGI').selectedOptions[0].text.trim(),
            regimenCode: document.getElementById('vCODI_REGI').value,
            captcha: document.getElementById('_cfield').value
        };''')
        if (parse_date(values['start']) != initial or parse_date(values['end']) != final
                or self.normalizar_texto(values['regimen']) != self.normalizar_texto(regimen)
                or values['captcha'] != word):
            raise ValueError('El formulario cambió. No se envió la consulta.')
        self.check_cancelled()
        self.driver.execute_script(INSTALL_OBSERVER, values)
        submitted = self.driver.execute_script('''
            const before=arguments[0], select=document.getElementById('vCODI_REGI');
            if (document.getElementById('vVFCHINI').value !== before.start ||
                document.getElementById('vVFCHFIN').value !== before.end ||
                select.selectedOptions[0].text.trim() !== before.regimen ||
                document.getElementById('_cfield').value !== before.captcha) return false;
            document.getElementsByName('BUTTON1')[0].click(); return true;
        ''', values)
        if not submitted:
            raise ValueError('El formulario cambió antes del envío; la consulta queda pendiente.')
        def query_result(driver):
            state = driver.execute_script('return window.chcQueryConfirmation') or {}
            replies = state.get('requests', [])
            if len(replies) > 1:
                raise ValueError('Hubo varios envíos; no se puede confirmar un resultado único.')
            if replies and replies[0].get('done'):
                count = confirmed_count(replies[0], values)
                return 'empty' if count == 0 else 'xml'
            # Compatibilidad con respuestas XML directas y fixtures locales.
            # Esta vía nunca acredita un vacío por el contador del formulario.
            if EC.element_to_be_clickable((By.NAME, 'BUTTON6'))(driver):
                return 'xml'
            return False
        if self.wait(query_result, 300) == 'empty':
            self.log(f'{regimen}: TICA confirmó 0 DUAs para {initial}–{final}; '
                     'CAPTCHA aceptado, fechas y régimen verificados, sin mensajes de error.')
            return []
        self.wait(EC.element_to_be_clickable((By.NAME, 'BUTTON6')), 300).click()
        def complete_xml(driver):
            raw = driver.find_element(By.TAG_NAME, 'body').get_attribute('innerHTML')
            if re.search(r'<root(?:\s[^>]*)?\s*/>', raw) or ('<root' in raw and '</root>' in raw):
                return raw
            return False
        return parse_xml(self.wait(complete_xml, 300))

    def close(self):
        self.driver.quit()
