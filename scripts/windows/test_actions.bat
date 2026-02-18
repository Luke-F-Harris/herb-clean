@echo off
REM Test all bot actions
REM Run from project root: scripts\windows\test_actions.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run comprehensive test
python tests\test_bot_actions.py
pause
