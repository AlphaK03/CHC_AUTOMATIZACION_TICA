@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\xmovimientos\.venv\Scripts\python.exe" (
    py -3.12 -m venv bots\xmovimientos\.venv
    if errorlevel 1 exit /b 1
)
"bots\xmovimientos\.venv\Scripts\python.exe" -m pip install -r bots\xmovimientos\requirements.workbench.lock.txt
if errorlevel 1 exit /b 1
"bots\xmovimientos\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo XMovimientos instalado. Abra Abrir_Workbench.bat.
pause
