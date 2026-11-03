"""Presupuesto de cálculo nativo, separado de los trabajadores de descarga.

Aplicar únicamente dentro del proceso de un motor y antes de importar NumPy.
OpenBLAS puede comprometer cientos de MiB por proceso al crear su pool, aunque
el motor solo use pandas para texto y agrupaciones. No limita asyncio, Qt,
Playwright, ni los hilos elegidos por el usuario para consultar TICA.
"""
import os


VARIABLES = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
             'BLIS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')


def configure():
    # La configuración del entorno anfitrión puede incluir OPENBLAS_NUM_THREADS
    # elevado. El presupuesto propio del motor debe prevalecer sobre ese valor.
    # Una anulación explícita facilita comparar rendimientos sin cambiar código.
    value = os.environ.get('CHC_NUMERIC_THREADS', '1')
    try:
        threads = int(value)
        if not 1 <= threads <= 64:
            raise ValueError()
    except (TypeError, ValueError):
        threads = 1
    for name in VARIABLES:
        os.environ[name] = str(threads)
    return threads
