@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Falta .venv. Consulte la instalacion en README.md.
    exit /b 1
)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name BLs_BOT_AstraCode --distpath build\release --workpath build\pyinstaller --specpath build --hidden-import playwright.async_api --collect-data bs4 --collect-data openpyxl src\main.py
if errorlevel 1 exit /b 1
if not exist "dist" mkdir "dist"
copy /y "build\release\BLs_BOT_AstraCode.exe" "dist\BLs_BOT_AstraCode.exe" >nul
if errorlevel 1 (
    echo No se pudo actualizar el ejecutable. Cierre la aplicacion y copie build\release\BLs_BOT_AstraCode.exe a dist.
    exit /b 1
)
echo Ejecutable generado: dist\BLs_BOT_AstraCode.exe
