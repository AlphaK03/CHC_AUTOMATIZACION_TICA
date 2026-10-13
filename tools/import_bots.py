"""Plan y copia de las raíces activas; no importa ni ejecuta bots."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
REPORTS = ROOT / 'docs' / 'migration'
SOURCES = [
    ('bls', 'BLs_BOT', '', None),
    ('detalles', 'Detalles_BOT', '', None),
    ('duas_transito', 'DuasTransito BOT', 'v2', 'DuasTransitoBot_v2.spec'),
    ('talon', 'Talon_BOT', 'v2', 'TalonBot_v2.spec'),
    ('xmovimientos', 'XMovimientos_BOT', 'v2', 'XMovimientosBot_v2.spec'),
]
PRUNE = {
    '.git', '.venv', 'venv', 'node_modules', '.idea', '.claude', '__pycache__',
    '.pytest_cache', 'build', 'dist', 'data', 'output', 'outputs', 'logs',
    'tmp', 'temp', 'screenshots', 'descargas', 'codigo viejo', 'drivers',
}
CODE_EXTENSIONS = {'.py', '.md', '.bat', '.ps1', '.spec', '.toml', '.yml', '.yaml'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', check=True)
    return result.stdout.strip()


def included(relative, module):
    name = relative.name
    if relative.suffix.lower() in CODE_EXTENSIONS or name == '.gitattributes':
        return True
    # La política del monorepo sustituye los gitignore antiguos.
    if name == '.gitignore':
        return False
    if name == 'captcha_lookup.json' or name.endswith('.example.json'):
        return True
    if name.startswith('requirements') and relative.suffix == '.txt':
        return True
    if name.startswith('version_info') and relative.suffix == '.txt':
        return True
    if relative.suffix == '.html' and 'tests' in relative.parts:
        return True
    return module in {'duas_transito', 'talon', 'xmovimientos'} and relative.as_posix() == 'Names_TicaPortal.xlsx'


def record(source, destination):
    return {'source': str(source), 'destination': destination.as_posix(),
            'bytes': source.stat().st_size, 'sha256': digest(source)}


def build_plan():
    if (REPORTS / 'import_manifest.json').exists():
        raise RuntimeError('La importación inicial ya existe; conservar su manifiesto.')
    plan = {'schema_version': 1, 'created_at_utc': stamp(), 'modules': []}
    for module, folder, active, spec in SOURCES:
        repo = WORKSPACE / folder
        source_root = repo / active
        if not source_root.is_dir() or not (source_root / 'src' / 'main.py').is_file():
            raise RuntimeError(f'No existe la raíz activa esperada: {source_root}')
        files, excluded = [], []
        for directory, dirs, names in os.walk(source_root):
            current = Path(directory)
            for name in sorted(dirs):
                candidate = current / name
                if name.lower() in PRUNE or candidate.is_symlink():
                    excluded.append({'path': candidate.relative_to(source_root).as_posix(),
                                     'reason': 'operational_directory_or_link'})
            dirs[:] = sorted(name for name in dirs if name.lower() not in PRUNE
                             and not (current / name).is_symlink())
            for name in sorted(names):
                source = current / name
                relative = source.relative_to(source_root)
                if source.is_symlink() or not included(relative, module):
                    excluded.append({'path': relative.as_posix(), 'reason': 'outside_code_and_required_assets'})
                    continue
                files.append(record(source, Path('bots') / module / relative))
        if spec:
            source_spec = repo / spec
            if not source_spec.is_file():
                raise RuntimeError(f'Falta el spec de referencia: {source_spec}')
            files.append(record(source_spec, Path('bots') / module / 'docs' / 'reference' / spec))
        plan['modules'].append({
            'id': module, 'source_repository': str(repo), 'source_active_root': str(source_root),
            'destination_root': f'bots/{module}', 'branch': git(repo, 'branch', '--show-current'),
            'head_commit': git(repo, 'rev-parse', 'HEAD'),
            'working_tree_status': git(repo, 'status', '--porcelain=v1', '--untracked-files=normal').splitlines(),
            'excluded': excluded, 'files': files,
        })
    write_json(REPORTS / 'copy_plan.json', plan)
    for module in plan['modules']:
        print(f"{module['id']}: {len(module['files'])} archivos incluidos; raíz activa {module['source_active_root']}")


def extract_defaults(module_root):
    path = module_root / 'src' / 'utils.py'
    if not path.exists():
        return []
    defaults = []
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    mapping = {'_DEFAULT_MACHINE': 'machine.example.json', '_DEFAULT_SESSION': 'session.example.json'}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in mapping:
                    destination = module_root / 'config' / mapping[target.id]
                    if destination.exists():
                        raise RuntimeError(f'No se sobrescribe el ejemplo existente: {destination}')
                    write_json(destination, ast.literal_eval(node.value))
                    defaults.append(destination)
    return defaults


def copy_plan():
    if (REPORTS / 'import_manifest.json').exists():
        raise RuntimeError('La importación inicial ya existe; no se sobrescribirá.')
    plan = json.loads((REPORTS / 'copy_plan.json').read_text(encoding='utf-8'))
    # Preflight completo antes de escribir un solo archivo de bot.
    for module in plan['modules']:
        destination_root = ROOT / module['destination_root']
        if destination_root.exists():
            raise RuntimeError(f'El destino ya existe: {destination_root}')
        for item in module['files']:
            destination = (ROOT / item['destination']).resolve()
            if not destination.is_relative_to((ROOT / 'bots').resolve()):
                raise RuntimeError(f'Destino fuera de bots/: {destination}')
            if digest(Path(item['source'])) != item['sha256']:
                raise RuntimeError(f'La fuente cambió desde el plan: {item["source"]}')
    generated = []
    for module in plan['modules']:
        for item in module['files']:
            source, destination = Path(item['source']), ROOT / item['destination']
            destination.parent.mkdir(parents=True, exist_ok=True)
            # xb impide reemplazar cualquier archivo aparecido durante la copia.
            with source.open('rb') as src, destination.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            if digest(source) != item['sha256'] or digest(destination) != item['sha256']:
                raise RuntimeError(f'Integridad de copia incorrecta: {destination}')
        generated.extend(extract_defaults(ROOT / module['destination_root']))
        if module['id'] in {'duas_transito', 'talon', 'xmovimientos'}:
            requirements = ROOT / module['destination_root'] / 'requirements.runtime.txt'
            requirements.write_text(
                '# Imports del camino Playwright activo; pendiente de validar instalación.\n'
                'pandas==2.2.3\nopenpyxl==3.1.5\nbeautifulsoup4==4.12.3\n'
                'requests>=2.32,<3\nplaywright==1.62.0\n', encoding='utf-8')
            generated.append(requirements)
        print(f"Copiado {module['id']}: {len(module['files'])} archivos")
    manifest = {**plan, 'copied_at_utc': stamp(), 'generated_files': [
        {'destination': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)} for path in generated]}
    write_json(REPORTS / 'import_manifest.json', manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--plan', action='store_true')
    modes.add_argument('--copy', action='store_true')
    args = parser.parse_args()
    if args.plan:
        build_plan()
    else:
        copy_plan()


if __name__ == '__main__':
    main()
