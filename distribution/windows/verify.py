"""Exercise the delivered interpreters, engines, browsers and EXE without TICA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

MODULES = ('detalles', 'duas_transito', 'talon', 'xmovimientos', 'manifiestos', 'bls')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    root = args.folder.resolve()
    report = {}
    manifest = root / 'SHA256SUMS.json'
    if manifest.exists():
        hashes = json.loads(manifest.read_text(encoding='utf-8'))
        for relative, expected in hashes.items():
            file = (root / relative).resolve()
            assert file.is_relative_to(root), relative
            assert hashlib.sha256(file.read_bytes()).hexdigest() == expected, relative
        report['payload integrity'] = {'files': len(hashes), 'verified': True}
        print('Payload integrity: OK (' + str(len(hashes)) + ' files)', flush=True)
    with tempfile.TemporaryDirectory(prefix='CHC-package-') as folder:
        home = Path(folder)
        env = {**os.environ, 'CHC_WORKBENCH_HOME': str(home / 'user'),
               'PYTHONHOME': str(home / 'nonexistent-python'), 'PYTHONPATH': str(home / 'nonexistent-site'),
               'PLAYWRIGHT_BROWSERS_PATH': str(home / 'nonexistent-browsers'),
               'PATH': os.environ['WINDIR'] + ';' + os.environ['WINDIR'] + '/System32',
               'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'}

        def run(name, command, data=None, timeout=90):
            process = subprocess.run([str(x) for x in command], input=data, capture_output=True,
                                     encoding='utf-8', errors='replace', env=env, cwd=home, timeout=timeout)
            report[name] = {'exit': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            if process.returncode:
                logs = list((home / 'user/runtime/workbench/logs').glob('*.log'))
                report[name]['launcher_logs'] = [f.read_text(encoding='utf-8')[-6000:] for f in logs]
                args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
                raise RuntimeError(name + ': ' + process.stderr + process.stdout)
            print(name + ': OK', flush=True)
            return process.stdout

        for module in ('workbench', *('bots/' + m for m in MODULES)):
            python = root / module / '.venv/Scripts/python.exe'
            result = json.loads(run(module + ' isolated runtime', [python, '-c',
                'import sys,json; print(json.dumps({"executable":sys.executable,"path":sys.path,"isolated":sys.flags.isolated}))']))
            assert result['isolated'] == 1
            assert all(Path(value).resolve().is_relative_to(root) for value in result['path'])
            if module == 'workbench':
                run('Qt and OAuth dependencies', [python, '-c', 'import PySide6.QtQuick,msal,msal_extensions,cryptography; print("OK")'])
                continue
            bot = module.split('/')[1]
            flows = ('tabla', 'conocimientos', 'duas', 'movimientos', 'contenedores', 'bases', 'bls_source') if bot == 'manifiestos' else ('bls',) if bot == 'bls' else ('',)
            for flow in flows:
                command = [python, root / module / 'workbench_worker.py', '--storage-root', home / bot / (flow or 'main')]
                if bot in ('manifiestos', 'bls'):
                    command += ['--flow', flow]
                output = run(bot + ':' + flow + ' initialize', command, '{"command":"shutdown"}\n')
                assert any(json.loads(line).get('event') in ('ready', 'closed') for line in output.splitlines() if line.startswith('{'))
            run(bot + ' bundled browser', [python, '-c',
                'import asyncio; from playwright.async_api import async_playwright; '
                'from chc_runtime.distribution import chromium_options\n'
                'async def main():\n'
                ' async with async_playwright() as pw:\n'
                '  browser=await pw.chromium.launch(headless=True, **chromium_options())\n'
                '  page=await browser.new_page(); await page.set_content("<p>000123</p>")\n'
                '  assert await page.inner_text("p")=="000123"; await browser.close()\n'
                'asyncio.run(main()); print("OK")'])
        python = root / 'bots/detalles/.venv/Scripts/python.exe'
        run('Selenium shares bundled Chromium', [python, '-c',
            'import sys; from pathlib import Path; from chc_runtime.distribution import CODE_ROOT; '
            'sys.path.insert(0,str(CODE_ROOT/"integrations/duas_source/src")); '
            'from chc_runtime.selenium_browser import bundled_extractor; '
            'bot=bundled_extractor()({"mostrar_navegador":False}); '
            'bot.driver.get("data:text/html,<p>000123</p>"); '
            'assert bot.driver.find_element("tag name","p").text=="000123"; bot.close(); print("OK")'])
        run('EXE and QML navigation', [root / 'CHC Workbench.exe', '--smoke-test'], timeout=120)
        logs = list((home / 'user/runtime/workbench/logs').glob('*.log'))
        report['launcher_logs'] = [path.read_text(encoding='utf-8') for path in logs]
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('All distribution checks passed.', flush=True)


if __name__ == '__main__':
    main()
