@echo off
REM Download herb template images from OSRSBox

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Run download script
python download_herb_templates.py
pause
