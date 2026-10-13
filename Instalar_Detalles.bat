@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\detalles\.venv\Scripts\python.exe" (
    py -3.12 -m venv bots\detalles\.venv
    if errorlevel 1 exit /b 1
)
"bots\detalles\.venv\Scripts\python.exe" -m pip install -r bots\detalles\requirements.workbench.lock.txt
if errorlevel 1 exit /b 1
"bots\detalles\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo Detalles instalado. Abra Abrir_Workbench.bat.
pause
