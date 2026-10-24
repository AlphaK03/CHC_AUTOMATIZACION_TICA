@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\xmovimientos\.venv\Scripts\python.exe" (
    echo Primero ejecute Instalar_XMovimientos.bat.
    pause
    exit /b 1
)
"bots\xmovimientos\.venv\Scripts\python.exe" "tools\compact_movement_evidence.py" --interactive
pause
