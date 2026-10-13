@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\bls\.venv\Scripts\python.exe" (
    py -3.12 -m venv bots\bls\.venv
    if errorlevel 1 exit /b 1
)
"bots\bls\.venv\Scripts\python.exe" -m pip install -r bots\bls\requirements.workbench.lock.txt
if errorlevel 1 exit /b 1
"bots\bls\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo BLs instalado. Abra Abrir_Workbench.bat.
pause
