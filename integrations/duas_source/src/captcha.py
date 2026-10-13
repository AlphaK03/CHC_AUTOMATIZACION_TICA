import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlsplit


@lru_cache(maxsize=1)
def lookup():
    root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    data = json.loads((root / 'config/captcha_lookup.json').read_text(encoding='utf-8'))
    if not data or any(not key.isdigit() or not isinstance(value, str) or not value.strip() for key, value in data.items()):
        raise ValueError('Catálogo de CAPTCHA inválido.')
    return MappingProxyType(data)


def word_for(url):
    match = re.search(r'/Captcha/images/(\d+)\.jpg$', urlsplit(url).path, re.I)
    if not match or str(int(match[1])) not in lookup():
        raise ValueError('El CAPTCHA no está en el catálogo. La consulta queda pendiente.')
    return lookup()[str(int(match[1]))]
