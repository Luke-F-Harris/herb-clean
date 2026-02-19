@echo off
REM Debug inventory detection
REM Run from project root: scripts\windows\debug_inventory.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run debug script
python debug\debug_inventory.py
pause
