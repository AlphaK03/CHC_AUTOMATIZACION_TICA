"""browser.py — Fábrica del navegador Edge."""
import atexit
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time

import urllib3
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions

# Aumenta el pool de conexiones de urllib3 (Selenium lo usa internamente).
# Por defecto maxsize=1, lo que fuerza reconexiones TCP constantes a localhost.
_defaults = urllib3.connectionpool.HTTPConnectionPool.__init__.__defaults__
urllib3.connectionpool.HTTPConnectionPool.__init__.__defaults__ = tuple(
    10 if isinstance(d, int) and d == 1 else d for d in _defaults
)

_BLOCKED_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.css',
    '.woff', '.woff2', '.ttf', '.otf', '.svg',
)

# Nombre del archivo que guarda el PID de msedgedriver dentro de cada carpeta de sesión.
# Permite al limpiador de huérfanos matar el proceso sin tener referencia al objeto Service.
_PID_FILENAME = 'msedgedriver.pid'

# Directorio base del bot: junto al .exe en producción, raíz del proyecto en desarrollo.
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BOT_TEMP_BASE = os.path.join(_BASE_DIR, 'temp', 'edge')

# Registro de sesiones activas — sus carpetas NO se tocan durante la limpieza periódica.
_active_sessions: set[str] = set()
_active_sessions_lock = threading.Lock()


# ── Utilidades de proceso ────────────────────────────────────────────────────

def _force_kill_pid(pid: int) -> None:
    """
    Mata un PID y todo su árbol de procesos hijos con taskkill /F /T.
    Esto libera los file handles sobre la carpeta de perfil de Edge.
    """
    try:
        subprocess.run(
            ['taskkill', '/F', '/T', '/PID', str(pid)],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


def _force_kill_service(service) -> None:
    """
    Mata el proceso msedgedriver (y sus hijos Edge) referenciado por el objeto Service.
    Se usa cuando tenemos la referencia en memoria (sesiones propias).
    """
    proc = getattr(service, 'process', None)
    if proc is None:
        return
    pid = getattr(proc, 'pid', None)
    if pid is not None:
        _force_kill_pid(pid)
    # Fallback vía subprocess.Popen.kill() por si taskkill falla
    try:
        proc.kill()
    except Exception:
        pass


def _kill_orphan_by_pid_file(session_dir: str) -> None:
    """
    Lee el archivo PID guardado en la carpeta de sesión y mata ese proceso.
    Se usa para sesiones huérfanas de runs anteriores que crashearon.
    """
    pid_path = os.path.join(session_dir, _PID_FILENAME)
    if not os.path.exists(pid_path):
        return
    try:
        with open(pid_path, 'r') as f:
            pid = int(f.read().strip())
        _force_kill_pid(pid)
    except Exception:
        pass


# ── Limpieza de carpetas ──────────────────────────────────────────────────────

def _safe_rmtree(path: str, retries: int = 8, delay: float = 1.5) -> None:
    """
    Elimina `path` con robustez para Windows:
    - onerror quita el flag read-only antes de reintentar
    - Reintenta hasta `retries` veces con `delay` segundos de espera
    """
    def _onerror(func, p, _):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    for attempt in range(retries):
        if not os.path.exists(path):
            return
        try:
            shutil.rmtree(path, onerror=_onerror)
            if not os.path.exists(path):
                return
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(delay)


def _cleanup_session(session_dir: str, service=None) -> None:
    """
    Cierra limpiamente una sesión: mata el proceso y borra la carpeta.

    - Si `service` está disponible (sesión propia) usa _force_kill_service.
    - Si no (sesión huérfana) lee el PID del archivo guardado en la carpeta.
    """
    if service is not None:
        _force_kill_service(service)
    else:
        _kill_orphan_by_pid_file(session_dir)

    with _active_sessions_lock:
        _active_sessions.discard(session_dir)

    _safe_rmtree(session_dir)


def _cleanup_orphans(base: str, interval: int = 300) -> None:
    """
    Hilo daemon: cada `interval` segundos elimina las carpetas de `base` que
    no correspondan a una sesión activa (huérfanas de crashes anteriores).

    Para cada carpeta huérfana:
      1. Lee el PID del archivo msedgedriver.pid y mata el proceso (si sigue vivo).
      2. Borra la carpeta con _safe_rmtree.

    Así no importa si hay sesiones activas en `base` — solo se tocan las inactivas.
    """
    while True:
        if os.path.isdir(base):
            with _active_sessions_lock:
                active = set(_active_sessions)
            for entry in os.listdir(base):
                path = os.path.join(base, entry)
                if os.path.isdir(path) and path not in active:
                    # Matar proceso primero, luego borrar
                    _kill_orphan_by_pid_file(path)
                    _safe_rmtree(path)
        threading.Event().wait(interval)


# Inicia el hilo de limpieza una sola vez al importar el módulo.
threading.Thread(
    target=_cleanup_orphans,
    args=(_BOT_TEMP_BASE,),
    daemon=True,
    name='edge-temp-cleanup',
).start()


# ── Fábrica del driver ────────────────────────────────────────────────────────

def create_edge_driver(driver_path: str, headless: bool = False) -> webdriver.Edge:
    """
    Crea y retorna una instancia de Edge WebDriver optimizada para scraping.

    Ciclo de vida de la sesión:
      1. Se crea una carpeta temporal exclusiva en temp/edge/
      2. El PID de msedgedriver se guarda en msedgedriver.pid dentro de esa carpeta
      3. Al llamar quit() (aunque falle), se mata el proceso y se borra la carpeta
      4. Un hilo daemon limpia cada 5 min carpetas huérfanas de crashes anteriores,
         usando el archivo PID para matar el proceso correspondiente sin importar
         si hay otras sesiones activas en ese momento.
    """
    os.makedirs(_BOT_TEMP_BASE, exist_ok=True)
    session_dir = tempfile.mkdtemp(dir=_BOT_TEMP_BASE)

    with _active_sessions_lock:
        _active_sessions.add(session_dir)
    # Seguridad adicional: limpiar al salir del proceso aunque no se llame quit()
    atexit.register(_cleanup_session, session_dir)

    options = EdgeOptions()
    options.add_argument(f'--user-data-dir={session_dir}')
    if headless:
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
    for arg in (
        '--disable-extensions',
        '--disable-popup-blocking',
        '--disable-notifications',
        '--mute-audio',
        '--no-first-run',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
        '--disable-translate',
        '--disable-features=NetworkService',
        '--disable-blink-features=AutomationControlled',
    ):
        options.add_argument(arg)

    service = EdgeService(executable_path=driver_path)
    driver = webdriver.Edge(service=service, options=options)

    # Guardar el PID de msedgedriver en la carpeta de sesión.
    # Esto permite al limpiador de huérfanos matar el proceso incluso después de un crash.
    try:
        pid_path = os.path.join(session_dir, _PID_FILENAME)
        with open(pid_path, 'w') as f:
            f.write(str(service.process.pid))
    except Exception:
        pass

    # Intercepta quit() para garantizar cleanup aunque la sesión ya esté muerta.
    # NO se llama a _original_quit() porque bloquea hasta 20 segundos cuando la
    # sesión está caída (urllib3 reintenta la conexión al msedgedriver muerto).
    # taskkill /F /T es suficiente: mata msedgedriver + todos los hijos Edge.
    def _quit_and_cleanup():
        # Matar proceso y borrar carpeta en daemon thread → retorna inmediatamente.
        # El worker puede crear el nuevo browser sin esperar el cleanup del viejo.
        threading.Thread(
            target=_cleanup_session,
            args=(session_dir,),
            kwargs={'service': service},
            daemon=True,
            name='edge-session-cleanup',
        ).start()

    driver.quit = _quit_and_cleanup

    def _interceptor(request):
        if any(request.path.endswith(ext) for ext in _BLOCKED_EXTENSIONS):
            request.abort()

    driver.request_interceptor = _interceptor
    return driver
