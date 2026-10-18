"""Admitir números de manifiesto con una letra final sin cambiar fuentes copiadas.

El identificador completo siempre se conserva para firmas, SQLite y consultas.
La copia numérica se usa únicamente para reutilizar las demás validaciones del
original y su orden numérico de exportación. No representa otra consulta.
"""
from functools import wraps
import re
import sys


def _numeric_probe(mid):
    parts = str(mid).strip().split('-')
    if len(parts) != 5:
        return None
    match = re.fullmatch(r'([0-9]+)[A-Za-z]', parts[2])
    if not match:
        return None
    number = parts[2]
    parts[2] = match[1]
    return '-'.join(parts), number


def install_base_support():
    """Solo en el proceso de Manifiestos: generador automático y manual."""
    import bls_base
    if getattr(bls_base.manifest_identity, '_workbench_suffix_support', False):
        return
    original_identity = bls_base.manifest_identity
    original_normalize = bls_base.normalize_record

    @wraps(original_identity)
    def manifest_identity(mid):
        probe = _numeric_probe(mid)
        if probe is None:
            return original_identity(mid)
        parts, day = original_identity(probe[0])
        parts[2] = probe[1]
        return parts, day

    @wraps(original_normalize)
    def normalize_record(record):
        mid = str(record.get('IDManifiesto', '')).strip()
        probe = _numeric_probe(mid)
        if probe is None:
            return original_normalize(record)
        values = original_normalize({**record, 'IDManifiesto': probe[0]})
        return (mid, *values[1:])

    manifest_identity._workbench_suffix_support = True
    bls_base.manifest_identity = manifest_identity
    bls_base.normalize_record = normalize_record


def install_input_support():
    """Solo en el proceso BLs; conserva las claves y firmas de entradas numéricas."""
    from core import inputs
    if getattr(inputs.input_job, '_workbench_suffix_support', False):
        return
    original_input = inputs.input_job

    @wraps(original_input)
    def input_job(record, ordinal):
        job = original_input(record, ordinal)
        probe = _numeric_probe(job['record'].get('IDManifiesto', ''))
        if not job['error'] or probe is None:
            return job
        validated = original_input({**job['record'], 'IDManifiesto': probe[0]}, ordinal)
        job['error'] = validated['error']
        if not job['error']:
            job['record'].update(ID2=validated['record']['ID2'], ID3=probe[1],
                                 ID4=validated['record']['ID4'])
        return job

    input_job._workbench_suffix_support = True
    inputs.input_job = input_job
    # También cubrir consumidores que precargaron el motor antes del adaptador.
    for name in ('core.store', 'chc_runtime.bls_session'):
        consumer = sys.modules.get(name)
        if consumer is not None and getattr(consumer, 'input_job', None) is original_input:
            consumer.input_job = input_job
