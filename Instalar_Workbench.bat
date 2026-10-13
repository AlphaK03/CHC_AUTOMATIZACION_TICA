@echo off
setlocal
cd /d "%~dp0"
if not exist "workbench\.venv\Scripts\python.exe" (
    py -3.12 -m venv workbench\.venv
    if errorlevel 1 exit /b 1
)
"workbench\.venv\Scripts\python.exe" -m pip install -r workbench\requirements.txt
if errorlevel 1 exit /b 1
echo Panel instalado. Abra Abrir_Workbench.bat.
pause
