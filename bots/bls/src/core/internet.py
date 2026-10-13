"""Pausa compartida por cortes de Internet; errores del portal conservan sus límites."""
import asyncio
import logging
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout


class ConnectionWaitStopped(Exception):
    pass


def transport_error(exc):
    if isinstance(exc, (PlaywrightTimeout, ConnectionError, TimeoutError)):
        return True
    text = str(exc).lower()
    return any(token in text for token in ('err_internet_disconnected', 'err_network_changed',
        'err_name_not_resolved', 'err_connection', 'enetunreach', 'ehostunreach', 'enotfound',
        'eai_again', 'econnreset', 'etimedout', 'getaddrinfo', 'network is unreachable'))


async def probe_internet(playwright):
    """Dos destinos HTTPS independientes de TICA. HTTP/SSL no se interpreta como corte."""
    context = await playwright.request.new_context()
    async def probe(url):
        try:
            response = await context.get(url, timeout=5000)
            await response.dispose()
            return 'online'
        except (PlaywrightError, OSError) as exc:
            return 'offline' if transport_error(exc) else 'unknown'
    try:
        states = await asyncio.gather(probe('https://www.microsoft.com/favicon.ico'),
                                      probe('https://www.cloudflare.com/cdn-cgi/trace'))
        if 'online' in states:
            return 'online'
        return 'offline' if all(state == 'offline' for state in states) else 'unknown'
    finally:
        await context.dispose()


class InternetGuard:
    def __init__(self, probe, stop_event, on_status=None, interval=10):
        self.probe, self.stop_event, self.on_status = probe, stop_event, on_status
        self.interval = interval
        self.online = asyncio.Event()
        self.online.set()
        self.lock = asyncio.Lock()
        self.generation = 0
        self.pauses = 0
        self.checks = 0

    async def wait_until_online(self):
        while not self.online.is_set():
            if self.stop_event.is_set():
                raise ConnectionWaitStopped()
            await asyncio.sleep(.1)
        if self.stop_event.is_set():
            raise ConnectionWaitStopped()

    async def _probe(self):
        self.checks += 1
        try:
            return await self.probe()
        except Exception:
            logging.exception('No se pudo verificar la conexión; se conservan los límites de reintento')
            return 'unknown'

    async def recover_if_offline(self, error, force_probe=False, generation=None):
        if not force_probe and not transport_error(error):
            return False
        observed = self.generation if generation is None else generation
        if not self.online.is_set():
            await self.wait_until_online()
            return True
        if self.generation != observed:
            return True
        async with self.lock:
            if self.stop_event.is_set():
                raise ConnectionWaitStopped()
            # Otro trabajador confirmó el corte y ya esperó por todos.
            if self.generation != observed:
                return True
            if await self._probe() != 'offline':
                return False
            self.online.clear()
            self.generation += 1
            self.pauses += 1
            message = 'Sin conexión a Internet. Esperando reconexión; puede pulsar Detener.'
            logging.warning(message)
            if self.on_status:
                self.on_status('network_wait', message)
            try:
                while not self.stop_event.is_set():
                    remaining = self.interval
                    while remaining > 0 and not self.stop_event.is_set():
                        await asyncio.sleep(min(.1, remaining))
                        remaining -= .1
                    if self.stop_event.is_set():
                        raise ConnectionWaitStopped()
                    state = await self._probe()
                    if state != 'offline':
                        # Una verificación inconclusa no autoriza una espera indefinida.
                        message = 'Conexión recuperada. Reanudando los BL pendientes.' if state == 'online' else \
                                  'Verificación de conexión inconclusa. Se mantienen los reintentos limitados.'
                        logging.info(message)
                        if self.on_status:
                            self.on_status('network_resumed', message)
                        return state == 'online'
                raise ConnectionWaitStopped()
            finally:
                self.online.set()
