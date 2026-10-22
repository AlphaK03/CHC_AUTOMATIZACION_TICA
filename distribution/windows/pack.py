"""Seal a verified folder as a ZIP and an installer; refuse operational files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    args = p.parse_args()
    folder = args.folder.resolve()
    metadata = json.loads((folder / 'distribution.json').read_text())
    archive = folder.with_suffix('.zip')
    installer = folder.parent / 'Instalar CHC Workbench x64.exe'
    files = sorted(f for f in folder.rglob('*') if f.is_file())
    for file in files:
        rel = file.relative_to(folder)
        if (set(rel.parts) & {'runtime', 'data', 'logs', '__pycache__'}
                or file.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.csv', '.xlsx', '.pyc'}
                or file.name in {'config.json', 'machine.json', 'session.json'}):
            raise RuntimeError('Operational or generated file in package: ' + str(rel))
    # Integrity manifest excludes itself and is distributed alongside all licenses.
    hashes = {f.relative_to(folder).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files if f.name != 'SHA256SUMS.json'}
    (folder / 'SHA256SUMS.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    files = sorted(f for f in folder.rglob('*') if f.is_file())
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            z.write(f, f.relative_to(folder).as_posix())
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
                    '/win32manifest:' + str(HERE / 'app.manifest'),
                    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
                    '/reference:System.IO.Compression.dll', '/out:' + str(installer),
                    '/resource:' + str(archive) + ',payload.zip',
                    '/win32icon:' + str(folder / 'workbench/assets/branding/chc.ico'), str(HERE / 'Installer.cs')], check=True)
    report = {'installer': installer.name, 'installer_bytes': installer.stat().st_size,
              'installed_bytes': sum(f.stat().st_size for f in files), 'files': len(files),
              'sha256': hashlib.sha256(installer.read_bytes()).hexdigest(),
              'platform': metadata['platform']}
    (folder.parent / 'release.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
