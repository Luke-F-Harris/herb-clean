@echo off
REM Interactive inventory setup tool

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Run setup tool
python setup_inventory.py
pause
