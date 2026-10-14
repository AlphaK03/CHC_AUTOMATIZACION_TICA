"""Supervisión y cierre acotados, sin importar parsers ni dependencias de bots."""
import asyncio
import logging


class AttemptDeadline:
    def __init__(self, seconds):
        self.value = asyncio.get_running_loop().time() + seconds

    def reschedule(self, value):
        self.value = value


def _consume_result(task):
    if not task.cancelled():
        task.exception()


async def bounded_result(operation, timeout=5, deadline=None):
    """El supervisor no espera que Playwright acepte cancelar una operación."""
    task = asyncio.ensure_future(operation)
    task.add_done_callback(_consume_result)
    deadline = deadline or AttemptDeadline(timeout)
    try:
        while True:
            remaining = max(0, deadline.value - asyncio.get_running_loop().time())
            done, _ = await asyncio.wait({task}, timeout=remaining)
            if task in done:
                return task.result()
            # Tránsito puede renovar el plazo al confirmar otra página.
            if deadline.value <= asyncio.get_running_loop().time():
                raise TimeoutError('El intento excedió su plazo; se libera para reintentar.')
    except BaseException:
        if not task.done():
            task.cancel()
        raise


async def close_browser_resource(close, timeout=5):
    """Un navegador sin respuesta tampoco puede bloquear la cancelación del lote."""
    try:
        await bounded_result(close(), timeout=timeout)
        return True
    except Exception:
        logging.debug('No respondió el cierre del recurso del navegador.', exc_info=True)
        return False


