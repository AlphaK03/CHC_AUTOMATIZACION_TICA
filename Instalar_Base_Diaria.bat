@echo off
setlocal
cd /d "%~dp0"
if not exist "bots\detalles\.venv\Scripts\python.exe" (
    echo Primero ejecute Instalar_Detalles.bat.
    pause
    exit /b 1
)
"bots\detalles\.venv\Scripts\python.exe" "tools\install_daily_driver.py"
if errorlevel 1 (
    echo No se pudo preparar la descarga diaria.
    pause
    exit /b 1
)
echo Base diaria preparada. No se realizaron consultas a TICA.
pause
