#utils.py
import os
import json
import logging

def load_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'config.json')
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)
    return config

def save_config(config):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'config.json')
    with open(config_path, 'w') as config_file:
        json.dump(config, config_file, indent=4)


def setup_logging(log_file='logs/debug.log'):
    from resultados import resolve_path
    log_file = resolve_path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
