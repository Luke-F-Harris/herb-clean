@echo off
REM Interactive inventory setup tool
REM Run from project root: scripts\windows\setup_inventory.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run setup tool
python scripts\setup\setup_inventory.py
pause
