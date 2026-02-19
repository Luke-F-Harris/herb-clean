@echo off
REM Download herb template images from OSRSBox
REM Run from project root: scripts\windows\download_templates.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run download script
python scripts\setup\download_herb_templates.py
pause
