@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\duas_transito\.venv\Scripts\python.exe" (
    py -3.12 -m venv bots\duas_transito\.venv
    if errorlevel 1 exit /b 1
)
"bots\duas_transito\.venv\Scripts\python.exe" -m pip install -r bots\duas_transito\requirements.workbench.lock.txt
if errorlevel 1 exit /b 1
"bots\duas_transito\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo DUAs Transito instalado. Abra Abrir_Workbench.bat.
pause
