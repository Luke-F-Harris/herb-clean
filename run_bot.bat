@echo off
REM Quick launcher for the bot

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Run bot
python .\src\main.py %*
pause
