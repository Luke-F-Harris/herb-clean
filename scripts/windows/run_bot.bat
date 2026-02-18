@echo off
REM Quick launcher for the bot
REM Run from project root: scripts\windows\run_bot.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run bot
python main.py %*
pause
