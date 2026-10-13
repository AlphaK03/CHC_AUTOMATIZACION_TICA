@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\manifiestos\.venv\Scripts\python.exe" (
    py -3.12 -m venv bots\manifiestos\.venv
    if errorlevel 1 exit /b 1
)
"bots\manifiestos\.venv\Scripts\python.exe" -m pip install -r bots\manifiestos\requirements.workbench.lock.txt
if errorlevel 1 exit /b 1
"bots\manifiestos\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo Manifiestos instalado. Abra Abrir_Workbench.bat.
pause
