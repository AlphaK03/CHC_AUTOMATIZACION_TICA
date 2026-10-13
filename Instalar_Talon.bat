@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\talon\.venv\Scripts\python.exe" (
    py -3.12 -m venv bots\talon\.venv
    if errorlevel 1 exit /b 1
)
"bots\talon\.venv\Scripts\python.exe" -m pip install -r bots\talon\requirements.workbench.lock.txt
if errorlevel 1 exit /b 1
"bots\talon\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo Talon instalado. Abra Abrir_Workbench.bat.
pause
