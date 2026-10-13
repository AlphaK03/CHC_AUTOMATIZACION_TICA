@echo off
setlocal
cd /d "%~dp0"
if not exist "workbench\.venv\Scripts\pythonw.exe" (
    echo Primero ejecute Instalar_Workbench.bat.
    pause
    exit /b 1
)
start "" "workbench\.venv\Scripts\pythonw.exe" "workbench\app.py"
