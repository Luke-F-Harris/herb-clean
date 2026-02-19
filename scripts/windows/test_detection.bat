@echo off
REM Test inventory detection
REM Run from project root: scripts\windows\test_detection.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run test
python tests\test_inventory_detection.py
pause
