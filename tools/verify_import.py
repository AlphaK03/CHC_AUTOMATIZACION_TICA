"""Verifica la copia inicial sin dependencias, importación de bots ni consultas."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tokenize

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'docs' / 'migration'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(base, value):
    path = (base / value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError(f'Ruta fuera de su raíz: {value}')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-sources', action='store_true',
                        help='Comprobar también fuentes y estado Git originales; solo lectura.')
    args = parser.parse_args()
    manifest = json.loads((REPORTS / 'import_manifest.json').read_text(encoding='utf-8'))
    registry = json.loads((ROOT / 'workbench' / 'modules.json').read_text(encoding='utf-8'))
    failures = []
    count = 0
    sources_checked = 0
    for item in [file for module in manifest['modules'] for file in module['files']] + manifest['generated_files']:
        path = safe_path(ROOT, item['destination'])
        if not path.is_file() or digest(path) != item['sha256']:
            failures.append(f"Archivo ausente o modificado: {item['destination']}")
        count += 1
    if args.check_sources:
        for module in manifest['modules']:
            for item in module['files']:
                source = Path(item['source'])
                if not source.is_file() or digest(source) != item['sha256']:
                    failures.append(f"La fuente cambió después de la copia: {item['source']}")
                sources_checked += 1
            result = subprocess.run(
                ['git', '-C', module['source_repository'], 'status', '--porcelain=v1', '--untracked-files=normal'],
                capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.returncode != 0 or result.stdout.strip().splitlines() != module['working_tree_status']:
                failures.append(f"El estado Git original cambió: {module['id']}")
    syntax_count = 0
    bot_sources = []
    for folder, directories, files in os.walk(ROOT / 'bots'):
        directories[:] = [name for name in directories if name not in {'.venv', 'venv', '__pycache__', '.git', 'build', 'dist', 'data', 'logs', 'output'}]
        bot_sources.extend(Path(folder) / name for name in files if name.endswith('.py'))
    for path in sorted(bot_sources) + sorted((ROOT / 'tools').glob('*.py')):
        try:
            with tokenize.open(path) as stream:
                ast.parse(stream.read(), filename=str(path))
            syntax_count += 1
        except (SyntaxError, UnicodeError) as error:
            failures.append(f'Sintaxis: {path.relative_to(ROOT)}: {error}')
    ids = [module['id'] for module in registry['modules']]
    if len(ids) != len(set(ids)) or set(ids) != {module['id'] for module in manifest['modules']}:
        failures.append('IDs duplicados o módulos distintos entre registro y manifiesto.')
    for module in registry['modules']:
        base = safe_path(ROOT, module['root'])
        for value in [module['entrypoint'], module['engine'], module['requirements'], *module['resources']]:
            if not safe_path(base, value).is_file():
                failures.append(f"Referencia ausente para {module['id']}: {value}")
        if (base / 'v2').exists():
            failures.append(f"El módulo {module['id']} no se normalizó a su raíz.")
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'ok': not failures, 'files_checked': count, 'python_syntax_checked': syntax_count,
              'modules_checked': len(ids), 'failures': failures,
              'source_files_checked': sources_checked,
              'original_git_status_checked': args.check_sources,
              'scope': 'copy_integrity_syntax_registry_only_no_bot_execution'}
    (REPORTS / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
