"""Descarga por rondas con subdivisión persistente de los rangos que fallan."""
from collections import defaultdict
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from urllib3.exceptions import ReadTimeoutError
from data_store import RangeStore, RunLock, ranges_for, period_for
from tica_dua_bot import TICADUAExtractor, Cancelled


def error_message(exc):
    if isinstance(exc, (TimeoutException, ReadTimeoutError)):
        return 'La consulta tardó demasiado en responder.'
    if isinstance(exc, StaleElementReferenceException):
        return 'La página cambió durante la consulta.'
    return 'No se pudo completar la consulta. El detalle del error quedó guardado.'


def run_downloads(database, config, regimens, month, year, mode, log, cancel,
                  start=None, end=None, refresh=False, factory=TICADUAExtractor):
    period = period_for(month, year)
    ranges = ranges_for(period, mode, start, end)
    with RunLock(database):
        store = RangeStore(database)
        browser = None
        try:
            ids = store.plan(period, regimens, ranges, refresh)
            attempts = defaultdict(int)
            round_number = 0
            while not cancel.is_set():
                work = [key for key in store.work_items(ids)
                        if store.get(key)['status'] != 'succeeded' and attempts[key] < 3]
                if not work:
                    break
                round_number += 1
                for query_id in work:
                    if cancel.is_set():
                        break
                    query = store.get(query_id)
                    attempts[query_id] += 1
                    log(f'Consultando {query["regimen"]}: {query["day_start"]}–{query["day_end"]} de {month} {year}. Intento {attempts[query_id]}/3.')
                    store.start(query_id)
                    try:
                        if browser is None:
                            browser = factory(config, log_callback=log, cancel_event=cancel)
                        records = browser.fetch_range(query['regimen'], period, query['day_start'], query['day_end'])
                        if cancel.is_set():
                            raise Cancelled('Consulta detenida.')
                    except Cancelled:
                        store.fail(query_id, 'Descarga detenida.', cancelled=True)
                        cancel.set()
                        break
                    except Exception as exc:
                        store.fail(query_id, exc)
                        log(f'{query["regimen"]}: pendiente. {error_message(exc)}')
                        # A failure to launch Edge is not evidence of a heavy
                        # range. Retry it without multiplying work by day.
                        if browser is not None and not cancel.is_set():
                            parts = store.split(query_id)
                            if parts:
                                labels = [f'{store.get(key)["day_start"]}–{store.get(key)["day_end"]}' for key in parts]
                                log(f'{query["regimen"]}: se consultarán por separado los días {" y ".join(labels)} en la siguiente ronda.')
                        if browser is not None:
                            try:
                                browser.close()
                            except Exception:
                                pass
                            browser = None
                    else:
                        count = store.complete(query_id, records)
                        log(f'{query["regimen"]}: rango guardado, {count:,} DUAs.')
                remaining = [key for key in store.work_items(ids)
                             if store.get(key)['status'] != 'succeeded' and attempts[key] < 3]
                if cancel.is_set() or not remaining:
                    break
                log('Continuando con las partes pendientes al terminar la ronda.')
                cancel.wait(min(2 ** min(round_number, 3), 8))
            pending = sum(not store.is_complete(key) for key in ids)
            log(f'Rangos guardados: {len(ids)-pending}/{len(ids)}. Pendientes: {pending}.')
            return pending
        finally:
            try:
                if browser is not None:
                    browser.close()
            finally:
                store.close()
