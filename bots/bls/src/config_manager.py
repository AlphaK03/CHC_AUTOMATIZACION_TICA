"""
config_manager.py
Handles loading and saving user-facing configuration.
Config is stored next to the application (never mixed with runtime state).
"""

import os
import json
from paths import APP_DIR

# All supported config keys and their default values.
DEFAULTS = {
    "sheet_name":                      "BLS",
    "cant_hilos":                      2,
    "output_base_path":                "",
    "max_retries":                     3,
    "timeout":                         30,
    "headless":                        True,
    "target_url":                      "https://ticaconsultas.hacienda.go.cr/Tica/hcgconocimientos.aspx",
    "fecha_inicio":                    "01/01/2025",
    "fecha_fin":                       "31/12/2025",
    "dates_from_input":                True,
    "reuse_context":                   True,
    "detail_strategy":                 "http",
    "batch_revision":                  "",
}


def _config_path():
    return os.path.join(APP_DIR, "config.json")


def load_config() -> dict:
    """Return config dict, filling any missing keys with defaults."""
    path = _config_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        for key, val in DEFAULTS.items():
            if key not in data:
                data[key] = val
        return data
    return dict(DEFAULTS)


def save_config(config: dict) -> None:
    """Persist only user-facing settings (DEFAULTS keys) to config.json."""
    to_save = {k: config[k] for k in DEFAULTS if k in config}
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=4, ensure_ascii=False)
