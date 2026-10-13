"""Portable user paths; extended Windows paths only for internal file I/O."""
import os
from pathlib import Path
import tempfile


def filesystem_path(path):
    raw = os.path.abspath(os.fspath(path))
    if os.name == 'nt' and not raw.startswith('\\\\?\\'):
        raw = '\\\\?\\UNC\\' + raw[2:] if raw.startswith('\\\\') else '\\\\?\\' + raw
    return Path(raw).resolve()


def display_path(path):
    raw = os.fspath(path)
    if os.name == 'nt':
        if raw.startswith('\\\\?\\UNC\\'):
            raw = '\\\\' + raw[8:]
        elif raw.startswith('\\\\?\\'):
            raw = raw[4:]
    return Path(raw)


def output_path(value, app_dir):
    raw = str(value or '').strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1].strip()
    path = Path(os.path.expandvars(raw or 'DUAs_2025')).expanduser()
    if not path.is_absolute():
        if path.drive:
            raise ValueError('Escribe una ruta completa con unidad y carpeta, o una carpeta relativa a la app.')
        path = Path(app_dir) / path
    return display_path(filesystem_path(path))


def prepare_output_folder(path):
    path = filesystem_path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(prefix='.comprobando-', dir=path):
            pass
    except PermissionError as exc:
        raise OSError(f'No hay permiso para escribir en la carpeta de salida: {display_path(path)}. '
                      'Elige una carpeta donde tu usuario pueda guardar archivos.') from exc
    except FileExistsError as exc:
        raise OSError(f'La ruta de salida corresponde a un archivo, no a una carpeta: {display_path(path)}.') from exc
    except OSError as exc:
        raise OSError(f'No se pudo crear o utilizar la carpeta de salida: {display_path(path)}. '
                      f'Comprueba que la unidad o ubicación esté disponible. Detalle: {exc}') from exc
    return path
