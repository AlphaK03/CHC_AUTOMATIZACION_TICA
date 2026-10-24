"""Build an isolated Windows x64 folder; never include local operational state.

Run with workbench/.venv/Scripts/python.exe distribution/windows/build.py --output ...
The output must not exist. No pip/install or changes to the source environments.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ENVS = ['workbench'] + ['bots/' + name for name in (
    'detalles', 'duas_transito', 'talon', 'xmovimientos', 'manifiestos', 'bls')]
RESOURCES = ['bots/' + name + '/config/captcha_lookup.json' for name in (
    'detalles', 'duas_transito', 'talon', 'xmovimientos')] + ['integrations/duas_source/config/captcha_lookup.json']
SKIP = {'__pycache__', 'site-packages', 'tests', 'test', 'testing', 'doc', 'docs', 'examples',
        'include', 'Include', 'cmake', 'glue', 'typesystems', 'scripts',
        'pip', '_distutils_hack', 'setuptools', 'wheel', 'ensurepip', 'idlelib',
        'turtledemo', 'distutils-precedence.pth'}


def excluded(path):
    return (any(part in SKIP or part.startswith(('pip-', 'setuptools-', 'wheel-')) for part in path.parts)
            or path.suffix.lower() in {'.pyc', '.pyo', '.pyi', '.pdb', '.lib', '.h', '.obj', '.cpp', '.a', '.prl', '.cmake'}
            or (path.parts[0] == 'PySide6' and (path.suffix.lower() == '.exe'
                or any(p in path.parts for p in ('FluentWinUI3', 'Imagine', 'Material', 'Universal', 'Fusion', 'Windows', 'macOS', 'iOS')))))


def files(path):
    if path.is_file():
        yield path, Path(path.name)
        return
    for folder, dirs, names in os.walk(path):
        dirs[:] = sorted(d for d in dirs if not excluded(Path(path.name) / Path(folder).relative_to(path) / d))
        for name in sorted(names):
            file = Path(folder) / name
            relative = Path(path.name) / file.relative_to(path)
            if not excluded(relative):
                yield file, relative


def copy_file(source, target):
    # CopyFile2 otherwise fails on deeply nested Qt assets in a long checkout path.
    target = Path('\\\\?\\' + str(target.resolve()))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2('\\\\?\\' + str(source.resolve()), target)


def copy_tree(source, target):
    for file, rel in files(source):
        copy_file(file, target / rel.relative_to(source.name))


def digest(path):
    h = hashlib.sha256()
    for file, relative in files(path):
        h.update(relative.as_posix().encode('utf-8'))
        with file.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                h.update(block)
    return h.hexdigest()


def copy_code(out):
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().split('\0')
    for name in sorted(set(tracked)):
        p = Path(name)
        if not name or not (ROOT / p).is_file() or any(x in p.parts for x in ('tests', 'docs', '__pycache__')):
            continue
        active = name.startswith(('chc_runtime/', 'chc_cloud/', 'workbench/', 'integrations/duas_source/'))
        bot = name.startswith('bots/') and ('src' in p.parts or p.name == 'workbench_worker.py')
        resource = name in RESOURCES
        if (active or bot or resource) and (p.name == 'qmldir' or p.suffix.lower() in {'.py', '.qml', '.js', '.json', '.svg', '.ico', '.png', '.ttf'}):
            if p.name in {'config.json', 'machine.json', 'session.json', 'manifest_prefs.json'}:
                continue
            copy_file(ROOT / p, out / p)
    # Resource JSONs can be ignored by an upstream source; require explicit files.
    for name in RESOURCES:
        copy_file(ROOT / name, out / name)


def runtimes(out, lock):
    base = Path(sys.base_prefix)
    if sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise RuntimeError('Build requires CPython 3.12 x64.')
    shared = out / '_runtime'
    for name in ('Lib', 'DLLs', 'tcl'):
        source = base / name
        for file, rel in files(source):
            if 'site-packages' not in rel.parts:
                copy_file(file, shared / 'python' / rel)
    copy_file(base / 'LICENSE.txt', shared / 'python/LICENSE.txt')
    candidates = defaultdict(list)
    inventory = {}
    for env in ENVS:
        site = ROOT / env / '.venv/Lib/site-packages'
        inventory[env] = []
        for item in sorted(site.iterdir()):
            if excluded(Path(item.name)) or item.name.startswith(('playwright-', 'playwright.')) or item.name == 'playwright':
                continue
            if item.suffix == '.dist-info':
                inventory[env].append(item.name.removesuffix('.dist-info'))
            candidates[item.name].append((env, item))
        inventory[env].append('playwright-' + lock['playwright'] + ' (shared browser)')
    # One Playwright release for all processes, validated by the offline portal tests.
    selected = ROOT / 'bots/detalles/.venv/Lib/site-packages'
    for item in selected.glob('playwright*'):
        candidates[item.name].append(('shared', item))
    saved = 0
    versions = defaultdict(set)
    for name in candidates:
        if name.endswith('.dist-info'):
            family, version = name.removesuffix('.dist-info').rsplit('-', 1)
            versions[family].add(version)
    for name, entries in sorted(candidates.items()):
        if len(entries) == 1:
            equal = True
        else:
            hashes = [digest(item) for _, item in entries]
            equal = len(set(hashes)) == 1
        if name.endswith('.dist-info') and len(versions[name.removesuffix('.dist-info').rsplit('-', 1)[0]]) > 1:
            equal = False
        targets = [('shared', entries[0][1])] if equal else entries
        # A minority version (e.g. BLs pandas) overrides the shared majority via _pth.
        # Do not duplicate the majority just because one bot requires another version.
        if not equal and not name.endswith('.dist-info'):
            groups = defaultdict(list)
            for entry, sha in zip(entries, hashes):
                groups[sha].append(entry)
            majority = max(groups.values(), key=len)
            if len(majority) > 1:
                targets = [('shared', majority[0][1])] + [entry for entry in entries if entry not in majority]
                saved += sum(f.stat().st_size for f, _ in files(majority[0][1])) * (len(majority) - 1)
        for env, item in targets:
            destination = shared / 'site-packages' if env == 'shared' else out / env / '.venv/Lib/site-packages'
            for source, relative in files(item):
                copy_file(source, destination / relative)
        if equal:
            saved += sum(file.stat().st_size for file, _ in files(entries[0][1])) * (len(entries) - 1)
        print('Dependency:', name, 'shared' if equal else 'separate', flush=True)
    dlls = ['python.exe', 'pythonw.exe', 'python312.dll', 'python3.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']
    for env in ENVS:
        scripts = out / env / '.venv/Scripts'
        scripts.mkdir(parents=True)
        for name in dlls:
            copy_file(base / name, scripts / name)
        locations = [shared / 'python/Lib', shared / 'python/DLLs',
                     out / env / '.venv/Lib/site-packages', shared / 'site-packages', out, out / 'workbench']
        text = '\n'.join(os.path.relpath(p, scripts) for p in locations) + '\nimport site\n'
        (scripts / 'python312._pth').write_text(text, encoding='utf-8')
    # Imported by each isolated interpreter, even before workers import engines.
    (out / 'sitecustomize.py').write_text(
        'import os, sys\nfrom pathlib import Path\n'
        'root = Path(__file__).resolve().parent\n'
        'sys.dont_write_bytecode = True\n'
        'os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(root / "_runtime/browsers")\n'
        'os.environ["TCL_LIBRARY"] = str(root / "_runtime/python/tcl/tcl8.6")\n'
        'os.environ["TK_LIBRARY"] = str(root / "_runtime/python/tcl/tk8.6")\n', encoding='utf-8')
    return inventory, saved


def browser(out, lock):
    cache = Path(os.environ['LOCALAPPDATA']) / 'ms-playwright'
    for name in ('chromium-' + lock['chromium_revision'], 'winldd-1007'):
        copy_tree(cache / name, out / '_runtime/browsers' / name)
    # Full Chromium is shared with Selenium. Only its matching driver is additional.
    downloads = ROOT / 'runtime/build-cache'
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / ('chromedriver-' + lock['version'] + '.zip')
    if not archive.exists():
        temporary = archive.with_suffix('.download')
        with urllib.request.urlopen(lock['downloads']['chromedriver'], timeout=90) as response, temporary.open('wb') as target:
            shutil.copyfileobj(response, target)
        temporary.replace(archive)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    if lock.get('sha256') and sha != lock['sha256']:
        raise RuntimeError('ChromeDriver hash differs from release lock.')
    with zipfile.ZipFile(archive) as z:
        z.extractall(out / '_runtime/selenium')
    return sha


def compile_launcher(out):
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
                    '/win32manifest:' + str(HERE / 'app.manifest'),
                    '/reference:System.Windows.Forms.dll', '/out:' + str(out / 'CHC Workbench.exe'),
                    '/win32icon:' + str(ROOT / 'workbench/assets/branding/chc.ico'), str(HERE / 'Launcher.cs')], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    lock = json.loads((HERE / 'browser.lock.json').read_text())
    copy_code(out)
    copy_file(HERE / 'LEEME.txt', out / 'LEEME.txt')
    inventory, saved = runtimes(out, lock)
    driver_hash = browser(out, lock)
    compile_launcher(out)
    metadata = {'name': 'CHC Workbench', 'version': '2026.10.22', 'platform': 'Windows 10/11 x64',
                'python': sys.version.split()[0], 'chromium_revision': lock['chromium_revision'],
                'browser_version': lock['version'], 'driver_sha256': driver_hash,
                'dependencies': inventory, 'deduplicated_bytes': saved}
    (out / 'distribution.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(out), 'deduplicated_MiB': round(saved / 1048576),
                      'driver_sha256': driver_hash}), flush=True)


if __name__ == '__main__':
    main()
