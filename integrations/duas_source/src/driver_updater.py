"""Detección y actualización de Microsoft Edge WebDriver."""

import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import winreg
import xml.etree.ElementTree as ET
import zipfile
from typing import Callable

BASE_URL = "https://msedgedriver.microsoft.com"
DEST_FILE = "msedgedriver.exe"

_REGISTRY_LOCATIONS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\BLBeacon", "version"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}", "pv"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}", "pv"),
]


def get_edge_version() -> str:
    """Lee la versión instalada de Edge del registro de Windows."""
    for hive, subkey, value_name in _REGISTRY_LOCATIONS:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                version, _ = winreg.QueryValueEx(key, value_name)
            version = version.strip()
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version) and version != "0.0.0.0":
                return version
        except OSError:
            continue
    raise RuntimeError(
        "No se encontró la versión de Microsoft Edge en el registro de Windows.\n"
        "Asegúrese de tener Edge instalado."
    )


def get_current_driver_version(driver_path: str) -> str | None:
    """Devuelve la versión de un msedgedriver.exe, si existe y responde."""
    if not os.path.isfile(driver_path):
        return None
    try:
        result = subprocess.run(
            [driver_path, "--version"], capture_output=True, text=True, timeout=10,
        )
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", result.stdout)
        return match.group(1) if result.returncode == 0 and match else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_latest_compatible_version(edge_version: str) -> str:
    """Busca la revisión más nueva publicada para la misma compilación de Edge."""
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", edge_version):
        raise ValueError(f"Versión de Edge inválida: {edge_version}")
    build = ".".join(edge_version.split(".")[:3])
    marker = ""
    versions = set()
    try:
        while True:
            params = urllib.parse.urlencode({
                "restype": "container", "comp": "list",
                "prefix": build + ".", "marker": marker,
            })
            with urllib.request.urlopen(f"{BASE_URL}/?{params}", timeout=30) as response:
                root = ET.fromstring(response.read())
            for item in root.findall("./Blobs/Blob/Name"):
                name = item.text or ""
                if name.endswith("/edgedriver_win64.zip"):
                    version = name.split("/", 1)[0]
                    if re.fullmatch(re.escape(build) + r"\.\d+", version):
                        versions.add(version)
            marker = root.findtext("NextMarker") or ""
            if not marker:
                break
    except (urllib.error.URLError, ET.ParseError) as exc:
        raise RuntimeError(f"No se pudo consultar las versiones de Edge WebDriver: {exc}") from exc
    if not versions:
        raise RuntimeError(
            f"Microsoft aún no ha publicado Edge WebDriver para la compilación {build}."
        )
    return max(versions, key=lambda version: tuple(map(int, version.split("."))))


def download_driver(
    version: str,
    driver_path: str,
    progress_callback: Callable[[float, int], None] | None = None,
) -> str:
    """Descarga, verifica y reemplaza el driver en la ruta configurada."""
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise ValueError(f"Versión de driver inválida: {version}")
    driver_path = os.path.abspath(driver_path)
    dest_dir = os.path.dirname(driver_path)
    os.makedirs(dest_dir, exist_ok=True)
    url = f"{BASE_URL}/{version}/edgedriver_win64.zip"

    # El archivo anterior permanece intacto si la descarga o extracción falla.
    with tempfile.TemporaryDirectory(dir=dest_dir, prefix="edgedriver_") as tmp_dir:
        zip_path = os.path.join(tmp_dir, "edgedriver.zip")
        staged_exe = os.path.join(tmp_dir, DEST_FILE)
        try:
            with urllib.request.urlopen(url, timeout=60) as response, open(zip_path, "wb") as out:
                total = int(response.headers.get("Content-Length") or 0)
                downloaded = 0
                while chunk := response.read(1024 * 256):
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(min(downloaded / total * 100, 100), downloaded // 1024)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Error HTTP {exc.code} al descargar Edge WebDriver {version}.\n{url}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"No se pudo descargar Edge WebDriver.\n{url}\n{exc}") from exc

        try:
            with zipfile.ZipFile(zip_path) as archive:
                exe_name = next((name for name in archive.namelist()
                                 if name.replace("\\", "/").split("/")[-1].lower() == DEST_FILE), None)
                if not exe_name:
                    raise RuntimeError("El archivo descargado no contiene msedgedriver.exe.")
                with archive.open(exe_name) as src, open(staged_exe, "wb") as dst:
                    while chunk := src.read(1024 * 256):
                        dst.write(chunk)
        except (zipfile.BadZipFile, OSError) as exc:
            raise RuntimeError(f"No se pudo extraer Edge WebDriver: {exc}") from exc

        if get_current_driver_version(staged_exe) != version:
            raise RuntimeError("La versión del driver descargado no coincide con la publicada.")
        try:
            os.replace(staged_exe, driver_path)
        except OSError as exc:
            raise RuntimeError(
                f"No se pudo reemplazar {driver_path}. Cierre los procesos que usen el driver "
                f"y compruebe los permisos.\n{exc}"
            ) from exc
    return driver_path
