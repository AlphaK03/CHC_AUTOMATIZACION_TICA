"""Instala Chromium con el driver incluido, también desde el ejecutable congelado."""
import asyncio
from collections import deque
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from playwright._impl._driver import compute_driver_executable, get_driver_env
from playwright.async_api import Error as PlaywrightError
from core.internet import ConnectionWaitStopped


class BrowserSetupCancelled(Exception):
    """Detención solicitada durante la preparación del navegador."""


def configure_browser_cache():
    # El directorio temporal de PyInstaller no sirve como instalación persistente.
    if getattr(sys, 'frozen', False) and os.environ.get('LOCALAPPDATA') and not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(os.environ['LOCALAPPDATA']) / 'ms-playwright')


def _notify(callback, stage, message):
    logging.info(message)
    if callback:
        callback(stage, message)


async def _terminate_installer(process):
    if process.returncode is not None:
        return
    if os.name == 'nt':
        # El CLI crea un hijo para la descarga. Cerrar solo node.exe deja ese hijo vivo.
        killer = await asyncio.create_subprocess_exec(
            'taskkill', '/PID', str(process.pid), '/T', '/F',
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        await killer.wait()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(process.wait(), 3)
    except asyncio.TimeoutError:
        if os.name == 'nt':
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await process.wait()


async def install_chromium(stop_event, on_status=None, timeout=900):
    if stop_event.is_set():
        raise BrowserSetupCancelled()
    node, cli = compute_driver_executable()
    env = get_driver_env()
    env['CI'] = '1'
    # Otros bots pueden necesitar revisiones diferentes del navegador.
    env['PLAYWRIGHT_SKIP_BROWSER_GC'] = '1'
    env.setdefault('PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT', '120000')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
    _notify(on_status, 'installing', 'Falta Chromium. Descargando el navegador necesario; requiere conexión a Internet…')
    try:
        process = await asyncio.create_subprocess_exec(
            node, cli, 'install', 'chromium', '--no-progress', env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **options)
    except OSError as exc:
        raise RuntimeError('No se pudo abrir el instalador incluido de Chromium. '
                           'Revise los permisos de la carpeta y vuelva a pulsar Iniciar.') from exc
    tail = deque(maxlen=12)

    def log_line(line):
        line = line.strip()
        if not line:
            return
        tail.append(line)
        logging.info('Instalación Chromium: %s', line)
        if line.startswith('Downloading'):
            if 'Headless' in line:
                message = 'Descargando el componente de Chromium para trabajar en segundo plano…'
            elif 'Chrome' in line or 'Chromium' in line:
                message = 'Descargando Chromium… La primera instalación puede tardar varios minutos.'
            else:
                message = 'Descargando componentes necesarios del navegador…'
            if on_status:
                on_status('installing', message)

    async def read_output():
        buffer = ''
        while chunk := await process.stdout.read(4096):
            buffer += chunk.decode('utf-8', errors='replace').replace('\r', '\n')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                log_line(line)
        log_line(buffer)

    reader = asyncio.create_task(read_output())
    waiter = asyncio.create_task(process.wait())
    deadline = time.monotonic() + timeout
    try:
        while not waiter.done():
            if stop_event.is_set():
                raise BrowserSetupCancelled()
            if time.monotonic() >= deadline:
                raise RuntimeError('La descarga de Chromium superó el tiempo permitido. '
                                   'Revise su conexión y vuelva a pulsar Iniciar; el progreso se conserva.')
            await asyncio.wait({waiter}, timeout=.1)
        await reader
        if stop_event.is_set():
            raise BrowserSetupCancelled()
        if waiter.result() != 0:
            logging.error('El instalador terminó con código %s: %s', waiter.result(), '\n'.join(tail))
            raise RuntimeError('No se pudo descargar Chromium. Revise la conexión a Internet, '
                               'el espacio disponible y los permisos; después pulse Iniciar para reintentar. '
                               'Los datos guardados en SQLite se conservan.')
        _notify(on_status, 'verifying', 'Chromium descargado. Verificando que el navegador pueda abrirse…')
    finally:
        if process.returncode is None:
            await _terminate_installer(process)
        for task in (reader, waiter):
            if not task.done():
                task.cancel()
        await asyncio.gather(reader, waiter, return_exceptions=True)


async def launch_chromium(playwright, headless, stop_event, on_status=None, internet_guard=None, **launch_options):
    if stop_event.is_set():
        raise BrowserSetupCancelled()
    try:
        browser = await playwright.chromium.launch(headless=headless, **launch_options)
    except PlaywrightError as exc:
        # Un error de permisos, antivirus o cierre inesperado no prueba que falte Chromium.
        if "Executable doesn't exist at" not in str(exc):
            raise
        try:
            if internet_guard:
                await internet_guard.recover_if_offline(exc, force_probe=True)
            while True:
                try:
                    await install_chromium(stop_event, on_status)
                    break
                except RuntimeError as install_error:
                    if not internet_guard or not await internet_guard.recover_if_offline(install_error, force_probe=True):
                        raise
        except ConnectionWaitStopped:
            raise BrowserSetupCancelled() from None
        if stop_event.is_set():
            raise BrowserSetupCancelled()
        try:
            browser = await playwright.chromium.launch(headless=headless, **launch_options)
        except PlaywrightError as second:
            raise RuntimeError('Chromium se descargó, pero no pudo abrirse. '
                               'Revise los permisos o el antivirus y vuelva a pulsar Iniciar.') from second
        _notify(on_status, 'ready', 'Chromium instalado y verificado. Continuando con los BL pendientes…')
    if stop_event.is_set():
        await browser.close()
        raise BrowserSetupCancelled()
    return browser
